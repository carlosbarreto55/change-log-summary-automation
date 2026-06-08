import shutil
import subprocess
import unittest
from pathlib import Path

from release_notes_generator.commits import (
    GitCommitExtractor,
    filter_commits,
    group_commit_hashes_by_module,
)
from release_notes_generator.configuration import (
    load_module_config,
    load_release_marker_config,
    load_user_config,
)
from release_notes_generator.diffs import generate_diff_files
from release_notes_generator.paths import CONFIG_DIR, PROJECT_ROOT
from release_notes_generator.workflow import ReleaseNotesWorkflow


REDIS_REPOSITORY_PATH = PROJECT_ROOT.parent / "redis"
USER_IT_CONFIG_PATH = CONFIG_DIR / "userIT.json"
MODULE_IT_CONFIG_PATH = CONFIG_DIR / "moduleIT.json"
RELEASE_MARKER_IT_CONFIG_PATH = CONFIG_DIR / "releaseMarkerIT.json"
WORKFLOW_REDIS_IT_CONFIG_PATH = CONFIG_DIR / "workflowRedisIT.json"
ASSETS_DIR = PROJECT_ROOT / "tests" / "assets"


class RecordingSummaryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def summarize(self, module_name: str, diff_content: str) -> str:
        self.calls.append((module_name, diff_content))
        return f"- Summary for {module_name}"


class RedisWorkflowIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not REDIS_REPOSITORY_PATH.exists():
            raise unittest.SkipTest(
                f"Redis integration fixture not found at {REDIS_REPOSITORY_PATH}. "
                "Clone it once outside the test run."
            )

        result = subprocess.run(
            ["git", "-C", str(REDIS_REPOSITORY_PATH), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise unittest.SkipTest(
                f"Redis integration fixture is not a Git repository: {REDIS_REPOSITORY_PATH}"
            )

    def test_redis_integration_configuration_loads_marker_users_and_groups(self) -> None:
        release_marker_config = load_release_marker_config(RELEASE_MARKER_IT_CONFIG_PATH)
        user_config = load_user_config(USER_IT_CONFIG_PATH)
        module_config = load_module_config(MODULE_IT_CONFIG_PATH)

        self.assertEqual(release_marker_config.marker, "Update to latest hiredis (#10297)")
        self.assertEqual(
            user_config.approved_author_emails,
            ("debing.sun@redis.com", "vitahlin@gmail.com", "moticless@gmail.com"),
        )
        self.assertEqual(
            module_config.module_tags,
            {"Add": ("Add", "add"), "Fix": ("Fix", "fix")},
        )

    def test_redis_workflow_locates_release_marker_commit(self) -> None:
        release_marker_config = load_release_marker_config(RELEASE_MARKER_IT_CONFIG_PATH)
        extractor = GitCommitExtractor(REDIS_REPOSITORY_PATH)

        marker_hash = extractor.latest_release_marker_hash(release_marker_config.marker)

        self.assertEqual(marker_hash, "e8c5b66ed2aaf40bec345ff5aca90721fb707d30")

    def test_redis_workflow_extracts_large_commit_range_after_marker(self) -> None:
        release_marker_config = load_release_marker_config(RELEASE_MARKER_IT_CONFIG_PATH)
        extractor = GitCommitExtractor(REDIS_REPOSITORY_PATH)

        commits = extractor.commits_after_latest_release_marker(release_marker_config.marker)

        self.assertGreaterEqual(len(commits), 2000)
        self.assertNotIn(
            "Update to latest hiredis (#10297)",
            {commit.subject for commit in commits},
        )
        self.assertTrue(all(commit.commit_hash for commit in commits))
        self.assertTrue(all(commit.author_email for commit in commits))
        self.assertTrue(all(commit.subject for commit in commits))

    def test_redis_workflow_filters_commits_by_users_and_groups(self) -> None:
        release_marker_config = load_release_marker_config(RELEASE_MARKER_IT_CONFIG_PATH)
        user_config = load_user_config(USER_IT_CONFIG_PATH)
        module_config = load_module_config(MODULE_IT_CONFIG_PATH)
        commits = GitCommitExtractor(REDIS_REPOSITORY_PATH).commits_after_latest_release_marker(
            release_marker_config.marker
        )

        accepted_commits = filter_commits(
            commits,
            user_config.approved_author_emails,
            module_config.module_tags,
        )
        accepted_authors = {commit.author_email for commit in accepted_commits}
        accepted_groups = {commit.module_name for commit in accepted_commits}

        self.assertGreaterEqual(len(accepted_commits), 100)
        self.assertEqual(accepted_groups, {"Add", "Fix"})
        self.assertLessEqual(accepted_authors, set(user_config.approved_author_emails))
        self.assertTrue(
            all(
                commit.subject.startswith(tuple(module_config.module_tags[commit.module_name]))
                for commit in accepted_commits
            )
        )

    def test_redis_workflow_extracts_filters_groups_and_writes_separated_diff_files(self) -> None:
        _reset_assets_dir()
        release_marker_config = load_release_marker_config(RELEASE_MARKER_IT_CONFIG_PATH)
        user_config = load_user_config(USER_IT_CONFIG_PATH)
        module_config = load_module_config(MODULE_IT_CONFIG_PATH)
        commits = GitCommitExtractor(REDIS_REPOSITORY_PATH).commits_after_latest_release_marker(
            release_marker_config.marker
        )
        accepted_commits = filter_commits(
            commits,
            user_config.approved_author_emails,
            module_config.module_tags,
        )

        try:
            grouped_hashes = group_commit_hashes_by_module(accepted_commits)
            generated_files = generate_diff_files(REDIS_REPOSITORY_PATH, grouped_hashes, ASSETS_DIR)
            add_diff = generated_files["Add"].read_text(encoding="utf-8")
            fix_diff = generated_files["Fix"].read_text(encoding="utf-8")

            self.assertEqual(set(generated_files), {"Add", "Fix"})
            self.assertGreaterEqual(len(grouped_hashes["Add"]), 10)
            self.assertGreaterEqual(len(grouped_hashes["Fix"]), 100)
            self.assertGreater(generated_files["Add"].stat().st_size, 100_000)
            self.assertGreater(generated_files["Fix"].stat().st_size, 500_000)
            self.assertFalse(set(grouped_hashes["Add"]) & set(grouped_hashes["Fix"]))
            self.assertIn(f"commit {grouped_hashes['Add'][0]}", add_diff)
            self.assertNotIn(f"commit {grouped_hashes['Fix'][0]}", add_diff)
            self.assertIn(f"commit {grouped_hashes['Fix'][0]}", fix_diff)
            self.assertNotIn(f"commit {grouped_hashes['Add'][0]}", fix_diff)
        finally:
            _reset_assets_dir()

    def test_redis_full_workflow_generates_single_output_and_cleans_temporary_diffs(self) -> None:
        _reset_assets_dir()
        client = RecordingSummaryClient()

        try:
            with unittest.mock.patch(
                "release_notes_generator.workflow.synchronize_repository"
            ) as synchronize:
                result = ReleaseNotesWorkflow(summary_client=client).run(
                    WORKFLOW_REDIS_IT_CONFIG_PATH
                )

            output_path = ASSETS_DIR / "release_notes.md"
            output = output_path.read_text(encoding="utf-8")
            generated_files = tuple(ASSETS_DIR.rglob("*"))
            generated_file_paths = tuple(
                path for path in generated_files if path.is_file() and path.name != ".gitkeep"
            )
            remaining_diff_files = tuple(ASSETS_DIR.rglob("diff_*.md"))

            self.assertEqual(result, 0)
            synchronize.assert_called_once_with(REDIS_REPOSITORY_PATH)
            self.assertEqual({module_name for module_name, _ in client.calls}, {"Add", "Fix"})
            self.assertTrue(all("commit " in diff_content for _, diff_content in client.calls))
            self.assertTrue(output_path.is_file())
            self.assertEqual(generated_file_paths, (output_path,))
            self.assertEqual(remaining_diff_files, ())
            self.assertIn("## Global Features", output)
            self.assertIn("## Pix", output)
        finally:
            _reset_assets_dir()


def _reset_assets_dir() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for path in ASSETS_DIR.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


if __name__ == "__main__":
    unittest.main()

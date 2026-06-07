import subprocess
import unittest
from pathlib import Path

from release_notes_generator.commits import GitCommitExtractor, filter_commits
from release_notes_generator.configuration import (
    load_module_config,
    load_release_marker_config,
    load_user_config,
)
from release_notes_generator.paths import CONFIG_DIR, PROJECT_ROOT


REDIS_REPOSITORY_PATH = PROJECT_ROOT.parent / "redis"
USER_IT_CONFIG_PATH = CONFIG_DIR / "userIT.json"
MODULE_IT_CONFIG_PATH = CONFIG_DIR / "moduleIT.json"
RELEASE_MARKER_IT_CONFIG_PATH = CONFIG_DIR / "releaseMarkerIT.json"


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

    def test_redis_workflow_extracts_filters_and_separates_large_diff_payloads(self) -> None:
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

        grouped_hashes: dict[str, list[str]] = {module_name: [] for module_name in module_config.module_tags}
        for commit in accepted_commits:
            grouped_hashes[commit.module_name].append(commit.commit_hash)

        diff_sizes = {
            module_name: _combined_diff_size(commit_hashes)
            for module_name, commit_hashes in grouped_hashes.items()
        }

        self.assertGreaterEqual(len(grouped_hashes["Add"]), 10)
        self.assertGreaterEqual(len(grouped_hashes["Fix"]), 100)
        self.assertGreater(diff_sizes["Add"], 100_000)
        self.assertGreater(diff_sizes["Fix"], 500_000)
        self.assertFalse(set(grouped_hashes["Add"]) & set(grouped_hashes["Fix"]))


def _combined_diff_size(commit_hashes: list[str]) -> int:
    size = 0
    for commit_hash in commit_hashes:
        result = subprocess.run(
            ["git", "-C", str(REDIS_REPOSITORY_PATH), "show", "--format=fuller", commit_hash],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr.strip() or f"git show failed for {commit_hash}")
        size += len(result.stdout)
    return size


if __name__ == "__main__":
    unittest.main()

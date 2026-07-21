import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.commits import (
    GitCommitExtractor,
    filter_commits,
    group_commit_hashes_by_module,
    synchronize_repository,
)
from release_notes_generator.configuration import (
    load_ai_config,
    load_module_config,
    load_release_marker_config,
    load_user_config,
)
from release_notes_generator.diffs import generate_diff_files
from release_notes_generator.paths import CONFIG_DIR, PROJECT_ROOT
from release_notes_generator.pdf_export import export_release_pdf
from release_notes_generator.workflow import ReleaseNotesWorkflow


LINUX_REPOSITORY_PATH = PROJECT_ROOT.parent / "linux"
USER_IT_CONFIG_PATH = CONFIG_DIR / "userIT.json"
MODULE_IT_CONFIG_PATH = CONFIG_DIR / "moduleIT.json"
RELEASE_MARKER_IT_CONFIG_PATH = CONFIG_DIR / "releaseMarkerIT.json"
AI_IT_CONFIG_PATH = CONFIG_DIR / "aiIT.json"
WORKFLOW_LINUX_IT_CONFIG_PATH = CONFIG_DIR / "workflowLinuxIT.json"

EXPECTED_MODULES = ("Wi-Fi", "Network Core", "KVM", "ALSA SoC", "KSMBD")
EXPECTED_SECTIONS = ("Networking", "Virtualization", "Audio", "Filesystems")


class RecordingSummaryClient:
    def __init__(self) -> None:
        self.summarize_calls: list[tuple[str, str]] = []
        self.reduce_calls: list[tuple[str, str]] = []

    def summarize(self, module_name: str, diff_content: str) -> str:
        self.summarize_calls.append((module_name, diff_content))
        return f"- {module_name} chunk {len(self.summarize_calls)}"

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        self.reduce_calls.append((module_name, partial_summaries))
        return f"- Combined {module_name} changes"


class LinuxWorkflowIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not LINUX_REPOSITORY_PATH.exists():
            raise unittest.SkipTest(
                f"Linux integration fixture not found at {LINUX_REPOSITORY_PATH}. "
                "Clone git@github.com:torvalds/linux.git once outside the test run."
            )

        result = subprocess.run(
            ["git", "-C", str(LINUX_REPOSITORY_PATH), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise unittest.SkipTest(
                f"Linux integration fixture is not a Git repository: {LINUX_REPOSITORY_PATH}"
            )

    def test_linux_integration_configuration_uses_verified_history_data(self) -> None:
        release_marker_config = load_release_marker_config(RELEASE_MARKER_IT_CONFIG_PATH)
        user_config = load_user_config(USER_IT_CONFIG_PATH)
        module_config = load_module_config(MODULE_IT_CONFIG_PATH)
        ai_config = load_ai_config(AI_IT_CONFIG_PATH)

        self.assertEqual(release_marker_config.marker, "Linux 7.1")
        self.assertEqual(
            user_config.approved_author_emails,
            (
                "kuba@kernel.org",
                "johannes.berg@intel.com",
                "seanjc@google.com",
                "broonie@kernel.org",
                "linkinjeon@kernel.org",
            ),
        )
        self.assertEqual(
            tuple((module.name, module.tags, module.section) for module in module_config.modules),
            (
                ("Wi-Fi", ("wifi:",), "Networking"),
                ("Network Core", ("net:",), "Networking"),
                ("KVM", ("KVM:",), "Virtualization"),
                ("ALSA SoC", ("ASoC:",), "Audio"),
                ("KSMBD", ("ksmbd:",), "Filesystems"),
            ),
        )
        self.assertEqual(ai_config.max_diff_characters_per_request, 120_000)

    def test_linux_workflow_locates_release_marker_commit(self) -> None:
        release_marker_config = load_release_marker_config(RELEASE_MARKER_IT_CONFIG_PATH)

        marker_hash = GitCommitExtractor(LINUX_REPOSITORY_PATH).latest_release_marker_hash(
            release_marker_config.marker
        )

        self.assertEqual(marker_hash, "8cd9520d35a6c38db6567e97dd93b1f11f185dc6")

    def test_linux_workflow_extracts_large_commit_range_after_marker(self) -> None:
        release_marker_config = load_release_marker_config(RELEASE_MARKER_IT_CONFIG_PATH)

        commits = GitCommitExtractor(
            LINUX_REPOSITORY_PATH
        ).commits_after_latest_release_marker(release_marker_config.marker)

        self.assertGreaterEqual(len(commits), 15_000)
        self.assertNotIn("Linux 7.1", {commit.subject for commit in commits})
        self.assertTrue(all(commit.commit_hash for commit in commits))
        self.assertTrue(all(commit.author_email for commit in commits))
        self.assertTrue(all(commit.subject for commit in commits))

    def test_linux_workflow_filters_verified_contributors_and_prefixes(self) -> None:
        accepted_commits = _accepted_linux_commits(LINUX_REPOSITORY_PATH)
        user_config = load_user_config(USER_IT_CONFIG_PATH)
        module_config = load_module_config(MODULE_IT_CONFIG_PATH)

        self.assertGreaterEqual(len(accepted_commits), 350)
        self.assertEqual({commit.module_name for commit in accepted_commits}, set(EXPECTED_MODULES))
        self.assertLessEqual(
            {commit.author_email for commit in accepted_commits},
            set(user_config.approved_author_emails),
        )
        self.assertTrue(
            all(
                commit.subject.startswith(module_config.module_tags[commit.module_name])
                for commit in accepted_commits
            )
        )

    def test_temporary_linux_clone_rebases_and_generates_separated_diffs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repository_path = _temporary_linux_clone(temp_root)
            synchronize_repository(repository_path)
            accepted_commits = _accepted_linux_commits(repository_path)
            grouped_hashes = group_commit_hashes_by_module(accepted_commits)

            generated_files = generate_diff_files(
                repository_path,
                grouped_hashes,
                temp_root / "diffs",
            )

            minimum_counts = {
                "Wi-Fi": 100,
                "Network Core": 30,
                "KVM": 80,
                "ALSA SoC": 60,
                "KSMBD": 70,
            }
            self.assertEqual(set(generated_files), set(EXPECTED_MODULES))
            for module_name, minimum_count in minimum_counts.items():
                self.assertGreaterEqual(len(grouped_hashes[module_name]), minimum_count)
                self.assertGreater(generated_files[module_name].stat().st_size, 10_000)

            first_hashes = {
                module_name: commit_hashes[0]
                for module_name, commit_hashes in grouped_hashes.items()
            }
            for module_name, diff_file in generated_files.items():
                diff_content = diff_file.read_text(encoding="utf-8")
                self.assertIn(f"commit {first_hashes[module_name]}", diff_content)
                for other_module, other_hash in first_hashes.items():
                    if other_module != module_name:
                        self.assertNotIn(f"commit {other_hash}", diff_content)

    def test_linux_full_workflow_bounds_calls_generates_pdf_and_cleans_diffs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repository_path = _temporary_linux_clone(temp_root)
            output_path = temp_root / "release_notes.pdf"
            diff_dir = temp_root / "diffs"
            runtime_config_path = _temporary_runtime_config(
                temp_root,
                repository_path,
                diff_dir,
                output_path,
            )
            client = RecordingSummaryClient()
            documents = []

            def recording_export(document, destination) -> None:
                documents.append(document)
                export_release_pdf(document, destination)

            with patch(
                "release_notes_generator.workflow.export_release_pdf",
                side_effect=recording_export,
            ):
                result = ReleaseNotesWorkflow(summary_client=client).run(runtime_config_path)

            request_limit = load_ai_config(
                AI_IT_CONFIG_PATH
            ).max_diff_characters_per_request
            self.assertEqual(result, 0)
            self.assertEqual(output_path.read_bytes()[:5], b"%PDF-")
            self.assertEqual(tuple(diff_dir.glob("diff_*.md")), ())
            self.assertGreater(len(client.summarize_calls), len(EXPECTED_MODULES))
            self.assertTrue(client.reduce_calls)
            self.assertEqual(
                {module_name for module_name, _ in client.summarize_calls},
                set(EXPECTED_MODULES),
            )
            self.assertTrue(
                all(len(payload) <= request_limit for _, payload in client.summarize_calls)
            )
            self.assertTrue(
                all(len(payload) <= request_limit for _, payload in client.reduce_calls)
            )
            self.assertEqual(len(documents), 1)
            self.assertEqual(
                tuple(section.title for section in documents[0].sections),
                EXPECTED_SECTIONS,
            )
            self.assertEqual(
                tuple(
                    module.name
                    for section in documents[0].sections
                    for module in section.modules
                ),
                EXPECTED_MODULES,
            )


def _accepted_linux_commits(repository_path: Path):
    release_marker_config = load_release_marker_config(RELEASE_MARKER_IT_CONFIG_PATH)
    user_config = load_user_config(USER_IT_CONFIG_PATH)
    module_config = load_module_config(MODULE_IT_CONFIG_PATH)
    commits = GitCommitExtractor(repository_path).commits_after_latest_release_marker(
        release_marker_config.marker
    )
    return filter_commits(
        commits,
        user_config.approved_author_emails,
        module_config.module_tags,
    )


def _temporary_linux_clone(temp_root: Path) -> Path:
    repository_path = temp_root / "linux-worktree"
    _run_command(
        [
            "git",
            "clone",
            "--shared",
            "--no-checkout",
            str(LINUX_REPOSITORY_PATH),
            str(repository_path),
        ]
    )
    _run_command(["git", "-C", str(repository_path), "sparse-checkout", "init", "--cone"])
    _run_command(
        ["git", "-C", str(repository_path), "sparse-checkout", "set", "Documentation"]
    )
    _run_command(["git", "-C", str(repository_path), "read-tree", "-mu", "HEAD"])
    return repository_path


def _temporary_runtime_config(
    temp_root: Path,
    repository_path: Path,
    diff_dir: Path,
    output_path: Path,
) -> Path:
    runtime_data = json.loads(WORKFLOW_LINUX_IT_CONFIG_PATH.read_text(encoding="utf-8"))
    runtime_data.update(
        {
            "repository_path": str(repository_path),
            "user_config_path": str(USER_IT_CONFIG_PATH),
            "module_config_path": str(MODULE_IT_CONFIG_PATH),
            "release_marker_config_path": str(RELEASE_MARKER_IT_CONFIG_PATH),
            "ai_config_path": str(AI_IT_CONFIG_PATH),
            "temp_diff_dir": str(diff_dir),
            "output_path": str(output_path),
            "env_file_path": str(PROJECT_ROOT / ".env.local"),
        }
    )
    runtime_config_path = temp_root / "workflowLinuxIT.json"
    runtime_config_path.write_text(json.dumps(runtime_data, indent=2), encoding="utf-8")
    return runtime_config_path


def _run_command(command: list[str]) -> None:
    subprocess.run(command, capture_output=True, text=True, check=True)


if __name__ == "__main__":
    unittest.main()

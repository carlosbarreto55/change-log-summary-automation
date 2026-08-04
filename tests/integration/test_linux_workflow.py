from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.commits import (
    GitCommitExtractor,
    GitHistoryError,
    filter_commits,
)
from release_notes_generator.configuration import (
    RuntimeConfig,
    load_ai_config,
    load_module_config,
    load_release_marker_config,
    load_runtime_config,
    load_user_config,
)
from release_notes_generator.paths import CONFIG_DIR
from release_notes_generator.pdf_export import export_release_pdf
from release_notes_generator.workflow import ReleaseNotesWorkflow
from tests.context.git_state import snapshot_git_state
from tests.integration.git_fixture_state import snapshot_linux_fixture


WORKFLOW_LINUX_IT_CONFIG_PATH = CONFIG_DIR / "workflowLinuxIT.json"
EXPECTED_HEAD_SHA = "b95f03f04d475aa6719d15a636ddf32222d55657"
EXPECTED_MARKER_SHA = "8cd9520d35a6c38db6567e97dd93b1f11f185dc6"
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
        cls.runtime_config = load_runtime_config(WORKFLOW_LINUX_IT_CONFIG_PATH)
        cls.linux_repository = cls.runtime_config.repository_path
        if not cls.linux_repository.exists():
            raise unittest.SkipTest(
                f"Linux integration fixture not found at {cls.linux_repository}. "
                "Clone git@github.com:torvalds/linux.git once outside the test run."
            )

        result = subprocess.run(
            ["git", "-C", str(cls.linux_repository), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise unittest.SkipTest(
                f"Linux integration fixture is not a Git repository: "
                f"{cls.linux_repository}"
            )
        cls.external_fixture_baseline = snapshot_linux_fixture(
            cls.linux_repository
        )

    def tearDown(self) -> None:
        self.assertEqual(
            snapshot_linux_fixture(self.linux_repository),
            self.external_fixture_baseline,
            "The externally managed Linux fixture changed during an integration test.",
        )

    def test_linux_json_defines_verified_history_and_filter_data(self) -> None:
        runtime_config = load_runtime_config(WORKFLOW_LINUX_IT_CONFIG_PATH)
        release_marker_config = load_release_marker_config(
            self._selected_marker_path(runtime_config)
        )
        user_config = load_user_config(runtime_config.user_config_path)
        module_config = load_module_config(runtime_config.module_config_path)
        ai_config = load_ai_config(runtime_config.ai_config_path)

        self.assertEqual(runtime_config.repository_path, self.linux_repository)
        self.assertEqual(runtime_config.head_ref, EXPECTED_HEAD_SHA)
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
            tuple(
                (module.name, module.tags, module.section)
                for module in module_config.modules
            ),
            (
                ("Wi-Fi", ("wifi:",), "Networking"),
                ("Network Core", ("net:",), "Networking"),
                ("KVM", ("KVM:",), "Virtualization"),
                ("ALSA SoC", ("ASoC:",), "Audio"),
                ("KSMBD", ("ksmbd:",), "Filesystems"),
            ),
        )
        self.assertEqual(ai_config.max_diff_characters_per_request, 120_000)

    def test_configured_frozen_linux_range_finds_marker_and_large_history(
        self,
    ) -> None:
        runtime_config = load_runtime_config(WORKFLOW_LINUX_IT_CONFIG_PATH)
        marker = load_release_marker_config(
            self._selected_marker_path(runtime_config)
        ).marker
        extractor = GitCommitExtractor(runtime_config.repository_path)

        release_range = extractor.resolve_release_range(
            runtime_config.head_ref,
            release_marker=marker,
        )
        commits = extractor.commits_in_range(release_range)

        self.assertEqual(release_range.head_sha, EXPECTED_HEAD_SHA)
        self.assertEqual(release_range.base_sha, EXPECTED_MARKER_SHA)
        self.assertGreaterEqual(len(commits), 15_000)
        self.assertNotIn("Linux 7.1", {commit.subject for commit in commits})
        self.assertTrue(all(commit.commit_hash for commit in commits))
        self.assertTrue(all(commit.author_email for commit in commits))
        self.assertTrue(all(commit.subject for commit in commits))
        self.assertTrue(
            all(
                commit.authored_at.tzinfo is not None
                and commit.authored_at.utcoffset() is not None
                for commit in commits
            )
        )

    def test_configured_linux_range_filters_verified_contributors_and_prefixes(
        self,
    ) -> None:
        runtime_config = load_runtime_config(WORKFLOW_LINUX_IT_CONFIG_PATH)
        accepted_commits = _accepted_linux_commits(runtime_config)
        user_config = load_user_config(runtime_config.user_config_path)
        module_config = load_module_config(runtime_config.module_config_path)

        self.assertGreaterEqual(len(accepted_commits), 350)
        self.assertEqual(
            {commit.module_name for commit in accepted_commits},
            set(EXPECTED_MODULES),
        )
        self.assertLessEqual(
            {commit.author_email for commit in accepted_commits},
            set(user_config.approved_author_emails),
        )
        self.assertTrue(
            all(
                commit.subject.startswith(
                    module_config.module_tags[commit.module_name]
                )
                for commit in accepted_commits
            )
        )

    def test_direct_linux_read_only_workflow_writes_only_temporary_artifacts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            runtime_path = _temporary_runtime_config(
                temp_root,
                repository_path=self.linux_repository,
            )
            runtime_config = load_runtime_config(runtime_path)
            client = RecordingSummaryClient()
            warnings: list[str] = []
            documents = []

            def recording_export(document, destination) -> None:
                documents.append(document)
                export_release_pdf(document, destination)

            with patch(
                "release_notes_generator.workflow.export_release_pdf",
                side_effect=recording_export,
            ):
                result = ReleaseNotesWorkflow(
                    summary_client=client,
                    warning_handler=warnings.append,
                ).run(runtime_path)

            request_limit = load_ai_config(
                runtime_config.ai_config_path
            ).max_diff_characters_per_request
            self.assertEqual(result, 0)
            self.assertEqual(runtime_config.output_path.read_bytes()[:5], b"%PDF-")
            self.assertEqual(
                tuple(runtime_config.temp_diff_dir.glob("diff_*.md")),
                (),
            )
            self.assertGreater(len(client.summarize_calls), len(EXPECTED_MODULES))
            self.assertTrue(client.reduce_calls)
            self.assertEqual(
                {module_name for module_name, _ in client.summarize_calls},
                set(EXPECTED_MODULES),
            )
            self.assertTrue(
                all(
                    len(payload) <= request_limit
                    for _, payload in client.summarize_calls
                )
            )
            self.assertTrue(
                all(
                    len(payload) <= request_limit
                    for _, payload in client.reduce_calls
                )
            )
            self.assertTrue(any("dirty" in warning for warning in warnings))
            self.assertTrue(
                any("freshness is unknown" in warning for warning in warnings)
            )
            self.assertEqual(len(documents), 1)
            document = documents[0]
            self.assertEqual(document.repository_name, "linux")
            self.assertGreaterEqual(document.qualifying_change_count, 350)
            self.assertEqual(
                tuple(section.title for section in document.sections),
                EXPECTED_SECTIONS,
            )
            self.assertEqual(
                tuple(
                    module.name
                    for section in document.sections
                    for module in section.modules
                ),
                EXPECTED_MODULES,
            )

    def test_direct_linux_downstream_failure_preserves_fixture_and_writes_no_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            runtime_path = _temporary_runtime_config(
                temp_root,
                repository_path=self.linux_repository,
            )
            runtime_config = load_runtime_config(runtime_path)

            with (
                patch(
                    "release_notes_generator.workflow.GitCommitExtractor.commits_in_range",
                    side_effect=GitHistoryError("forced extraction failure"),
                ),
                self.assertRaisesRegex(GitHistoryError, "forced extraction failure"),
            ):
                ReleaseNotesWorkflow(
                    summary_client=RecordingSummaryClient()
                ).run(runtime_path)

            self.assertFalse(runtime_config.output_path.exists())
            self.assertFalse(runtime_config.temp_diff_dir.exists())

    def test_explicit_refresh_in_temporary_linux_clone_changes_only_named_tracking_ref(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repository = _temporary_linux_clone(temp_root)
            _run_git(repository, ["remote", "set-head", "origin", "--delete"])
            _run_git(
                repository,
                [
                    "update-ref",
                    "refs/remotes/origin/master",
                    EXPECTED_MARKER_SHA,
                ],
            )
            empty_users = _empty_user_config(temp_root)
            runtime_path = _temporary_runtime_config(
                temp_root,
                repository_path=repository,
                overrides={
                    "head_ref": "refs/remotes/origin/master",
                    "user_config_path": str(empty_users),
                    "repository_update_mode": "refresh_remote_refs",
                    "refresh_remote": "origin",
                    "refresh_refspecs": [
                        "+refs/heads/master:refs/remotes/origin/master"
                    ],
                },
            )
            before = snapshot_git_state(repository)

            ReleaseNotesWorkflow(
                summary_client=RecordingSummaryClient()
            ).run(runtime_path)

            after = snapshot_git_state(repository)
            self.assertEqual(after.symbolic_head, before.symbolic_head)
            self.assertEqual(after.head_sha, before.head_sha)
            self.assertEqual(after.local_refs, before.local_refs)
            self.assertEqual(after.index_sha256, before.index_sha256)
            self.assertEqual(after.index_mode, before.index_mode)
            self.assertEqual(after.index_mtime_ns, before.index_mtime_ns)
            self.assertEqual(after.index_size, before.index_size)
            self.assertEqual(after.index_tree, before.index_tree)
            self.assertEqual(after.operation_state, before.operation_state)
            self.assertEqual(after.worktree_inventory, before.worktree_inventory)
            self.assertEqual(
                _non_header_status(after.porcelain_status),
                _non_header_status(before.porcelain_status),
            )
            before_refs = dict(before.refs)
            after_refs = dict(after.refs)
            self.assertEqual(
                after_refs["refs/remotes/origin/master"],
                EXPECTED_HEAD_SHA,
            )
            changed_refs = {
                ref_name
                for ref_name in set(before_refs) | set(after_refs)
                if before_refs.get(ref_name) != after_refs.get(ref_name)
            }
            self.assertEqual(
                changed_refs,
                {"refs/remotes/origin/master"},
            )

    def test_guarded_legacy_sync_runs_only_in_temporary_linux_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repository = _temporary_linux_clone(temp_root)
            head_sha = _run_git(
                repository, ["rev-parse", "--verify", "HEAD^{commit}"]
            ).strip()
            empty_users = _empty_user_config(temp_root)
            runtime_path = _temporary_runtime_config(
                temp_root,
                repository_path=repository,
                overrides={
                    "head_ref": head_sha,
                    "base_ref": head_sha,
                    "user_config_path": str(empty_users),
                    "repository_update_mode": "legacy_in_place_sync",
                },
                remove_fields=("release_marker_config_path",),
            )

            with patch(
                "release_notes_generator.commits.subprocess.run",
                wraps=subprocess.run,
            ) as run:
                result = ReleaseNotesWorkflow(
                    summary_client=RecordingSummaryClient()
                ).run(runtime_path)

            commands = [
                call.args[0]
                for call in run.call_args_list
                if call.args and isinstance(call.args[0], list)
            ]
            fetch_index = next(
                index
                for index, command in enumerate(commands)
                if command[-2:] == ["fetch", "--prune"]
            )
            rebase_index = next(
                index
                for index, command in enumerate(commands)
                if command[-2:] == ["rebase", "@{upstream}"]
            )
            self.assertEqual(result, 0)
            self.assertLess(fetch_index, rebase_index)
            self.assertEqual(
                _run_git(repository, ["status", "--porcelain"]),
                "",
            )

    @staticmethod
    def _selected_marker_path(runtime_config: RuntimeConfig) -> Path:
        if runtime_config.release_marker_config_path is None:
            raise AssertionError("Linux integration JSON must select marker mode.")
        return runtime_config.release_marker_config_path


def _accepted_linux_commits(runtime_config: RuntimeConfig):
    if runtime_config.release_marker_config_path is None:
        raise AssertionError("Linux integration JSON must select marker mode.")
    release_marker = load_release_marker_config(
        runtime_config.release_marker_config_path
    ).marker
    user_config = load_user_config(runtime_config.user_config_path)
    module_config = load_module_config(runtime_config.module_config_path)
    extractor = GitCommitExtractor(runtime_config.repository_path)
    release_range = extractor.resolve_release_range(
        runtime_config.head_ref,
        release_marker=release_marker,
    )
    commits = extractor.commits_in_range(release_range)
    return filter_commits(
        commits,
        user_config.approved_author_emails,
        module_config.module_tags,
    )


def _temporary_linux_clone(temp_root: Path) -> Path:
    repository = temp_root / "linux-worktree"
    _run_command(
        [
            "git",
            "clone",
            "--shared",
            "--no-checkout",
            str(load_runtime_config(WORKFLOW_LINUX_IT_CONFIG_PATH).repository_path),
            str(repository),
        ]
    )
    _run_git(repository, ["sparse-checkout", "init", "--cone"])
    _run_git(repository, ["sparse-checkout", "set", "Documentation"])
    _run_git(repository, ["read-tree", "-mu", "HEAD"])
    return repository


def _temporary_runtime_config(
    temp_root: Path,
    *,
    repository_path: Path,
    overrides: dict[str, object] | None = None,
    remove_fields: tuple[str, ...] = (),
) -> Path:
    committed = load_runtime_config(WORKFLOW_LINUX_IT_CONFIG_PATH)
    runtime_data = json.loads(
        WORKFLOW_LINUX_IT_CONFIG_PATH.read_text(encoding="utf-8")
    )
    runtime_data.update(
        {
            "repository_path": str(repository_path),
            "user_config_path": str(committed.user_config_path),
            "module_config_path": str(committed.module_config_path),
            "release_marker_config_path": str(
                LinuxWorkflowIntegrationTests._selected_marker_path(committed)
            ),
            "ai_config_path": str(committed.ai_config_path),
            "temp_diff_dir": str(temp_root / "analysis" / "diffs"),
            "output_path": str(temp_root / "analysis" / "release_notes.pdf"),
            "env_file_path": str(temp_root / ".env.unused"),
        }
    )
    if overrides is not None:
        runtime_data.update(overrides)
    for field_name in remove_fields:
        runtime_data.pop(field_name, None)

    runtime_config_path = temp_root / "workflowLinuxIT.json"
    runtime_config_path.write_text(
        json.dumps(runtime_data, indent=2),
        encoding="utf-8",
    )
    return runtime_config_path


def _empty_user_config(temp_root: Path) -> Path:
    path = temp_root / "users-empty.json"
    path.write_text(
        json.dumps({"approved_author_emails": []}, indent=2),
        encoding="utf-8",
    )
    return path


def _run_git(repository: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _run_command(command: list[str]) -> None:
    subprocess.run(command, capture_output=True, text=True, check=True)


def _non_header_status(status: str) -> tuple[str, ...]:
    return tuple(
        line for line in status.splitlines() if not line.startswith("# ")
    )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.domain.configuration import (
    ClaudeCodeAISettings,
    ContributorPolicy,
    ModuleDefinition,
    ModulePolicy,
    OpenAICompatibleAISettings,
    ReportMode,
    WorkflowConfiguration,
)
from release_notes_generator.domain.summarization import SummarizationProvenance
from release_notes_generator.infrastructure.claude_code import ClaudeCodeClient
from release_notes_generator.infrastructure.git import GitAdapter
from release_notes_generator.infrastructure.json_reader import FileJSONReader
from release_notes_generator.infrastructure.reportlab_pdf import ReportLabPDFExporter
from release_notes_generator.services.commit_selection import CommitSelectionService
from release_notes_generator.services.configuration import ConfigurationService
from release_notes_generator.services.errors import GitHistoryError
from release_notes_generator.services.summarization import SummarizationService
from tests.context.application import ReleaseNotesRunner
from tests.claude_code_harness import (
    installed_fake_claude,
    load_fake_claude_records,
)
from tests.context.git_state import snapshot_git_state
from tests.integration.git_fixture_state import snapshot_linux_fixture


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
WORKFLOW_LINUX_IT_CONFIG_PATH = CONFIG_DIR / "workflowLinuxIT.json"
WORKFLOW_LINUX_COMMIT_LIST_IT_CONFIG_PATH = (
    CONFIG_DIR / "workflowLinuxCommitListIT.json"
)
EXPECTED_HEAD_SHA = "b95f03f04d475aa6719d15a636ddf32222d55657"
EXPECTED_MARKER_SHA = "8cd9520d35a6c38db6567e97dd93b1f11f185dc6"
EXPECTED_MODULES = ("Wi-Fi", "Network Core", "KVM", "ALSA SoC", "KSMBD")
EXPECTED_SECTIONS = ("Networking", "Virtualization", "Audio", "Filesystems")
EXPECTED_MODULE_COUNTS = {
    "Wi-Fi": 112,
    "Network Core": 33,
    "KVM": 86,
    "ALSA SoC": 65,
    "KSMBD": 72,
}


class RuntimeConfig:
    """Test view retaining referenced paths while delegating domain values."""

    def __init__(self, path: Path) -> None:
        self.configuration = ConfigurationService(FileJSONReader()).load(path)
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        base = Path(path).resolve(strict=False).parent
        self.user_config_path = _resolve_reference(raw["user_config_path"], base)
        self.module_config_path = _resolve_reference(raw["module_config_path"], base)
        ai_path = raw.get("ai_config_path")
        self.ai_config_path = (
            _resolve_reference(ai_path, base) if isinstance(ai_path, str) else None
        )
        marker_path = raw.get("release_marker_config_path")
        self.release_marker_config_path = (
            _resolve_reference(marker_path, base)
            if isinstance(marker_path, str)
            else None
        )

    def __getattr__(self, name: str):
        return getattr(self.configuration, name)


def _resolve_reference(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve(strict=False) if path.is_absolute() else (base / path).resolve(strict=False)


def load_runtime_config(path: Path) -> RuntimeConfig:
    return RuntimeConfig(path)


def load_user_config(path: Path) -> ContributorPolicy:
    data = FileJSONReader().read_object(path)
    return ContributorPolicy(tuple(data["approved_author_emails"]))


def load_module_config(path: Path) -> ModulePolicy:
    data = FileJSONReader().read_object(path)
    return ModulePolicy(
        tuple(
            ModuleDefinition(module["name"], tuple(module["tags"]), module["section"])
            for module in data["modules"]
        )
    )


def load_release_marker_config(path: Path):
    data = FileJSONReader().read_object(path)
    return type("ReleaseMarker", (), {"marker": data["marker"]})()


def load_ai_config(path: Path):
    data = FileJSONReader().read_object(path)
    common = (
        data["model"],
        data["prompt"],
        data["max_diff_characters_per_request"],
    )
    if data.get("backend") == "claude_code":
        return ClaudeCodeAISettings(*common)
    return OpenAICompatibleAISettings(
        data["api_url"], common[0], data["api_key_env_var"], common[1], common[2]
    )


class GitCommitExtractor:
    def __init__(self, repository_path: Path) -> None:
        self.repository_path = repository_path
        self.git = GitAdapter()

    def resolve_release_range(self, head_ref, *, base_ref=None, release_marker=None):
        return self.git.resolve_release_range(
            self.repository_path,
            head_ref,
            base_ref=base_ref,
            release_marker=release_marker,
        )

    def commits_in_range(self, release_range):
        return self.git.commits_in_range(self.repository_path, release_range)


def filter_commits(commits, approved_emails, module_tags):
    modules = ModulePolicy(
        tuple(
            ModuleDefinition(name, tuple(tags), name)
            for name, tags in module_tags.items()
        )
    )
    return CommitSelectionService().select(
        commits, ContributorPolicy(tuple(approved_emails)), modules
    )


def export_release_pdf(document, destination):
    return ReportLabPDFExporter().export(document, destination)


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

    def test_commit_list_linux_workflow_is_exact_and_has_no_diff_or_ai_artifacts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            runtime_path = _temporary_commit_list_runtime_config(
                temp_root,
                repository_path=self.linux_repository,
            )
            runtime_config = load_runtime_config(runtime_path)
            accepted_commits = tuple(_accepted_linux_commits(runtime_config))
            documents = []
            original_export = ReportLabPDFExporter.export

            def recording_export(exporter, document, destination):
                documents.append(document)
                return original_export(exporter, document, destination)

            fixture_before = snapshot_linux_fixture(self.linux_repository)
            with patch.object(
                ReportLabPDFExporter,
                "export",
                new=recording_export,
            ):
                result = ReleaseNotesRunner().run(runtime_path)
            fixture_after = snapshot_linux_fixture(self.linux_repository)

            self.assertEqual(result, 0)
            self.assertEqual(fixture_after, fixture_before)
            self.assertIs(runtime_config.report_mode, ReportMode.COMMIT_LIST)
            self.assertIsNone(runtime_config.ai)
            self.assertIsNone(runtime_config.env_file_path)
            self.assertIsNone(runtime_config.temp_diff_dir)
            self.assertEqual(runtime_config.output_path.read_bytes()[:5], b"%PDF-")
            self.assertFalse((temp_root / "analysis").exists())

            self.assertEqual(len(accepted_commits), 368)
            self.assertEqual(
                {commit.author_email for commit in accepted_commits},
                set(load_user_config(runtime_config.user_config_path).approved_author_emails),
            )
            self.assertEqual(
                {
                    module_name: sum(
                        commit.module_name == module_name
                        for commit in accepted_commits
                    )
                    for module_name in EXPECTED_MODULES
                },
                EXPECTED_MODULE_COUNTS,
            )

            self.assertEqual(len(documents), 1)
            document = documents[0]
            self.assertEqual(document.title, "Release Commit Report")
            self.assertEqual(document.repository_name, "linux")
            self.assertEqual(document.qualifying_change_count, 368)
            self.assertEqual(
                tuple(section.title for section in document.sections),
                EXPECTED_SECTIONS,
            )
            rendered_modules = tuple(
                module
                for section in document.sections
                for module in section.modules
            )
            self.assertEqual(
                tuple(module.name for module in rendered_modules),
                EXPECTED_MODULES,
            )
            for module in rendered_modules:
                expected_entries = tuple(
                    (commit.subject, commit.commit_hash)
                    for commit in accepted_commits
                    if commit.module_name == module.name
                )
                self.assertEqual(module.qualifying_change_count, len(expected_entries))
                self.assertEqual(
                    tuple(
                        (entry.subject, entry.commit_hash)
                        for entry in module.commits
                    ),
                    expected_entries,
                )
                self.assertTrue(
                    all(len(entry.commit_hash) == 40 for entry in module.commits)
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
            original_export = ReportLabPDFExporter.export

            def recording_export(document, destination) -> None:
                documents.append(document)
                original_export(ReportLabPDFExporter(), document, destination)

            with patch(
                "release_notes_generator.infrastructure.reportlab_pdf.ReportLabPDFExporter.export",
                side_effect=recording_export,
            ):
                result = ReleaseNotesRunner(
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

    def test_fake_claude_real_process_linux_workflow_is_bounded_and_isolated(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            claude_ai_path = CONFIG_DIR / "aiClaudeCodeIT.json"
            runtime_path = _temporary_runtime_config(
                temp_root,
                repository_path=self.linux_repository,
                overrides={"ai_config_path": str(claude_ai_path)},
            )
            runtime_config = load_runtime_config(runtime_path)
            ai_config = load_ai_config(claude_ai_path)
            accepted_commits = list(_accepted_linux_commits(runtime_config))
            request_trace: list[dict[str, object]] = []
            outcomes = []
            original_summarize = ClaudeCodeClient.summarize
            original_reduce = ClaudeCodeClient.reduce
            original_outcome = SummarizationService.summarize

            def recording_summarize(client, module_name, diff_content):
                request_trace.append(
                    _sanitized_request_trace("summarize", module_name, diff_content)
                )
                return original_summarize(client, module_name, diff_content)

            def recording_reduce(client, module_name, partial_summaries):
                request_trace.append(
                    _sanitized_request_trace("reduce", module_name, partial_summaries)
                )
                return original_reduce(client, module_name, partial_summaries)

            def recording_outcome(service, *args, **kwargs):
                outcome = original_outcome(service, *args, **kwargs)
                outcomes.append(outcome)
                return outcome

            fixture_before = snapshot_linux_fixture(self.linux_repository)
            with (
                installed_fake_claude(temp_root) as record_path,
                patch.dict(
                    os.environ,
                    {"CLAUDE_TEST_TOKEN": "FAKE-SENSITIVE-ENVIRONMENT-VALUE"},
                ),
                patch.object(
                    ClaudeCodeClient,
                    "summarize",
                    new=recording_summarize,
                ),
                patch.object(
                    ClaudeCodeClient,
                    "reduce",
                    new=recording_reduce,
                ),
                patch.object(
                    SummarizationService,
                    "summarize",
                    new=recording_outcome,
                ),
            ):
                result = ReleaseNotesRunner().run(runtime_path)

            records = load_fake_claude_records(record_path)
            fixture_after = snapshot_linux_fixture(self.linux_repository)

            self.assertEqual(result, 0)
            self.assertEqual(fixture_after, fixture_before)
            self.assertEqual(len(accepted_commits), 368)
            self.assertEqual(
                {
                    module_name: sum(
                        commit.module_name == module_name
                        for commit in accepted_commits
                    )
                    for module_name in EXPECTED_MODULES
                },
                EXPECTED_MODULE_COUNTS,
            )
            self.assertEqual(
                {commit.author_email for commit in accepted_commits},
                set(load_user_config(runtime_config.user_config_path).approved_author_emails),
            )

            self.assertTrue(
                any(entry["kind"] == "summarize" for entry in request_trace)
            )
            self.assertTrue(any(entry["kind"] == "reduce" for entry in request_trace))
            requested_modules = tuple(
                dict.fromkeys(entry["module"] for entry in request_trace)
            )
            self.assertEqual(set(requested_modules), set(EXPECTED_MODULES))
            self.assertEqual(len(requested_modules), len(EXPECTED_MODULES))
            self.assertTrue(
                all(
                    entry["content_size"]
                    <= ai_config.max_diff_characters_per_request
                    for entry in request_trace
                )
            )
            for module_name in EXPECTED_MODULES:
                module_kinds = [
                    entry["kind"]
                    for entry in request_trace
                    if entry["module"] == module_name
                ]
                if "reduce" in module_kinds:
                    first_reduce = module_kinds.index("reduce")
                    self.assertNotIn("summarize", module_kinds[first_reduce:])

            self.assertEqual(records[0]["argument_names"], ["--version"])
            request_records = records[1:]
            self.assertEqual(len(request_records), len(request_trace))
            self.assertEqual(
                [record["payload_sha256"] for record in request_records],
                [entry["stdin_sha256"] for entry in request_trace],
            )
            self.assertEqual(
                len({record["process_id"] for record in records}),
                len(records),
            )
            self.assertTrue(
                all(record["working_directory"]["is_empty"] for record in records)
            )
            self.assertTrue(
                all(
                    not record["working_directory"]["contains_git_entry"]
                    for record in records
                )
            )

            self.assertEqual(len(outcomes), 1)
            provenance = outcomes[0].provenance
            self.assertEqual(
                provenance,
                SummarizationProvenance(
                    backend="claude_code",
                    model=ai_config.model,
                    claude_code_version="2.1.251",
                ),
            )
            self.assertEqual(
                {field.name for field in dataclasses.fields(provenance)},
                {"backend", "model", "claude_code_version"},
            )
            sanitized_artifacts = record_path.read_text(encoding="utf-8") + json.dumps(
                dataclasses.asdict(provenance), sort_keys=True
            )
            self.assertNotIn("FAKE-SENSITIVE-ENVIRONMENT-VALUE", sanitized_artifacts)
            for forbidden_name in (
                "api_key",
                "oauth",
                "authorization",
                "credential",
                "environment",
            ):
                self.assertNotIn(forbidden_name, sanitized_artifacts.lower())

            self.assertEqual(runtime_config.output_path.read_bytes()[:5], b"%PDF-")
            self.assertEqual(tuple(runtime_config.temp_diff_dir.glob("diff_*.md")), ())

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
                    "release_notes_generator.infrastructure.git.GitAdapter.commits_in_range",
                    side_effect=GitHistoryError("forced extraction failure"),
                ),
                self.assertRaisesRegex(GitHistoryError, "forced extraction failure"),
            ):
                ReleaseNotesRunner(
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

            ReleaseNotesRunner(
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
                "release_notes_generator.infrastructure.git.subprocess.run",
                wraps=subprocess.run,
            ) as run:
                result = ReleaseNotesRunner(
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


def _temporary_commit_list_runtime_config(
    temp_root: Path,
    *,
    repository_path: Path,
) -> Path:
    committed = load_runtime_config(WORKFLOW_LINUX_COMMIT_LIST_IT_CONFIG_PATH)
    runtime_data = json.loads(
        WORKFLOW_LINUX_COMMIT_LIST_IT_CONFIG_PATH.read_text(encoding="utf-8")
    )
    if committed.release_marker_config_path is None:
        raise AssertionError("Linux commit-list JSON must select marker mode.")
    runtime_data.update(
        {
            "repository_path": str(repository_path),
            "user_config_path": str(committed.user_config_path),
            "module_config_path": str(committed.module_config_path),
            "release_marker_config_path": str(committed.release_marker_config_path),
            "output_path": str(temp_root / "output" / "commit_report.pdf"),
        }
    )
    runtime_config_path = temp_root / "workflowLinuxCommitListIT.json"
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


def _sanitized_request_trace(
    kind: str,
    module_name: str,
    content: str,
) -> dict[str, object]:
    boundary = "Diff" if kind == "summarize" else "Partial summaries"
    stdin_text = f"Module: {module_name}\n\n{boundary}:\n{content}"
    return {
        "kind": kind,
        "module": module_name,
        "content_size": len(content),
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "stdin_sha256": hashlib.sha256(stdin_text.encode("utf-8")).hexdigest(),
    }


if __name__ == "__main__":
    unittest.main()

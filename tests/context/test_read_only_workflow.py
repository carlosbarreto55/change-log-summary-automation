import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.domain.repository import (
    RepositoryStatus,
)
from release_notes_generator.services.errors import (
    AISummarizationError,
    DiffGenerationError,
    GitHistoryError,
    PDFGenerationError,
    RepositorySafetyError,
)
from tests.context.application import ReleaseNotesRunner
from tests.context.git_state import snapshot_git_state
from tests.context.workflow_fixture import (
    configure_resolvable_upstream,
    create_repository,
    run_git,
    write_runtime_configuration,
)


class RecordingSummaryClient:
    def __init__(self, failure: Exception = None) -> None:
        self.failure = failure
        self.calls: list[tuple[str, str]] = []

    def summarize(self, module_name: str, diff_content: str) -> str:
        self.calls.append((module_name, diff_content))
        if self.failure is not None:
            raise self.failure
        return f"- {module_name} summary"

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        return partial_summaries


class ReadOnlyWorkflowProofTests(unittest.TestCase):
    def test_default_mode_preserves_dirty_checkout_and_ignores_local_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            (repository / "source.txt").write_text(
                "released\ncommitted feature\nunstaged local change\n",
                encoding="utf-8",
            )
            (repository / "staged.txt").write_text("staged local change\n", encoding="utf-8")
            run_git(repository, ["add", "staged.txt"])
            (repository / "untracked.txt").write_text(
                "untracked local change\n",
                encoding="utf-8",
            )
            runtime_path = write_runtime_configuration(root, repository)
            warnings: list[str] = []
            client = RecordingSummaryClient()
            before = snapshot_git_state(repository)

            result = ReleaseNotesRunner(
                summary_client=client,
                warning_handler=warnings.append,
            ).run(runtime_path)

            after = snapshot_git_state(repository)
            self.assertEqual(result, 0)
            self.assertEqual(after, before)
            self.assertTrue(any("dirty" in warning for warning in warnings))
            self.assertTrue(any("freshness is unknown" in warning for warning in warnings))
            payload = "\n".join(content for _, content in client.calls)
            self.assertNotIn("unstaged local change", payload)
            self.assertNotIn("staged local change", payload)
            self.assertNotIn("untracked local change", payload)
            self.assertEqual(tuple((root / "analysis" / "diffs").glob("diff_*.md")), ())
            self.assertEqual((root / "analysis" / "release.pdf").read_bytes()[:5], b"%PDF-")

    def test_explicit_analysis_head_can_differ_from_checkout_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, analysis_sha = create_repository(root)
            run_git(repository, ["branch", "analysis", analysis_sha])
            (repository / "checkout.txt").write_text("checkout only\n", encoding="utf-8")
            run_git(repository, ["add", "checkout.txt"])
            run_git(repository, ["commit", "--quiet", "-m", "Pix: checkout only"])
            runtime_path = write_runtime_configuration(
                root,
                repository,
                head_ref="refs/heads/analysis",
            )
            warnings: list[str] = []
            client = RecordingSummaryClient()
            before = snapshot_git_state(repository)

            ReleaseNotesRunner(
                summary_client=client,
                warning_handler=warnings.append,
            ).run(runtime_path)

            self.assertEqual(snapshot_git_state(repository), before)
            self.assertTrue(any("differs from analysis head" in warning for warning in warnings))
            self.assertNotIn(
                "checkout only",
                "\n".join(content for _, content in client.calls),
            )

    def test_default_mode_failures_preserve_exact_repository_state(self) -> None:
        cases = (
            ("boundary", GitHistoryError, None),
            ("commit", GitHistoryError, "commits"),
            ("diff", DiffGenerationError, "diff"),
            ("ai", AISummarizationError, "ai"),
            ("pdf", PDFGenerationError, "pdf"),
        )
        for name, error_type, stage in cases:
            with self.subTest(stage=name), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                repository, _, _ = create_repository(root)
                runtime_path = write_runtime_configuration(
                    root,
                    repository,
                    head_ref="refs/heads/missing" if stage is None else "refs/heads/main",
                )
                before = snapshot_git_state(repository)
                client = RecordingSummaryClient(
                    AISummarizationError("AI failed") if stage == "ai" else None
                )

                patches = []
                if stage == "commits":
                    patches.append(
                        patch(
                            "release_notes_generator.infrastructure.git.GitAdapter.commits_in_range",
                            side_effect=GitHistoryError("commit extraction failed"),
                        )
                    )
                elif stage == "diff":
                    patches.append(
                        patch(
                            "release_notes_generator.services.diff_generation.DiffGenerationService.generate",
                            side_effect=DiffGenerationError("diff failed"),
                        )
                    )
                elif stage == "pdf":
                    patches.append(
                        patch(
                            "release_notes_generator.infrastructure.reportlab_pdf.ReportLabPDFExporter.export",
                            side_effect=PDFGenerationError("PDF failed"),
                        )
                    )

                with ExitStack() as stack:
                    for active_patch in patches:
                        stack.enter_context(active_patch)
                    with self.assertRaises(error_type):
                        ReleaseNotesRunner(summary_client=client).run(runtime_path)

                self.assertEqual(snapshot_git_state(repository), before)
                self.assertFalse((root / "analysis" / "release.pdf").exists())
                self.assertEqual(
                    tuple((root / "analysis" / "diffs").glob("diff_*.md")),
                    (),
                )

    def test_internal_paths_are_rejected_before_downstream_work(self) -> None:
        temp_modes = (
            ("read_only", None, ()),
            (
                "refresh_remote_refs",
                "origin",
                ("refs/heads/main:refs/remotes/origin/main",),
            ),
            ("legacy_in_place_sync", None, ()),
        )
        for mode, remote, refspecs in temp_modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                repository, _, _ = create_repository(root)
                runtime_path = write_runtime_configuration(
                    root,
                    repository,
                    update_mode=mode,
                    refresh_remote=remote,
                    refresh_refspecs=refspecs,
                    temp_diff_dir=repository / "tmp" / "diffs",
                )
                before = snapshot_git_state(repository)

                with (
                    patch("release_notes_generator.infrastructure.git.GitAdapter.update") as update,
                    patch("release_notes_generator.services.diff_generation.DiffGenerationService.generate") as generate,
                    patch("release_notes_generator.infrastructure.reportlab_pdf.ReportLabPDFExporter.export") as export,
                    self.assertRaises(RepositorySafetyError),
                ):
                    ReleaseNotesRunner(
                        summary_client=RecordingSummaryClient()
                    ).run(runtime_path)

                update.assert_not_called()
                generate.assert_not_called()
                export.assert_not_called()
                self.assertEqual(snapshot_git_state(repository), before)
                self.assertFalse((repository / "tmp").exists())

        for mode in ("read_only", "refresh_remote_refs"):
            with self.subTest(output_mode=mode), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                repository, _, _ = create_repository(root)
                runtime_path = write_runtime_configuration(
                    root,
                    repository,
                    update_mode=mode,
                    refresh_remote="origin" if mode == "refresh_remote_refs" else None,
                    refresh_refspecs=(
                        ("refs/heads/main:refs/remotes/origin/main",)
                        if mode == "refresh_remote_refs"
                        else ()
                    ),
                    output_path=repository / "release.pdf",
                )
                before = snapshot_git_state(repository)

                with (
                    patch("release_notes_generator.infrastructure.git.GitAdapter.update") as update,
                    self.assertRaises(RepositorySafetyError),
                ):
                    ReleaseNotesRunner(
                        summary_client=RecordingSummaryClient()
                    ).run(runtime_path)

                update.assert_not_called()
                self.assertEqual(snapshot_git_state(repository), before)
                self.assertFalse((repository / "release.pdf").exists())

    def test_refresh_failure_stops_all_downstream_work_and_preserves_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            runtime_path = write_runtime_configuration(
                root,
                repository,
                update_mode="refresh_remote_refs",
                refresh_remote="missing",
                refresh_refspecs=(
                    "refs/heads/main:refs/remotes/missing/main",
                ),
            )
            before = snapshot_git_state(repository)

            with (
                patch("release_notes_generator.infrastructure.git.GitAdapter.resolve_release_range") as extractor,
                patch("release_notes_generator.services.diff_generation.DiffGenerationService.generate") as generate,
                patch(
                    "release_notes_generator.services.summarization."
                    "SummarizationService.summarize"
                ) as summarize,
                patch("release_notes_generator.infrastructure.reportlab_pdf.ReportLabPDFExporter.export") as export,
                self.assertRaises(GitHistoryError),
            ):
                ReleaseNotesRunner(
                    summary_client=RecordingSummaryClient()
                ).run(runtime_path)

            extractor.assert_not_called()
            generate.assert_not_called()
            summarize.assert_not_called()
            export.assert_not_called()
            self.assertEqual(snapshot_git_state(repository), before)
            self.assertFalse((root / "analysis").exists())

    def test_rejected_legacy_guards_preserve_exact_repository_state(self) -> None:
        cases = ("staged", "unstaged", "untracked", "detached", "no-upstream", "bad-upstream")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                repository, _, _ = create_repository(root)
                if case in {"staged", "unstaged", "untracked"}:
                    configure_resolvable_upstream(repository)
                if case == "staged":
                    (repository / "staged.txt").write_text("staged\n", encoding="utf-8")
                    run_git(repository, ["add", "staged.txt"])
                elif case == "unstaged":
                    (repository / "source.txt").write_text(
                        "released\ncommitted feature\nunstaged\n",
                        encoding="utf-8",
                    )
                elif case == "untracked":
                    (repository / "untracked.txt").write_text("untracked\n", encoding="utf-8")
                elif case == "detached":
                    run_git(repository, ["checkout", "--quiet", "--detach", "HEAD"])
                elif case == "bad-upstream":
                    run_git(repository, ["remote", "add", "origin", str(repository)])
                    run_git(repository, ["config", "branch.main.remote", "origin"])
                    run_git(repository, ["config", "branch.main.merge", "refs/heads/missing"])

                runtime_path = write_runtime_configuration(
                    root,
                    repository,
                    update_mode="legacy_in_place_sync",
                )
                before = snapshot_git_state(repository)

                with self.assertRaises(GitHistoryError):
                    ReleaseNotesRunner(
                        summary_client=RecordingSummaryClient()
                    ).run(runtime_path)

                self.assertEqual(snapshot_git_state(repository), before)
                self.assertFalse((root / "analysis").exists())

    def test_explicit_refresh_changes_only_named_tracking_ref_and_objects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            remote = root / "remote.git"
            run_git(root, ["init", "--quiet", "--bare", str(remote)])
            run_git(repository, ["remote", "add", "origin", str(remote)])
            run_git(repository, ["push", "--quiet", "-u", "origin", "main"])

            publisher = root / "publisher"
            run_git(root, ["clone", "--quiet", str(remote), str(publisher)])
            run_git(publisher, ["config", "user.name", "Publisher"])
            run_git(publisher, ["config", "user.email", "dev@example.com"])
            (publisher / "remote.txt").write_text("remote feature\n", encoding="utf-8")
            run_git(publisher, ["add", "remote.txt"])
            run_git(publisher, ["commit", "--quiet", "-m", "Pix: remote feature"])
            run_git(publisher, ["push", "--quiet", "origin", "main"])

            runtime_path = write_runtime_configuration(
                root,
                repository,
                head_ref="refs/remotes/origin/main",
                update_mode="refresh_remote_refs",
                refresh_remote="origin",
                refresh_refspecs=(
                    "refs/heads/main:refs/remotes/origin/main",
                ),
            )
            before = snapshot_git_state(repository)
            warnings: list[str] = []

            ReleaseNotesRunner(
                summary_client=RecordingSummaryClient(),
                warning_handler=warnings.append,
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
            self.assertEqual(
                tuple(
                    line
                    for line in after.porcelain_status.splitlines()
                    if not line.startswith("# ")
                ),
                tuple(
                    line
                    for line in before.porcelain_status.splitlines()
                    if not line.startswith("# ")
                ),
            )
            self.assertEqual(after.operation_state, before.operation_state)
            self.assertEqual(after.worktree_inventory, before.worktree_inventory)
            before_refs = dict(before.refs)
            after_refs = dict(after.refs)
            self.assertNotEqual(
                after_refs["refs/remotes/origin/main"],
                before_refs["refs/remotes/origin/main"],
            )
            self.assertTrue(
                any("refs/remotes/origin/main" in warning for warning in warnings)
            )

    def test_every_preflight_condition_is_emitted_as_a_workflow_warning(self) -> None:
        conditions = (
            "dirty",
            "detached",
            "ahead",
            "behind",
            "diverged",
            "relationship is unknown",
            "freshness is unknown",
        )
        for condition in conditions:
            with self.subTest(condition=condition), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                repository, _, _ = create_repository(root)
                runtime_path = write_runtime_configuration(root, repository)
                status = RepositoryStatus(
                    staged_count=0,
                    unstaged_count=0,
                    untracked_count=0,
                    branch="main",
                    upstream="origin/main",
                    upstream_resolved=True,
                    relation="equal",
                    ahead_count=0,
                    behind_count=0,
                    checkout_head_sha="checkout",
                    warnings=(f"Repository condition: {condition}.",),
                )
                warnings: list[str] = []

                with (
                    patch(
                        "release_notes_generator.infrastructure.git.GitAdapter.inspect",
                        return_value=status,
                    ),
                    patch(
                        "release_notes_generator.infrastructure.git.GitAdapter.update",
                        return_value=status,
                    ),
                ):
                    ReleaseNotesRunner(
                        summary_client=RecordingSummaryClient(),
                        warning_handler=warnings.append,
                    ).run(runtime_path)

                self.assertTrue(any(condition in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import subprocess
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.domain.configuration import (
    ContributorPolicy,
    ModuleDefinition,
    ModulePolicy,
)
from release_notes_generator.domain.repository import (
    ClassifiedCommit,
    Commit as GitCommit,
    ReleaseRange,
    RepositoryStatus,
)
from release_notes_generator.infrastructure.artifacts import LocalArtifactStore
from release_notes_generator.infrastructure.git import (
    GitAdapter,
    _GitCommitExtractor as GitCommitExtractor,
    inspect_repository,
    update_repository,
)
from release_notes_generator.services.commit_selection import CommitSelectionService
from release_notes_generator.services.diff_generation import DiffGenerationService
from release_notes_generator.services.errors import DiffGenerationError, GitHistoryError


TEST_TIMESTAMP = datetime(2026, 1, 3, 12, 30, tzinfo=timezone.utc)


def filter_commits(commits, approved_author_emails, module_tags):
    policy = ModulePolicy(
        tuple(
            ModuleDefinition(module_name, tuple(tags), module_name)
            for module_name, tags in module_tags.items()
        )
    )
    return CommitSelectionService().select(
        commits, ContributorPolicy(tuple(approved_author_emails)), policy
    )


def group_commit_hashes_by_module(commits):
    return CommitSelectionService().group(commits)


def generate_diff_files(repository_path, grouped_commit_hashes, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = DiffGenerationService(
        GitAdapter(), LocalArtifactStore()
    ).generate(repository_path, grouped_commit_hashes, output_dir)
    return {artifact.module_name: artifact.path for artifact in artifacts}


def _git_result(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _status(**overrides: object) -> RepositoryStatus:
    values: dict[str, object] = {
        "staged_count": 0,
        "unstaged_count": 0,
        "untracked_count": 0,
        "branch": "main",
        "upstream": "origin/main",
        "upstream_resolved": True,
        "relation": "equal",
        "ahead_count": 0,
        "behind_count": 0,
        "checkout_head_sha": "checkout-sha",
    }
    values.update(overrides)
    return RepositoryStatus(**values)


class RepositoryInspectionTests(unittest.TestCase):
    def test_repository_status_is_immutable_and_reports_clean_state(self) -> None:
        status, calls = self._inspect()

        self.assertFalse(status.is_dirty)
        self.assertEqual(status.staged_count, 0)
        self.assertEqual(status.unstaged_count, 0)
        self.assertEqual(status.untracked_count, 0)
        self.assertEqual(status.branch, "main")
        self.assertEqual(status.upstream, "origin/main")
        self.assertTrue(status.upstream_resolved)
        self.assertEqual(status.relation, "equal")
        self.assertEqual(status.ahead_count, 0)
        self.assertEqual(status.behind_count, 0)
        self.assertEqual(status.checkout_head_sha, "checkout-sha")
        self.assertEqual(status.freshness_for("refs/remotes/origin/main"), "unknown")
        self.assertTrue(any("freshness is unknown" in warning for warning in status.warnings))
        with self.assertRaises(FrozenInstanceError):
            status.branch = "other"  # type: ignore[misc]

        self.assertEqual(len(calls), 4)

    def test_counts_staged_unstaged_untracked_and_combined_dirty_states(self) -> None:
        cases = (
            ("1 M. N... 100644 100644 100644 a a staged.txt\n", (1, 0, 0)),
            ("1 .M N... 100644 100644 100644 a a unstaged.txt\n", (0, 1, 0)),
            ("? untracked.txt\n", (0, 0, 1)),
            (
                "1 MM N... 100644 100644 100644 a a both.txt\n"
                "? untracked.txt\n",
                (1, 1, 1),
            ),
        )

        for worktree_lines, expected_counts in cases:
            with self.subTest(expected_counts=expected_counts):
                status, _ = self._inspect(status_lines=worktree_lines)
                self.assertTrue(status.is_dirty)
                self.assertEqual(
                    (
                        status.staged_count,
                        status.unstaged_count,
                        status.untracked_count,
                    ),
                    expected_counts,
                )
                self.assertTrue(any("dirty" in warning for warning in status.warnings))

    def test_attached_checkout_warning_distinguishes_analysis_head(self) -> None:
        status, _ = self._inspect(analysis_head_ref="refs/remotes/origin/release")

        self.assertEqual(status.branch, "main")
        self.assertTrue(
            any(
                "main" in warning and "refs/remotes/origin/release" in warning
                for warning in status.warnings
            )
        )

    def test_detached_checkout_is_diagnostic_not_an_inspection_error(self) -> None:
        status_output = "# branch.oid detached-sha\n# branch.head (detached)\n"
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result(status_output),
                _git_result(stderr="not a symbolic ref", returncode=1),
            ]

            status = inspect_repository(
                Path("/repo"), analysis_head_ref="refs/remotes/origin/release"
            )

        self.assertIsNone(status.branch)
        self.assertIsNone(status.upstream)
        self.assertEqual(status.relation, "unknown")
        self.assertTrue(any("detached" in warning for warning in status.warnings))
        self.assertTrue(
            any("refs/remotes/origin/release" in warning for warning in status.warnings)
        )

    def test_classifies_upstream_relationship_from_left_and_right_counts(self) -> None:
        cases = {
            "0\t0\n": ("equal", 0, 0),
            "2\t0\n": ("ahead", 2, 0),
            "0\t3\n": ("behind", 0, 3),
            "2\t3\n": ("diverged", 2, 3),
        }

        for comparison_output, expected in cases.items():
            with self.subTest(expected=expected):
                status, _ = self._inspect(comparison_output=comparison_output)
                self.assertEqual(
                    (status.relation, status.ahead_count, status.behind_count),
                    expected,
                )
                if status.relation != "equal":
                    self.assertTrue(
                        any(status.relation in warning for warning in status.warnings)
                    )

    def test_warns_without_guessing_when_upstream_is_absent(self) -> None:
        status_output = "# branch.oid checkout-sha\n# branch.head main\n"
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result(status_output),
                _git_result("main\n"),
                _git_result(stderr="no upstream configured", returncode=1),
            ]

            status = inspect_repository(Path("/repo"))

        self.assertIsNone(status.upstream)
        self.assertFalse(status.upstream_resolved)
        self.assertEqual(status.relation, "unknown")
        self.assertTrue(any("no configured upstream" in warning for warning in status.warnings))

    def test_warns_when_configured_upstream_tracking_ref_is_missing(self) -> None:
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result(self._status_output()),
                _git_result("main\n"),
                _git_result(stderr="unknown revision", returncode=1),
            ]

            status = inspect_repository(Path("/repo"))

        self.assertEqual(status.upstream, "origin/main")
        self.assertFalse(status.upstream_resolved)
        self.assertEqual(status.relation, "unknown")
        self.assertTrue(any("cannot be resolved" in warning for warning in status.warnings))

    def test_warns_when_upstream_comparison_fails(self) -> None:
        status, _ = self._inspect(
            comparison_result=_git_result(stderr="comparison failed", returncode=1)
        )

        self.assertEqual(status.upstream, "origin/main")
        self.assertTrue(status.upstream_resolved)
        self.assertEqual(status.relation, "unknown")
        self.assertIsNone(status.ahead_count)
        self.assertIsNone(status.behind_count)
        self.assertTrue(any("could not be compared" in warning for warning in status.warnings))

    def test_every_inspection_command_disables_optional_git_locks(self) -> None:
        _, calls = self._inspect()

        for call in calls:
            self.assertEqual(call.kwargs["env"]["GIT_OPTIONAL_LOCKS"], "0")

    def _inspect(
        self,
        *,
        status_lines: str = "",
        comparison_output: str = "0\t0\n",
        comparison_result: subprocess.CompletedProcess[str] | None = None,
        analysis_head_ref: str | None = None,
    ) -> tuple[RepositoryStatus, list[object]]:
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result(self._status_output(status_lines)),
                _git_result("main\n"),
                _git_result("origin/main\n"),
                comparison_result or _git_result(comparison_output),
            ]

            status = inspect_repository(
                Path("/repo"), analysis_head_ref=analysis_head_ref
            )

        return status, run.call_args_list

    @staticmethod
    def _status_output(status_lines: str = "") -> str:
        return (
            "# branch.oid checkout-sha\n"
            "# branch.head main\n"
            "# branch.upstream origin/main\n"
            f"{status_lines}"
        )


class FrozenReleaseRangeTests(unittest.TestCase):
    def test_explicit_refs_resolve_once_and_commits_use_only_frozen_shas(self) -> None:
        head_sha = "a" * 64
        base_sha = "b" * 64
        extractor = GitCommitExtractor(Path("/repo"))
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result(f"{head_sha}\n"),
                _git_result(f"{base_sha}\n"),
                _git_result(
                    "commit-object-id\x1fdev@example.com\x1f"
                    "2026-01-03T12:30:00+00:00\x1fPix: frozen\n"
                ),
            ]

            release_range = extractor.resolve_release_range(
                "refs/heads/release", base_ref="refs/tags/v1"
            )
            commits = extractor.commits_in_range(release_range)

        self.assertEqual(release_range, ReleaseRange(base_sha, head_sha))
        self.assertEqual(commits[0].commit_hash, "commit-object-id")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(
            commands[0][-4:],
            ["rev-parse", "--verify", "--end-of-options", "refs/heads/release^{commit}"],
        )
        self.assertEqual(
            commands[1][-4:],
            ["rev-parse", "--verify", "--end-of-options", "refs/tags/v1^{commit}"],
        )
        self.assertEqual(commands[2][-2:], [f"{base_sha}..{head_sha}", "--"])
        self.assertNotIn("HEAD", commands[2])

    def test_marker_lookup_is_bounded_to_frozen_head_and_uses_newest_subject_match(self) -> None:
        head_sha = "frozen-head-object-id"
        extractor = GitCommitExtractor(Path("/repo"))
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result(f"{head_sha}\n"),
                _git_result(
                    "body-only\x1fFeature after release\n"
                    "newest-marker\x1f[Release] 2.0\n"
                    "older-marker\x1f[Release] 1.0\n"
                ),
            ]

            release_range = extractor.resolve_release_range(
                "refs/remotes/origin/release", release_marker="[Release]"
            )

        self.assertEqual(release_range, ReleaseRange("newest-marker", head_sha))
        marker_command = run.call_args_list[1].args[0]
        self.assertIn(head_sha, marker_command)
        self.assertNotIn("HEAD", marker_command)
        self.assertEqual(marker_command[-1], "--")

    def test_read_commands_for_resolution_marker_and_commit_log_disable_locks(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result("head-object-id\n"),
                _git_result("marker-object-id\x1f[Release] 1.0\n"),
                _git_result(""),
            ]

            release_range = extractor.resolve_release_range(
                "release", release_marker="[Release]"
            )
            extractor.commits_in_range(release_range)

        for call in run.call_args_list:
            self.assertEqual(call.kwargs["env"]["GIT_OPTIONAL_LOCKS"], "0")

    def test_unresolved_head_stops_before_lower_boundary_or_commit_log(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result(stderr="bad head", returncode=1)

            with self.assertRaisesRegex(GitHistoryError, "head ref.*missing-head"):
                extractor.resolve_release_range("missing-head", base_ref="base")

        self.assertEqual(run.call_count, 1)

    def test_unresolved_base_stops_before_commit_log(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result("head-object-id\n"),
                _git_result(stderr="bad base", returncode=1),
            ]

            with self.assertRaisesRegex(GitHistoryError, "base ref.*missing-base"):
                extractor.resolve_release_range("head", base_ref="missing-base")

        self.assertEqual(run.call_count, 2)

    def test_missing_reachable_marker_stops_before_commit_extraction(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result("head-object-id\n"),
                _git_result("body-only\x1fFeature subject\n"),
            ]

            with self.assertRaisesRegex(GitHistoryError, "No release marker.*Release"):
                extractor.resolve_release_range("head", release_marker="[Release]")

        self.assertEqual(run.call_count, 2)

    def test_moving_configured_ref_does_not_change_frozen_commits_or_diffs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository = root / "repository"
            repository.mkdir()
            subprocess.run(
                ["git", "-C", str(repository), "init", "--quiet", "--initial-branch=main"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.name", "Test"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.email", "dev@example.com"],
                check=True,
            )
            source = repository / "source.txt"
            source.write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "source.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "--quiet", "-m", "base"],
                check=True,
            )
            base_sha = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            source.write_text("base\nfrozen\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "source.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "--quiet", "-m", "Pix: frozen"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "branch", "analysis", "HEAD"],
                check=True,
            )

            extractor = GitCommitExtractor(repository)
            release_range = extractor.resolve_release_range(
                "refs/heads/analysis",
                base_ref=base_sha,
            )

            source.write_text("base\nfrozen\nmoved\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "source.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "commit", "--quiet", "-m", "Pix: moved"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "branch", "--force", "analysis", "HEAD"],
                check=True,
            )

            commits = extractor.commits_in_range(release_range)
            diff_files = generate_diff_files(
                repository,
                {"Pix": tuple(commit.commit_hash for commit in commits)},
                root / "diffs",
            )
            diff_content = diff_files["Pix"].read_text(encoding="utf-8")

        self.assertEqual(tuple(commit.subject for commit in commits), ("Pix: frozen",))
        self.assertIn("frozen", diff_content)
        self.assertNotIn("Pix: moved", diff_content)

    def test_release_range_is_immutable(self) -> None:
        release_range = ReleaseRange("base", "head")

        with self.assertRaises(FrozenInstanceError):
            release_range.head_sha = "moved"  # type: ignore[misc]

    def test_returns_no_commits_for_an_empty_frozen_range_log(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result("")

            commits = extractor.commits_in_range(ReleaseRange("base", "head"))

        self.assertEqual(commits, ())

    def test_raises_when_frozen_range_commit_timestamp_is_malformed(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result(
                "a1\x1fdev@example.com\x1fnot-a-timestamp\x1fPix: change\n"
            )

            with self.assertRaisesRegex(
                GitHistoryError, "Unexpected Git author timestamp"
            ):
                extractor.commits_in_range(ReleaseRange("base", "head"))


class RepositoryUpdateModeTests(unittest.TestCase):
    def test_read_only_mode_runs_no_mutation_and_keeps_freshness_unknown(self) -> None:
        status = _status(warnings=())
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            updated = update_repository(Path("/repo"), "read_only", status=status)

        run.assert_not_called()
        self.assertEqual(updated.freshness_for("refs/remotes/origin/main"), "unknown")
        self.assertTrue(any("freshness is unknown" in warning for warning in updated.warnings))

    def test_refresh_fetches_only_exact_remote_and_refspecs_before_resolution(self) -> None:
        refspecs = (
            "+refs/heads/main:refs/remotes/origin/main",
            "refs/heads/release:refs/remotes/origin/release",
        )
        extractor = GitCommitExtractor(Path("/repo"))
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result(),
                _git_result("head-sha\n"),
                _git_result("base-sha\n"),
            ]

            updated = update_repository(
                Path("/repo"),
                "refresh_remote_refs",
                status=_status(),
                remote="origin",
                refspecs=refspecs,
            )
            release_range = extractor.resolve_release_range("origin/main", base_ref="v1")

        commands = [call.args[0] for call in run.call_args_list]
        # Normalize path separators for cross-platform comparison
        self.assertEqual(len(commands[0]), 9)
        self.assertEqual(commands[0][0], "git")
        self.assertEqual(commands[0][1], "-C")
        # Path is platform-specific, just check it ends with "repo"
        self.assertTrue(commands[0][2].endswith("repo"))
        self.assertEqual(commands[0][3:], [
            "fetch",
            "--no-tags",
            "--no-write-fetch-head",
            "origin",
            *refspecs,
        ])
        self.assertNotIn("env", run.call_args_list[0].kwargs)
        self.assertEqual(release_range, ReleaseRange("base-sha", "head-sha"))
        self.assertEqual(
            updated.refreshed_refs,
            ("refs/remotes/origin/main", "refs/remotes/origin/release"),
        )

    def test_refresh_marks_only_named_destinations_fresh_as_of_fetch(self) -> None:
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result()
            updated = update_repository(
                Path("/repo"),
                "refresh_remote_refs",
                status=_status(),
                remote="origin",
                refspecs=("refs/heads/main:refs/remotes/origin/main",),
            )

        self.assertEqual(
            updated.freshness_for("refs/remotes/origin/main"), "fresh_as_of_fetch"
        )
        self.assertEqual(
            updated.freshness_for("refs/remotes/origin/release"), "unknown"
        )
        self.assertIsNotNone(updated.freshness_checked_at)

    def test_refresh_failure_raises_before_any_boundary_resolution(self) -> None:
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result(stderr="network failed", returncode=1)

            with self.assertRaises(GitHistoryError) as error:
                update_repository(
                    Path("/repo"),
                    "refresh_remote_refs",
                    status=_status(),
                    remote="origin",
                    refspecs=("refs/heads/main:refs/remotes/origin/main",),
                )

        self.assertIn("refresh", str(error.exception))
        self.assertIn("network failed", str(error.exception))
        self.assertEqual(run.call_count, 1)

    def test_refresh_rejects_destination_outside_named_remote_namespace(self) -> None:
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            with self.assertRaisesRegex(GitHistoryError, "remote-tracking namespace"):
                update_repository(
                    Path("/repo"),
                    "refresh_remote_refs",
                    status=_status(),
                    remote="origin",
                    refspecs=("refs/heads/main:refs/heads/main",),
                )

        run.assert_not_called()

    def test_legacy_guards_reject_dirty_detached_or_unresolvable_upstream(self) -> None:
        cases = (
            _status(staged_count=1),
            _status(unstaged_count=1),
            _status(untracked_count=1),
            _status(branch=None, upstream=None, upstream_resolved=False, relation="unknown"),
            _status(upstream=None, upstream_resolved=False, relation="unknown"),
            _status(upstream="origin/main", upstream_resolved=False, relation="unknown"),
        )

        for status in cases:
            with self.subTest(status=status):
                with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
                    with self.assertRaises(GitHistoryError):
                        update_repository(
                            Path("/repo"), "legacy_in_place_sync", status=status
                        )
                run.assert_not_called()

    def test_legacy_success_fetches_then_rebases_before_range_resolution(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result(),
                _git_result(),
                _git_result("head-sha\n"),
                _git_result("base-sha\n"),
            ]

            update_repository(Path("/repo"), "legacy_in_place_sync", status=_status())
            release_range = extractor.resolve_release_range("main", base_ref="v1")

        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][-2:], ["fetch", "--prune"])
        self.assertEqual(commands[1][-2:], ["rebase", "@{upstream}"])
        self.assertEqual(commands[2][-4:-1], ["rev-parse", "--verify", "--end-of-options"])
        self.assertEqual(release_range, ReleaseRange("base-sha", "head-sha"))

    def test_legacy_fetch_failure_skips_rebase(self) -> None:
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result(stderr="fetch failed", returncode=1)

            with self.assertRaises(GitHistoryError) as error:
                update_repository(
                    Path("/repo"), "legacy_in_place_sync", status=_status()
                )

        self.assertIn("during fetch", str(error.exception))
        self.assertIn("fetch failed", str(error.exception))
        self.assertEqual(run.call_count, 1)

    def test_legacy_rebase_failure_preserves_error_and_attempts_abort(self) -> None:
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result(),
                _git_result(stderr="rebase conflict", returncode=1),
                _git_result(),
            ]

            with self.assertRaises(GitHistoryError) as error:
                update_repository(
                    Path("/repo"), "legacy_in_place_sync", status=_status()
                )

        self.assertIn("rebase conflict", str(error.exception))
        self.assertIn("rebase was aborted", str(error.exception))
        self.assertEqual(run.call_args_list[2].args[0][-2:], ["rebase", "--abort"])

    def test_legacy_abort_failure_is_reported_separately(self) -> None:
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.side_effect = [
                _git_result(),
                _git_result(stderr="original rebase error", returncode=1),
                _git_result(stderr="abort also failed", returncode=1),
            ]

            with self.assertRaises(GitHistoryError) as error:
                update_repository(
                    Path("/repo"), "legacy_in_place_sync", status=_status()
                )

        message = str(error.exception)
        self.assertIn("original rebase error", message)
        self.assertIn("abort also failed", message)
        self.assertIn("manual recovery", message)


class CommitFilteringTests(unittest.TestCase):
    def test_unauthorized_authors_are_ignored(self) -> None:
        commits = (
            GitCommit("a1", "approved@example.com", "Pix: add payment", TEST_TIMESTAMP),
            GitCommit("b2", "unknown@example.com", "Pix: add refund", TEST_TIMESTAMP),
        )

        accepted = filter_commits(
            commits,
            approved_author_emails=("approved@example.com",),
            module_tags={"Pix": ("Pix",)},
        )

        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].commit_hash, "a1")

    def test_unmapped_modules_are_ignored(self) -> None:
        commits = (
            GitCommit("a1", "approved@example.com", "Pix: add payment", TEST_TIMESTAMP),
            GitCommit("b2", "approved@example.com", "Unknown: add feature", TEST_TIMESTAMP),
        )

        accepted = filter_commits(
            commits,
            approved_author_emails=("approved@example.com",),
            module_tags={"Pix": ("Pix",)},
        )

        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].commit_hash, "a1")

    def test_commit_message_prefixes_are_matched_against_module_tags(self) -> None:
        commits = (
            GitCommit("a1", "approved@example.com", "PIX-123 add payment", TEST_TIMESTAMP),
            GitCommit("b2", "approved@example.com", "GL-456 add rewards", TEST_TIMESTAMP),
        )

        accepted = filter_commits(
            commits,
            approved_author_emails=("approved@example.com",),
            module_tags={"Pix": ("PIX-",), "GlobalLoyalty": ("GL-",)},
        )

        self.assertEqual([commit.module_name for commit in accepted], ["Pix", "GlobalLoyalty"])

    def test_author_email_and_commit_prefix_matching_are_case_sensitive(self) -> None:
        commits = (
            GitCommit(
                "email-case", "Approved@example.com", "Pix: email case", TEST_TIMESTAMP
            ),
            GitCommit(
                "prefix-case", "approved@example.com", "pix: prefix case", TEST_TIMESTAMP
            ),
        )

        accepted = filter_commits(
            commits,
            approved_author_emails=("approved@example.com",),
            module_tags={"Pix": ("Pix:",)},
        )

        self.assertEqual(accepted, ())

    def test_first_configured_matching_module_wins(self) -> None:
        commits = (
            GitCommit("a1", "approved@example.com", "Feature: add payment", TEST_TIMESTAMP),
        )

        accepted = filter_commits(
            commits,
            approved_author_emails=("approved@example.com",),
            module_tags={"Broad": ("Feature",), "Specific": ("Feature:",)},
        )

        self.assertEqual(accepted[0].module_name, "Broad")

    def test_filter_returns_classified_commits_for_authorized_mapped_commits(self) -> None:
        commits = (
            GitCommit(
                "a1",
                "approved@example.com",
                "TransitOpenLoop: add fare",
                TEST_TIMESTAMP,
            ),
        )

        accepted = filter_commits(
            commits,
            approved_author_emails=("approved@example.com",),
            module_tags={"TransitOpenLoop": ("TransitOpenLoop",)},
        )

        self.assertEqual(accepted[0].commit_hash, "a1")
        self.assertEqual(accepted[0].author_email, "approved@example.com")
        self.assertEqual(accepted[0].subject, "TransitOpenLoop: add fare")
        self.assertEqual(accepted[0].module_name, "TransitOpenLoop")
        self.assertEqual(accepted[0].authored_at, TEST_TIMESTAMP)

    def test_grouping_uses_only_frozen_range_derived_commit_hashes(self) -> None:
        commits = (
            ClassifiedCommit(
                "frozen-a", "dev@example.com", "Pix: a", "Pix", TEST_TIMESTAMP
            ),
            ClassifiedCommit(
                "frozen-b", "dev@example.com", "Pix: b", "Pix", TEST_TIMESTAMP
            ),
        )

        grouped = group_commit_hashes_by_module(commits)

        self.assertEqual(grouped, {"Pix": ("frozen-a", "frozen-b")})
        self.assertNotIn("HEAD", grouped["Pix"])


class ChangedFilesTests(unittest.TestCase):
    """Tests for GitAdapter.changed_files method (task 3.3)."""

    def test_nul_separated_output_parses_to_expected_tuple(self) -> None:
        """Verify NUL-separated output parses to the expected tuple."""
        adapter = GitAdapter()
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result(
                stdout="file1.txt\x00file2.txt\x00dir/file3.txt\x00",
                returncode=0,
            )

            result = adapter.changed_files(Path("/repo"), "abc123")

        self.assertEqual(result, ("file1.txt", "file2.txt", "dir/file3.txt"))

    def test_empty_output_yields_empty_tuple(self) -> None:
        """Verify empty output yields an empty tuple."""
        adapter = GitAdapter()
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result(stdout="", returncode=0)

            result = adapter.changed_files(Path("/repo"), "abc123")

        self.assertEqual(result, ())

    def test_non_ascii_path_round_trips_unescaped(self) -> None:
        """Verify a non-ASCII path round-trips unescaped."""
        adapter = GitAdapter()
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            # Git returns NUL-separated UTF-8 paths
            run.return_value = _git_result(
                stdout="path/to/\u00e9cole.txt\x00",  # école.txt
                returncode=0,
            )

            result = adapter.changed_files(Path("/repo"), "abc123")

        self.assertEqual(result, ("path/to/\u00e9cole.txt",))

    def test_failing_invocation_raises_git_history_error(self) -> None:
        """Verify a failing invocation raises GitHistoryError."""
        adapter = GitAdapter()
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result(
                stderr="fatal: bad object abc123",
                returncode=128,
            )

            with self.assertRaisesRegex(GitHistoryError, "fatal: bad object abc123"):
                adapter.changed_files(Path("/repo"), "abc123")

    def test_single_file_change(self) -> None:
        """Verify single file change returns single-element tuple."""
        adapter = GitAdapter()
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result(
                stdout="single.txt\x00",
                returncode=0,
            )

            result = adapter.changed_files(Path("/repo"), "abc123")

        self.assertEqual(result, ("single.txt",))

    def test_git_command_uses_correct_diff_tree_flags(self) -> None:
        """Verify the exact diff-tree flag combination from design.md."""
        adapter = GitAdapter()
        with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
            run.return_value = _git_result(stdout="", returncode=0)

            adapter.changed_files(Path("/repo"), "abc123")

        call_args = run.call_args_list[0].args[0]
        expected_flags = [
            "diff-tree",
            "-r",
            "-m",
            "--first-parent",
            "--root",
            "--no-commit-id",
            "--name-only",
            "-z",
            "--no-ext-diff",
            "--no-textconv",
            "abc123",
        ]
        self.assertEqual(call_args[3:], expected_flags)


if __name__ == "__main__":
    unittest.main()

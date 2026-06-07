import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.commits import (
    GitCommit,
    GitCommitExtractor,
    GitHistoryError,
    filter_commits,
)


class GitCommitExtractorTests(unittest.TestCase):
    def test_detects_latest_release_marker_in_git_history(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))

        with patch("release_notes_generator.commits.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="newer\x1fFeature after release\nrelease\x1f[Release] 1.0\nolder\x1f[Release] 0.9\n",
                stderr="",
            )

            marker_hash = extractor.latest_release_marker_hash("[Release]")

        self.assertEqual(marker_hash, "release")
        run.assert_called_once_with(
            ["git", "-C", "/repo", "log", "--format=%H%x1f%s"],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_extracts_commits_after_latest_release_marker(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))

        with patch("release_notes_generator.commits.subprocess.run") as run:
            run.side_effect = [
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="release\x1f[Release] 1.0\nolder\x1f[Release] 0.9\n",
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="a1\x1fdev@example.com\x1fPix: add payment\nb2\x1fdev@example.com\x1fGlobalLoyalty: add rewards\n",
                    stderr="",
                ),
            ]

            commits = extractor.commits_after_latest_release_marker("[Release]")

        self.assertEqual(
            commits,
            (
                GitCommit("a1", "dev@example.com", "Pix: add payment"),
                GitCommit("b2", "dev@example.com", "GlobalLoyalty: add rewards"),
            ),
        )
        run.assert_called_with(
            [
                "git",
                "-C",
                "/repo",
                "log",
                "--reverse",
                "--format=%H%x1f%ae%x1f%s",
                "release..HEAD",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_ignores_commits_outside_selected_release_range(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))

        with patch("release_notes_generator.commits.subprocess.run") as run:
            run.side_effect = [
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="release\x1f[Release]\n", stderr=""
                ),
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="included\x1fdev@example.com\x1fPix: included\n",
                    stderr="",
                ),
            ]

            commits = extractor.commits_after_latest_release_marker("[Release]")

        self.assertEqual(
            commits,
            (GitCommit("included", "dev@example.com", "Pix: included"),),
        )
        self.assertEqual(
            run.call_args_list[1].args[0][-1],
            "release..HEAD",
        )

    def test_returns_no_commits_when_history_after_release_marker_is_empty(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))

        with patch("release_notes_generator.commits.subprocess.run") as run:
            run.side_effect = [
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="release\x1f[Release]\n", stderr=""
                ),
                subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
            ]

            commits = extractor.commits_after_latest_release_marker("[Release]")

        self.assertEqual(commits, ())

    def test_raises_when_no_release_marker_exists(self) -> None:
        extractor = GitCommitExtractor(Path("/repo"))

        with patch("release_notes_generator.commits.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="a1\x1fFeature\n", stderr=""
            )

            with self.assertRaises(GitHistoryError):
                extractor.commits_after_latest_release_marker("[Release]")


class CommitFilteringTests(unittest.TestCase):
    def test_unauthorized_authors_are_ignored(self) -> None:
        commits = (
            GitCommit("a1", "approved@example.com", "Pix: add payment"),
            GitCommit("b2", "unknown@example.com", "Pix: add refund"),
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
            GitCommit("a1", "approved@example.com", "Pix: add payment"),
            GitCommit("b2", "approved@example.com", "Unknown: add feature"),
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
            GitCommit("a1", "approved@example.com", "PIX-123 add payment"),
            GitCommit("b2", "approved@example.com", "GL-456 add rewards"),
        )

        accepted = filter_commits(
            commits,
            approved_author_emails=("approved@example.com",),
            module_tags={"Pix": ("PIX-",), "GlobalLoyalty": ("GL-",)},
        )

        self.assertEqual([commit.module_name for commit in accepted], ["Pix", "GlobalLoyalty"])

    def test_filter_returns_classified_commits_for_authorized_mapped_commits(self) -> None:
        commits = (GitCommit("a1", "approved@example.com", "TransitOpenLoop: add fare"),)

        accepted = filter_commits(
            commits,
            approved_author_emails=("approved@example.com",),
            module_tags={"TransitOpenLoop": ("TransitOpenLoop",)},
        )

        self.assertEqual(accepted[0].commit_hash, "a1")
        self.assertEqual(accepted[0].author_email, "approved@example.com")
        self.assertEqual(accepted[0].subject, "TransitOpenLoop: add fare")
        self.assertEqual(accepted[0].module_name, "TransitOpenLoop")


if __name__ == "__main__":
    unittest.main()

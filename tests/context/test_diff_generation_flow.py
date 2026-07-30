import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.commits import (
    GitCommit,
    filter_commits,
    group_commit_hashes_by_module,
)
from release_notes_generator.configuration import load_module_config
from release_notes_generator.diffs import generate_diff_files


class DiffGenerationFlowTests(unittest.TestCase):
    def test_accepted_commits_are_rendered_into_expected_temporary_markdown_files(self) -> None:
        commits = (
            _commit("pix1", "approved@example.com", "Pix: add payment"),
            _commit("gl1", "approved@example.com", "GlobalLoyalty: add rewards"),
            _commit("tol1", "approved@example.com", "TransitOpenLoop: add fare"),
            _commit("bad-author", "unknown@example.com", "Pix: should be ignored"),
            _commit("bad-module", "approved@example.com", "Unknown: should be ignored"),
        )
        accepted_commits = filter_commits(
            commits,
            approved_author_emails=("approved@example.com",),
            module_tags=load_module_config().module_tags,
        )
        grouped_hashes = group_commit_hashes_by_module(accepted_commits)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            with patch("release_notes_generator.diffs.subprocess.run") as run:
                run.side_effect = [
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="pix diff", stderr=""),
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="global loyalty diff", stderr=""),
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="transit diff", stderr=""),
                ]

                generated_files = generate_diff_files(Path("/repo"), grouped_hashes, output_dir)

            self.assertEqual(
                generated_files,
                {
                    "Pix": output_dir / "diff_pix.md",
                    "GlobalLoyalty": output_dir / "diff_globalloyalty.md",
                    "TransitOpenLoop": output_dir / "diff_transitopenloop.md",
                },
            )
            self.assertEqual((output_dir / "diff_pix.md").read_text(encoding="utf-8"), "pix diff\n")
            self.assertEqual(
                (output_dir / "diff_globalloyalty.md").read_text(encoding="utf-8"),
                "global loyalty diff\n",
            )
            self.assertEqual(
                (output_dir / "diff_transitopenloop.md").read_text(encoding="utf-8"),
                "transit diff\n",
            )
            self.assertEqual(
                [call.args[0][-2] for call in run.call_args_list],
                ["pix1", "gl1", "tol1"],
            )


def _commit(commit_hash: str, author_email: str, subject: str) -> GitCommit:
    return GitCommit(
        commit_hash,
        author_email,
        subject,
        datetime(2026, 1, 3, 12, tzinfo=timezone.utc),
    )


if __name__ == "__main__":
    unittest.main()

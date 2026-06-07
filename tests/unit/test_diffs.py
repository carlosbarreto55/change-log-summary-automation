import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.diffs import DiffGenerationError, generate_diff_files


class DiffGenerationTests(unittest.TestCase):
    def test_category_diff_files_only_include_commits_for_their_category(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "diffs"

            with patch("release_notes_generator.diffs.subprocess.run") as run:
                run.side_effect = [
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="pix diff", stderr=""),
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="gl diff", stderr=""),
                ]

                files = generate_diff_files(
                    Path("/repo"),
                    {
                        "Pix": ("pix1",),
                        "GlobalLoyalty": ("gl1",),
                    },
                    output_dir,
                )

            self.assertEqual(files["Pix"], output_dir / "diff_pix.md")
            self.assertEqual(files["GlobalLoyalty"], output_dir / "diff_globalloyalty.md")
            self.assertEqual(files["Pix"].read_text(encoding="utf-8"), "pix diff\n")
            self.assertEqual(files["GlobalLoyalty"].read_text(encoding="utf-8"), "gl diff\n")

    def test_unrelated_module_diffs_are_not_mixed_into_same_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "diffs"

            with patch("release_notes_generator.diffs.subprocess.run") as run:
                run.side_effect = [
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="pix first", stderr=""),
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="pix second", stderr=""),
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="transit diff", stderr=""),
                ]

                files = generate_diff_files(
                    Path("/repo"),
                    {
                        "Pix": ("pix1", "pix2"),
                        "TransitOpenLoop": ("tol1",),
                    },
                    output_dir,
                )

            self.assertEqual(
                files["Pix"].read_text(encoding="utf-8"),
                "pix first\n\npix second\n",
            )
            self.assertEqual(files["TransitOpenLoop"].read_text(encoding="utf-8"), "transit diff\n")

    def test_empty_groups_do_not_generate_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "diffs"

            with patch("release_notes_generator.diffs.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="gl diff", stderr=""
                )

                files = generate_diff_files(
                    Path("/repo"),
                    {"Pix": (), "GlobalLoyalty": ("gl1",)},
                    output_dir,
                )

            self.assertEqual(set(files), {"GlobalLoyalty"})
            self.assertFalse((output_dir / "diff_pix.md").exists())
            run.assert_called_once_with(
                ["git", "-C", "/repo", "show", "gl1"],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_git_show_failure_raises_diff_generation_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("release_notes_generator.diffs.subprocess.run") as run:
                run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=128, stdout="", stderr="bad revision"
                )

                with self.assertRaises(DiffGenerationError):
                    generate_diff_files(Path("/repo"), {"Pix": ("missing",)}, Path(temp_dir))


if __name__ == "__main__":
    unittest.main()

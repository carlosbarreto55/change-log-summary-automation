import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from release_notes_generator.domain.analysis import DiffArtifact
from release_notes_generator.infrastructure.artifacts import LocalArtifactStore
from release_notes_generator.infrastructure.git import GitAdapter
from release_notes_generator.services.diff_generation import DiffGenerationService
from release_notes_generator.services.errors import DiffGenerationError


def generate_diff_files(repository_path, grouped_commit_hashes, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = DiffGenerationService(
        GitAdapter(), LocalArtifactStore()
    ).generate(repository_path, grouped_commit_hashes, output_dir)
    return {artifact.module_name: artifact.path for artifact in generated}


def delete_diff_files(paths):
    LocalArtifactStore().delete(
        tuple(DiffArtifact("test", Path(path)) for path in paths)
    )


def _git_show_call(commit_hash: str):
    # Use Path to normalize separators for cross-platform compatibility
    # Note: We check path ends with "repo" in assertions since resolve() is platform-specific
    return call(
        [
            "git",
            "-C",
            "/repo",
            "show",
            "--no-ext-diff",
            "--no-textconv",
            commit_hash,
            "--",
        ],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        env={"PATH": "/usr/bin", "GIT_OPTIONAL_LOCKS": "0"},
    )


class DiffGenerationTests(unittest.TestCase):
    def test_category_diff_files_only_include_commits_for_their_category(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "diffs"

            with patch("release_notes_generator.infrastructure.git.subprocess.run") as run:
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

    def test_frozen_hash_order_and_module_isolation_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "diffs"

            with (
                patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True),
                patch("release_notes_generator.infrastructure.git.subprocess.run") as run,
            ):
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
            # Check call count and commit hashes, path is platform-specific
            self.assertEqual(len(run.call_args_list), 3)
            for i, expected_hash in enumerate(["pix1", "pix2", "tol1"]):
                call_args = run.call_args_list[i].args[0]
                self.assertEqual(call_args[0], "git")
                self.assertEqual(call_args[1], "-C")
                self.assertTrue(call_args[2].endswith("repo"))
                self.assertEqual(call_args[6], expected_hash)

    def test_empty_groups_do_not_generate_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "diffs"

            with (
                patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True),
                patch("release_notes_generator.infrastructure.git.subprocess.run") as run,
            ):
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
            # Check call count and commit hash, path is platform-specific
            self.assertEqual(len(run.call_args_list), 1)
            call_args = run.call_args_list[0].args[0]
            self.assertEqual(call_args[0], "git")
            self.assertEqual(call_args[1], "-C")
            self.assertTrue(call_args[2].endswith("repo"))
            self.assertEqual(call_args[6], "gl1")

    def test_git_show_failure_stops_generation_without_partial_module_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            with (
                patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True),
                patch("release_notes_generator.infrastructure.git.subprocess.run") as run,
            ):
                run.side_effect = [
                    subprocess.CompletedProcess(args=[], returncode=0, stdout="first", stderr=""),
                    subprocess.CompletedProcess(
                        args=[], returncode=128, stdout="", stderr="bad revision"
                    ),
                ]

                with self.assertRaisesRegex(DiffGenerationError, "^bad revision$"):
                    generate_diff_files(
                        Path("/repo"),
                        {"Pix": ("first", "missing"), "TransitOpenLoop": ("not-reached",)},
                        output_dir,
                    )

            # Check call count and commit hashes, path is platform-specific
            self.assertEqual(len(run.call_args_list), 2)
            for i, expected_hash in enumerate(["first", "missing"]):
                call_args = run.call_args_list[i].args[0]
                self.assertEqual(call_args[0], "git")
                self.assertEqual(call_args[1], "-C")
                self.assertTrue(call_args[2].endswith("repo"))
                self.assertEqual(call_args[6], expected_hash)
            self.assertFalse((output_dir / "diff_pix.md").exists())
            self.assertFalse((output_dir / "diff_transitopenloop.md").exists())

    def test_write_failure_removes_all_completed_and_partial_diff_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            original_write_text = Path.write_text

            def fail_second_write(path, content, **kwargs):
                if path.name == "diff_transitopenloop.md":
                    original_write_text(path, "partial", **kwargs)
                    raise OSError("disk full")
                return original_write_text(path, content, **kwargs)

            with (
                patch.object(GitAdapter, "show", return_value="diff"),
                patch.object(Path, "write_text", autospec=True, side_effect=fail_second_write),
                self.assertRaisesRegex(DiffGenerationError, "Unable to write"),
            ):
                generate_diff_files(
                    Path("/repo"),
                    {"Pix": ("pix1",), "TransitOpenLoop": ("tol1",)},
                    output_dir,
                )

            self.assertFalse((output_dir / "diff_pix.md").exists())
            self.assertFalse((output_dir / "diff_transitopenloop.md").exists())

    def test_delete_diff_files_removes_generated_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            diff_file = Path(temp_dir) / "diff_pix.md"
            other_file = Path(temp_dir) / "manual-note.md"
            diff_file.write_text("temporary diff", encoding="utf-8")
            other_file.write_text("keep", encoding="utf-8")

            delete_diff_files((diff_file, Path(temp_dir) / "already-deleted.md"))

            self.assertFalse(diff_file.exists())
            self.assertTrue(other_file.exists())


if __name__ == "__main__":
    unittest.main()

import os
import subprocess
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from release_notes_generator.domain.configuration import ReportMode, RepositoryUpdateMode
from release_notes_generator.infrastructure.path_safety import (
    PathSafetyAdapter,
    validate_analysis_paths,
)
from release_notes_generator.services.errors import RepositorySafetyError


class RepositorySafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.root = Path(self._temporary_directory.name)
        self.repository = self.root / "repository"
        subprocess.run(
            ["git", "init", "--quiet", str(self.repository)],
            check=True,
            capture_output=True,
            text=True,
        )
        self.external = self.root / "analysis"
        self.adapter = PathSafetyAdapter()

    def validate(
        self,
        temp_diff_dir: Path,
        output_path: Path,
        mode: object = RepositoryUpdateMode.READ_ONLY,
        repository_path: Optional[Path] = None,
        report_mode: object = ReportMode.AI_SUMMARY,
    ):
        return validate_analysis_paths(
            repository_path=repository_path or self.repository,
            temp_diff_dir=temp_diff_dir,
            output_path=output_path,
            repository_update_mode=mode,
            report_mode=report_mode,
        )

    def validate_commit_list(self, output_path: Path):
        return validate_analysis_paths(
            repository_path=self.repository,
            temp_diff_dir=None,
            output_path=output_path,
            repository_update_mode=RepositoryUpdateMode.READ_ONLY,
            report_mode=ReportMode.COMMIT_LIST,
        )

    def test_accepts_canonical_external_paths_and_returns_immutable_value(self) -> None:
        nested_repository_path = self.repository / "source"
        nested_repository_path.mkdir()
        temp_diff_dir = self.external / "tmp" / "diffs"
        output_path = self.external / "output" / "release.pdf"

        paths = self.validate(
            temp_diff_dir,
            output_path,
            repository_path=nested_repository_path,
        )

        self.assertEqual(paths.repository_root, self.repository.resolve())
        self.assertEqual(paths.temp_diff_dir, temp_diff_dir.resolve())
        self.assertEqual(paths.output_path, output_path.resolve())
        with self.assertRaises(FrozenInstanceError):
            paths.temp_diff_dir = self.repository  # type: ignore[misc]

    def test_ai_summary_still_requires_and_validates_temporary_paths(self) -> None:
        with self.assertRaisesRegex(
            RepositorySafetyError, "Temporary analysis path"
        ):
            validate_analysis_paths(
                repository_path=self.repository,
                temp_diff_dir=None,
                output_path=self.external / "release.pdf",
                repository_update_mode=RepositoryUpdateMode.READ_ONLY,
                report_mode=ReportMode.AI_SUMMARY,
            )

        with self.assertRaisesRegex(
            RepositorySafetyError, "Temporary analysis path"
        ):
            self.validate(
                self.repository / "diffs",
                self.external / "release.pdf",
                report_mode=ReportMode.AI_SUMMARY,
            )

    def test_commit_list_validates_only_the_pdf_destination(self) -> None:
        output_path = self.external / "output" / "release.pdf"

        paths = self.validate_commit_list(output_path)

        self.assertIsNone(paths.temp_diff_dir)
        self.assertIsNone(paths.configured_temp_diff_dir)
        self.assertEqual(paths.output_path, output_path.resolve())

    def test_commit_list_prepare_and_revalidate_create_only_output_parent(self) -> None:
        output_path = self.external / "output" / "release.pdf"
        paths = self.validate_commit_list(output_path)

        prepared = self.adapter.prepare(paths)
        revalidated = self.adapter.revalidate(prepared)

        self.assertIs(revalidated, paths)
        self.assertTrue(output_path.parent.is_dir())
        self.assertEqual(tuple(self.external.iterdir()), (output_path.parent,))
        self.assertFalse(output_path.exists())

    def test_commit_list_revalidation_rejects_output_alias_into_worktree(self) -> None:
        output_path = self.external / "alias" / "release.pdf"
        paths = self.validate_commit_list(output_path)
        self.external.mkdir()
        (self.external / "alias").symlink_to(
            self.repository, target_is_directory=True
        )

        with self.assertRaisesRegex(RepositorySafetyError, "Final output path"):
            self.adapter.revalidate(paths)

    def test_resolves_git_top_level_with_optional_locks_disabled(self) -> None:
        completed_process = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=f"{self.repository}\n",
            stderr="",
        )

        with patch(
            "release_notes_generator.infrastructure.path_safety.subprocess.run",
            return_value=completed_process,
        ) as run:
            self.validate(
                self.external / "diffs",
                self.external / "release.pdf",
            )

        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(
            args[0],
            [
                "git",
                "-C",
                str(self.repository),
                "rev-parse",
                "--show-toplevel",
            ],
        )
        self.assertTrue(kwargs["check"])
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["env"]["GIT_OPTIONAL_LOCKS"], "0")
        self.assertEqual(
            {key: value for key, value in os.environ.items()},
            {
                key: value
                for key, value in kwargs["env"].items()
                if key != "GIT_OPTIONAL_LOCKS"
            },
        )

    def test_rejects_equal_and_descendant_temp_paths_in_every_mode(self) -> None:
        for mode in RepositoryUpdateMode:
            for name, temp_diff_dir in (
                ("equal", self.repository),
                ("descendant", self.repository / "tmp" / "diffs"),
            ):
                with self.subTest(mode=mode.value, path=name):
                    with self.assertRaisesRegex(
                        RepositorySafetyError,
                        "Temporary analysis path",
                    ):
                        self.validate(
                            temp_diff_dir,
                            self.external / "release.pdf",
                            mode,
                        )

                    self.assertFalse((self.repository / "tmp").exists())

    def test_rejects_equal_and_descendant_output_in_protected_modes(self) -> None:
        for mode in (
            RepositoryUpdateMode.READ_ONLY,
            RepositoryUpdateMode.REFRESH_REMOTE_REFS,
        ):
            for name, output_path in (
                ("equal", self.repository),
                ("descendant", self.repository / "output" / "release.pdf"),
            ):
                with self.subTest(mode=mode.value, path=name):
                    with self.assertRaisesRegex(
                        RepositorySafetyError,
                        "Final output path",
                    ):
                        self.validate(
                            self.external / "diffs",
                            output_path,
                            mode,
                        )

                    self.assertFalse((self.repository / "output").exists())

    def test_allows_internal_output_only_for_explicit_legacy_mode(self) -> None:
        output_path = self.repository / "output" / "release.pdf"

        paths = self.validate(
            self.external / "diffs",
            output_path,
            RepositoryUpdateMode.LEGACY_IN_PLACE_SYNC,
        )

        self.assertEqual(paths.output_path, output_path.resolve())
        self.assertFalse(output_path.parent.exists())

    def test_uses_enum_value_without_importing_a_specific_enum_type(self) -> None:
        class CompatibleMode:
            value = "legacy_in_place_sync"

        paths = self.validate(
            self.external / "diffs",
            self.repository / "release.pdf",
            CompatibleMode(),
        )

        self.assertEqual(paths.output_path, (self.repository / "release.pdf").resolve())

    def test_rejects_relative_traversal_into_worktree_before_writes(self) -> None:
        traversal = self.external / ".." / self.repository.name / "tmp" / "diffs"

        with self.assertRaises(RepositorySafetyError):
            self.validate(traversal, self.external / "release.pdf")

        self.assertFalse((self.repository / "tmp").exists())

    def test_rejects_existing_symlink_aliases_into_worktree(self) -> None:
        alias = self.root / "repository-alias"
        alias.symlink_to(self.repository, target_is_directory=True)

        with self.assertRaises(RepositorySafetyError):
            self.validate(alias / "diffs", self.external / "release.pdf")
        with self.assertRaises(RepositorySafetyError):
            self.validate(self.external / "diffs", alias / "release.pdf")

        self.assertFalse((self.repository / "diffs").exists())
        self.assertFalse((self.repository / "release.pdf").exists())

    def test_rejects_nonexistent_suffix_below_symlink_ancestor(self) -> None:
        alias = self.root / "repository-alias"
        alias.symlink_to(self.repository, target_is_directory=True)
        nonexistent_suffix = alias / "not-created" / "nested"

        with self.assertRaises(RepositorySafetyError):
            self.validate(
                nonexistent_suffix,
                self.external / "release.pdf",
            )
        with self.assertRaises(RepositorySafetyError):
            self.validate(
                self.external / "diffs",
                nonexistent_suffix / "release.pdf",
            )

        self.assertFalse((self.repository / "not-created").exists())

    def test_revalidates_after_external_temp_directory_creation(self) -> None:
        temp_diff_dir = self.external / "diffs"
        paths = self.validate(temp_diff_dir, self.external / "release.pdf")
        temp_diff_dir.mkdir(parents=True)

        revalidated = self.adapter.revalidate(paths)

        self.assertIs(revalidated, paths)

    def test_prepare_creates_external_directories_and_revalidates(self) -> None:
        temp_diff_dir = self.external / "tmp" / "diffs"
        output_path = self.external / "output" / "release.pdf"
        paths = self.validate(temp_diff_dir, output_path)

        prepared = self.adapter.prepare(paths)

        self.assertIs(prepared, paths)
        self.assertTrue(temp_diff_dir.is_dir())
        self.assertTrue(output_path.parent.is_dir())
        self.assertFalse(output_path.exists())

    def test_revalidation_rejects_temp_path_replaced_by_internal_symlink(self) -> None:
        self.external.mkdir()
        temp_diff_dir = self.external / "diffs"
        paths = self.validate(temp_diff_dir, self.external / "release.pdf")
        temp_diff_dir.symlink_to(self.repository, target_is_directory=True)

        with self.assertRaises(RepositorySafetyError):
            self.adapter.revalidate(paths)

    def test_unusable_external_temp_path_errors_without_worktree_fallback(self) -> None:
        self.external.mkdir()
        unusable_ancestor = self.external / "not-a-directory"
        unusable_ancestor.write_text("content", encoding="utf-8")

        with self.assertRaisesRegex(RepositorySafetyError, "cannot be used"):
            self.validate(
                unusable_ancestor / "diffs",
                self.external / "release.pdf",
            )

        self.assertEqual(unusable_ancestor.read_text(encoding="utf-8"), "content")
        self.assertFalse((self.repository / "tmp").exists())
        self.assertFalse((self.repository / "diffs").exists())


if __name__ == "__main__":
    unittest.main()

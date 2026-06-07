"""Temporary diff-file generation for classified release-note commits."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, Mapping

from release_notes_generator.paths import TEMP_DIFF_DIR


class DiffGenerationError(RuntimeError):
    """Raised when a temporary category diff file cannot be generated."""


def generate_diff_files(
    repository_path: Path,
    grouped_commit_hashes: Mapping[str, Iterable[str]],
    output_dir: Path = TEMP_DIFF_DIR,
) -> dict[str, Path]:
    """Write one temporary Markdown diff file for each non-empty module group."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    generated_files: dict[str, Path] = {}
    for module_name, commit_hashes in grouped_commit_hashes.items():
        hashes = tuple(commit_hashes)
        if not hashes:
            continue

        diff_file_path = output_path / _diff_file_name(module_name)
        diff_outputs = [_git_show(repository_path, commit_hash) for commit_hash in hashes]
        diff_file_path.write_text(_join_diff_outputs(diff_outputs), encoding="utf-8")
        generated_files[module_name] = diff_file_path

    return generated_files


def _git_show(repository_path: Path, commit_hash: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository_path), "show", commit_hash],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git show failed."
        raise DiffGenerationError(message)
    return result.stdout


def _join_diff_outputs(diff_outputs: Iterable[str]) -> str:
    return "\n\n".join(output.rstrip("\n") for output in diff_outputs) + "\n"


def _diff_file_name(module_name: str) -> str:
    safe_name = "".join(
        character.lower() if character.isascii() and character.isalnum() else "_"
        for character in module_name
    ).strip("_")
    if not safe_name:
        raise DiffGenerationError("Module name cannot be converted into a diff file name.")
    return f"diff_{safe_name}.md"

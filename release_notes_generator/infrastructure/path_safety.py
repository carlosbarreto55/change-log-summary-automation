"""Canonical path validation for repository analysis artifacts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Optional

from release_notes_generator.domain.analysis import AnalysisPaths
from release_notes_generator.domain.configuration import WorkflowConfiguration
from release_notes_generator.services.errors import RepositorySafetyError


class PathSafetyAdapter:
    """Validate, prepare, and revalidate external analysis destinations."""

    def validate(self, configuration: WorkflowConfiguration) -> AnalysisPaths:
        return validate_analysis_paths(
            configuration.repository_path,
            configuration.temp_diff_dir,
            configuration.output_path,
            configuration.repository_update_mode,
            configuration.report_mode,
        )

    def revalidate(self, paths: AnalysisPaths) -> AnalysisPaths:
        temp_diff_dir, output_path = _validate_destinations(
            paths.repository_root,
            paths.configured_temp_diff_dir,
            paths.configured_output_path,
            paths.protect_output,
        )
        if temp_diff_dir != paths.temp_diff_dir or output_path != paths.output_path:
            raise RepositorySafetyError(
                "Analysis path identity changed after initial validation."
            )
        return paths

    def prepare(self, paths: AnalysisPaths) -> AnalysisPaths:
        try:
            if paths.temp_diff_dir is not None:
                paths.temp_diff_dir.mkdir(parents=True, exist_ok=True)
            paths.output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RepositorySafetyError(
                "Unable to prepare validated analysis destinations."
            ) from exc
        return self.revalidate(paths)


def validate_analysis_paths(
    repository_path: Path,
    temp_diff_dir: Optional[Path],
    output_path: Path,
    repository_update_mode: Any,
    report_mode: Any = "ai_summary",
) -> AnalysisPaths:
    """Resolve the worktree root and validate analysis destinations without writes."""
    repository_root = _resolve_repository_root(Path(repository_path))
    configured_output_path = _absolute_path(Path(output_path))
    mode_value = getattr(repository_update_mode, "value", repository_update_mode)
    valid_modes = {
        "read_only",
        "refresh_remote_refs",
        "legacy_in_place_sync",
    }
    if mode_value not in valid_modes:
        raise RepositorySafetyError(
            f"Unsupported repository update mode for path validation: {mode_value!r}."
        )

    report_mode_value = getattr(report_mode, "value", report_mode)
    if report_mode_value not in {"ai_summary", "commit_list"}:
        raise RepositorySafetyError(
            f"Unsupported report mode for path validation: {report_mode_value!r}."
        )
    if report_mode_value == "ai_summary":
        if temp_diff_dir is None:
            raise RepositorySafetyError(
                "Temporary analysis path is required for ai_summary mode."
            )
        configured_temp_diff_dir = _absolute_path(Path(temp_diff_dir))
    else:
        configured_temp_diff_dir = None

    protect_output = mode_value != "legacy_in_place_sync"
    canonical_temp_diff_dir, canonical_output_path = _validate_destinations(
        repository_root,
        configured_temp_diff_dir,
        configured_output_path,
        protect_output,
    )
    return AnalysisPaths(
        repository_root=repository_root,
        temp_diff_dir=canonical_temp_diff_dir,
        output_path=canonical_output_path,
        configured_temp_diff_dir=configured_temp_diff_dir,
        configured_output_path=configured_output_path,
        protect_output=protect_output,
    )


def _resolve_repository_root(repository_path: Path) -> Path:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository_path),
                "rev-parse",
                "--show-toplevel",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RepositorySafetyError(
            f"Unable to resolve Git worktree root from: {repository_path}"
        ) from exc

    top_level = result.stdout.strip()
    if not top_level:
        raise RepositorySafetyError(
            f"Git returned no worktree root for: {repository_path}"
        )
    try:
        repository_root = Path(top_level).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RepositorySafetyError(
            f"Unable to canonicalize Git worktree root: {top_level}"
        ) from exc
    if not repository_root.is_dir():
        raise RepositorySafetyError(
            f"Git worktree root is not a directory: {repository_root}"
        )
    return repository_root


def _validate_destinations(
    repository_root: Path,
    configured_temp_diff_dir: Optional[Path],
    configured_output_path: Path,
    protect_output: bool,
) -> tuple[Optional[Path], Path]:
    temp_diff_dir = None
    if configured_temp_diff_dir is not None:
        temp_diff_dir = _canonical_path(
            configured_temp_diff_dir,
            "Temporary analysis path",
        )
        _reject_worktree_path(
            temp_diff_dir,
            repository_root,
            "Temporary analysis path",
        )
        _require_usable_directory_destination(
            temp_diff_dir,
            "Temporary analysis path",
        )

    output_path = _canonical_path(configured_output_path, "Final output path")
    if protect_output:
        _reject_worktree_path(output_path, repository_root, "Final output path")
    _require_usable_file_destination(output_path, "Final output path")
    return temp_diff_dir, output_path


def _absolute_path(path: Path) -> Path:
    path = path.expanduser()
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _canonical_path(path: Path, description: str) -> Path:
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise RepositorySafetyError(
            f"{description} cannot be canonically resolved: {path}"
        ) from exc


def _reject_worktree_path(path: Path, repository_root: Path, description: str) -> None:
    if path == repository_root or repository_root in path.parents:
        raise RepositorySafetyError(
            f"{description} must be outside the analyzed worktree: {path}"
        )


def _require_usable_directory_destination(path: Path, description: str) -> None:
    if path.exists() and not path.is_dir():
        raise RepositorySafetyError(f"{description} cannot be used as a directory: {path}")
    ancestor = path if path.exists() else _nearest_existing_ancestor(path)
    _require_writable_directory(ancestor, path, description)


def _require_usable_file_destination(path: Path, description: str) -> None:
    if path.exists() and path.is_dir():
        raise RepositorySafetyError(f"{description} cannot be used as a file: {path}")
    ancestor = _nearest_existing_ancestor(path.parent)
    _require_writable_directory(ancestor, path, description)


def _nearest_existing_ancestor(path: Path) -> Path:
    current = path
    while not current.exists() and current.parent != current:
        current = current.parent
    return current


def _require_writable_directory(
    ancestor: Path,
    destination: Path,
    description: str,
) -> None:
    if not ancestor.is_dir() or not os.access(ancestor, os.W_OK | os.X_OK):
        raise RepositorySafetyError(
            f"{description} cannot be used at its configured destination: {destination}"
        )

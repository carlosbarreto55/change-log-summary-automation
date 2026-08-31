"""Immutable values for external analysis artifacts."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AnalysisPaths:
    """Canonical destinations validated for one repository analysis."""

    repository_root: Path
    temp_diff_dir: Optional[Path]
    output_path: Path
    configured_temp_diff_dir: Optional[Path] = field(repr=False, compare=False)
    configured_output_path: Path = field(repr=False, compare=False)
    protect_output: bool = field(repr=False, compare=False)


@dataclass(frozen=True)
class DiffArtifact:
    """One temporary module-specific diff artifact."""

    module_name: str
    path: Path

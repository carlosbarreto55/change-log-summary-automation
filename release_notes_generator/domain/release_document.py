"""Output-independent release-document content."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Union


@dataclass(frozen=True)
class ReleaseCommitEntry:
    """One exact subject and full object ID in a deterministic report."""

    subject: str
    commit_hash: str


@dataclass(frozen=True)
class TaskReference:
    """A task or PLM reference extracted from a commit subject.

    Attributes:
        reference_id: The task/PLM identifier (e.g., "WLT-123", "P260820-05441")
        module_name: The module to which the source commit was classified
        reference_count: Number of times this reference appears
    """

    reference_id: str
    module_name: str
    reference_count: int


@dataclass(frozen=True)
class ReleaseModuleSummary:
    """One configured module and its generated summary."""

    name: str
    summary: str
    qualifying_change_count: int
    change_start_date: date
    change_end_date: date


@dataclass(frozen=True)
class ReleaseModuleCommitList:
    """One configured module and its ordered qualifying commits."""

    name: str
    commits: tuple[ReleaseCommitEntry, ...]
    qualifying_change_count: int
    change_start_date: date
    change_end_date: date


ReleaseModuleContent = Union[ReleaseModuleSummary, ReleaseModuleCommitList]


@dataclass(frozen=True)
class ReleaseSection:
    """One configured release-notes section."""

    title: str
    modules: tuple[ReleaseModuleContent, ...]


@dataclass(frozen=True)
class TaskReferenceSection:
    """A section containing task/PLM references grouped by module.

    This section provides a cross-cutting view of all task references
    extracted from commit subjects, showing reference frequency and
    module context.

    Attributes:
        title: Section title (always "Task References")
        references: Tuple of TaskReference objects sorted by module and reference_id
    """

    title: str = "Task References"
    references: tuple[TaskReference, ...] = ()


@dataclass(frozen=True)
class ReleaseDocument:
    """Ordered release-note content independent from an output format."""

    title: str
    repository_name: str
    qualifying_change_count: int
    change_start_date: Optional[date]
    change_end_date: Optional[date]
    sections: tuple[ReleaseSection, ...]
    task_reference_section: Optional[TaskReferenceSection] = None
    empty_message: Optional[str] = None

    @property
    def change_start_iso_week(self) -> Optional[str]:
        return _iso_week(self.change_start_date)

    @property
    def change_end_iso_week(self) -> Optional[str]:
        return _iso_week(self.change_end_date)


def _iso_week(value: Optional[date]) -> Optional[str]:
    if value is None:
        return None
    iso_year, iso_week, _ = value.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"

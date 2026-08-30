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
class ReleaseDocument:
    """Ordered release-note content independent from an output format."""

    title: str
    repository_name: str
    qualifying_change_count: int
    change_start_date: Optional[date]
    change_end_date: Optional[date]
    sections: tuple[ReleaseSection, ...]
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

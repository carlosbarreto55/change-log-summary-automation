"""Output-independent structured release-notes composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timezone
from typing import Iterable, Mapping, Optional

from release_notes_generator.commits import ClassifiedCommit
from release_notes_generator.configuration import ModuleConfig


@dataclass(frozen=True)
class ReleaseModuleSummary:
    """One configured module and its generated summary."""

    name: str
    summary: str
    qualifying_change_count: int
    change_start_date: date
    change_end_date: date


@dataclass(frozen=True)
class ReleaseSection:
    """One configured release-notes section."""

    title: str
    modules: tuple[ReleaseModuleSummary, ...]


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
        """Return the ISO year-week containing the first qualifying change."""
        return _iso_week(self.change_start_date)

    @property
    def change_end_iso_week(self) -> Optional[str]:
        """Return the ISO year-week containing the last qualifying change."""
        return _iso_week(self.change_end_date)


def compose_release_document(
    summaries: Mapping[str, str],
    module_config: ModuleConfig,
    repository_name: str,
    accepted_commits: Iterable[ClassifiedCommit],
) -> ReleaseDocument:
    """Compose configured module summaries into ordered, non-empty sections."""
    commits = tuple(accepted_commits)
    commits_by_module: dict[str, list[ClassifiedCommit]] = {}
    for commit in commits:
        commits_by_module.setdefault(commit.module_name, []).append(commit)

    section_modules: dict[str, list[ReleaseModuleSummary]] = {}
    for module in module_config.modules:
        summary = summaries.get(module.name, "").strip()
        module_commits = commits_by_module.get(module.name, [])
        if not summary or not module_commits:
            continue

        module_start_date, module_end_date = _date_range(module_commits)
        if module_start_date is None or module_end_date is None:
            continue
        section_modules.setdefault(module.section, []).append(
            ReleaseModuleSummary(
                name=module.name,
                summary=summary,
                qualifying_change_count=len(module_commits),
                change_start_date=module_start_date,
                change_end_date=module_end_date,
            )
        )

    sections = tuple(
        ReleaseSection(title, tuple(modules))
        for title, modules in section_modules.items()
    )
    change_start_date, change_end_date = _date_range(commits)
    return ReleaseDocument(
        title="Release Notes",
        repository_name=repository_name,
        qualifying_change_count=len(commits),
        change_start_date=change_start_date,
        change_end_date=change_end_date,
        sections=sections,
        empty_message=None if sections else "No qualifying changes.",
    )


def _date_range(
    commits: Iterable[ClassifiedCommit],
) -> tuple[Optional[date], Optional[date]]:
    dates: list[date] = []
    for commit in commits:
        if commit.authored_at.tzinfo is None or commit.authored_at.utcoffset() is None:
            raise ValueError("Classified commit author timestamps must include a UTC offset.")
        dates.append(commit.authored_at.astimezone(timezone.utc).date())

    if not dates:
        return None, None
    return min(dates), max(dates)


def _iso_week(value: Optional[date]) -> Optional[str]:
    if value is None:
        return None
    iso_year, iso_week, _ = value.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"

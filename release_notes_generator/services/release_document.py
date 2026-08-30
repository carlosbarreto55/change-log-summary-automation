"""Configured release-document composition."""

from datetime import date, timezone
from typing import Iterable, Mapping, Optional

from release_notes_generator.domain.configuration import ModulePolicy
from release_notes_generator.domain.release_document import (
    ReleaseCommitEntry,
    ReleaseDocument,
    ReleaseModuleCommitList,
    ReleaseModuleSummary,
    ReleaseSection,
)
from release_notes_generator.domain.repository import ClassifiedCommit


class ReleaseDocumentService:
    """Compose ordered module summaries and descriptive metadata."""

    def compose(
        self,
        summaries: Mapping[str, str],
        modules: ModulePolicy,
        repository_name: str,
        accepted_commits: Iterable[ClassifiedCommit],
    ) -> ReleaseDocument:
        commits = tuple(accepted_commits)
        commits_by_module: dict[str, list[ClassifiedCommit]] = {}
        for commit in commits:
            commits_by_module.setdefault(commit.module_name, []).append(commit)

        section_modules: dict[str, list[ReleaseModuleSummary]] = {}
        for module in modules.modules:
            summary = summaries.get(module.name, "").strip()
            module_commits = commits_by_module.get(module.name, [])
            if not summary or not module_commits:
                continue
            start, end = _date_range(module_commits)
            if start is None or end is None:
                continue
            section_modules.setdefault(module.section, []).append(
                ReleaseModuleSummary(
                    name=module.name,
                    summary=summary,
                    qualifying_change_count=len(module_commits),
                    change_start_date=start,
                    change_end_date=end,
                )
            )

        sections = tuple(
            ReleaseSection(title, tuple(section_modules_for_title))
            for title, section_modules_for_title in section_modules.items()
        )
        change_start, change_end = _date_range(commits)
        return ReleaseDocument(
            title="Release Notes",
            repository_name=repository_name,
            qualifying_change_count=len(commits),
            change_start_date=change_start,
            change_end_date=change_end,
            sections=sections,
            empty_message=None if sections else "No qualifying changes.",
        )

    def compose_commit_list(
        self,
        modules: ModulePolicy,
        repository_name: str,
        accepted_commits: Iterable[ClassifiedCommit],
    ) -> ReleaseDocument:
        """Compose configured modules from exact accepted commit metadata."""
        commits = tuple(accepted_commits)
        commits_by_module: dict[str, list[ClassifiedCommit]] = {}
        for commit in commits:
            commits_by_module.setdefault(commit.module_name, []).append(commit)

        section_modules: dict[str, list[ReleaseModuleCommitList]] = {}
        for module in modules.modules:
            module_commits = commits_by_module.get(module.name, [])
            if not module_commits:
                continue
            start, end = _date_range(module_commits)
            if start is None or end is None:
                continue
            section_modules.setdefault(module.section, []).append(
                ReleaseModuleCommitList(
                    name=module.name,
                    commits=tuple(
                        ReleaseCommitEntry(commit.subject, commit.commit_hash)
                        for commit in module_commits
                    ),
                    qualifying_change_count=len(module_commits),
                    change_start_date=start,
                    change_end_date=end,
                )
            )

        sections = tuple(
            ReleaseSection(title, tuple(section_modules_for_title))
            for title, section_modules_for_title in section_modules.items()
        )
        change_start, change_end = _date_range(commits)
        return ReleaseDocument(
            title="Release Commit Report",
            repository_name=repository_name,
            qualifying_change_count=len(commits),
            change_start_date=change_start,
            change_end_date=change_end,
            sections=sections,
            empty_message=None if sections else "No qualifying changes.",
        )


def _date_range(
    commits: Iterable[ClassifiedCommit],
) -> tuple[Optional[date], Optional[date]]:
    dates: list[date] = []
    for commit in commits:
        if commit.authored_at.tzinfo is None or commit.authored_at.utcoffset() is None:
            raise ValueError(
                "Classified commit author timestamps must include a UTC offset."
            )
        dates.append(commit.authored_at.astimezone(timezone.utc).date())
    if not dates:
        return None, None
    return min(dates), max(dates)

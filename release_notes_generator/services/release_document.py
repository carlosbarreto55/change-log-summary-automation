"""Configured release-document composition."""

import re
from collections import defaultdict
from datetime import date, timezone
from typing import Iterable, Mapping, Optional

from release_notes_generator.domain.configuration import ModulePolicy, TaskPatternConfig
from release_notes_generator.domain.release_document import (
    DATABASE_CHANGES_SECTION_TITLE,
    DatabaseChangeEntry,
    DatabaseChangeModuleGroup,
    DatabaseChangeSection,
    ReleaseCommitEntry,
    ReleaseDocument,
    ReleaseModuleCommitList,
    ReleaseModuleSummary,
    ReleaseSection,
    TaskReference,
    TaskReferenceSection,
)
from release_notes_generator.domain.repository import ClassifiedCommit
from release_notes_generator.services.database_changes import DatabaseChangeMatch

# Default task reference patterns
DEFAULT_TASK_PATTERNS = {
    "wlt": re.compile(r"\bWLT-(\d+)\b"),
    "wltm": re.compile(r"\bWLTM-(\d+)\b"),
    "plm": re.compile(r"\bP(\d{6})-(\d+)\b"),
}


def build_task_patterns_from_config(
    task_patterns_config: Optional[TaskPatternConfig],
) -> Optional[dict[str, re.Pattern]]:
    """Build compiled regex patterns from configuration.

    Args:
        task_patterns_config: Optional TaskPatternConfig with 'wlt', 'wltm', 'plm' pattern strings.
                             If None or empty, returns None to use defaults.

    Returns:
        Dict of compiled regex patterns, or None to use defaults.

    Raises:
        ValueError: If any pattern string is not a valid regex.
    """
    if task_patterns_config is None:
        return None

    result: dict[str, re.Pattern] = {}
    for key in ("wlt", "wltm", "plm"):
        pattern_str = getattr(task_patterns_config, key, None)
        if pattern_str:
            try:
                result[key] = re.compile(pattern_str)
            except re.error as exc:
                raise ValueError(
                    f"Invalid task pattern '{key}': {pattern_str} - {exc}"
                ) from exc

    return result if result else None


class ReleaseDocumentService:
    """Compose ordered module summaries and descriptive metadata."""

    def extract_task_references(
        self,
        commits: Iterable[ClassifiedCommit],
        task_patterns: Optional[dict[str, re.Pattern]] = None,
    ) -> tuple[TaskReference, ...]:
        """Extract task/PLM references from commit subjects and aggregate by (reference_id, module_name).

        Args:
            commits: Classified commits to extract references from
            task_patterns: Optional custom regex patterns. If not provided, uses DEFAULT_TASK_PATTERNS.
                          Expected keys: "wlt", "wltm", "plm"

        Returns:
            Tuple of TaskReference objects sorted by (module_name, reference_id)

        Raises:
            ValueError: If any pattern in task_patterns is not a compiled regex Pattern
        """
        patterns = task_patterns if task_patterns is not None else DEFAULT_TASK_PATTERNS

        # Validate patterns
        for key, pattern in patterns.items():
            if not isinstance(pattern, re.Pattern):
                raise ValueError(
                    f"Task pattern '{key}' must be a compiled regex Pattern, got {type(pattern).__name__}"
                )

        # Count occurrences of each (reference_id, module_name) pair
        task_counts: dict[tuple[str, str], int] = defaultdict(int)

        for commit in commits:
            for pattern_key, pattern in patterns.items():
                for match in pattern.finditer(commit.subject):
                    # For PLM pattern, reconstruct full reference from groups
                    if pattern_key == "plm":
                        reference_id = f"P{match.group(1)}-{match.group(2)}"
                    else:
                        # For WLT and WLTM, include the prefix with the matched number
                        prefix = "WLT" if pattern_key == "wlt" else "WLTM"
                        reference_id = f"{prefix}-{match.group(1)}"

                    key = (reference_id, commit.module_name)
                    task_counts[key] += 1

        # Build TaskReference objects
        task_references = [
            TaskReference(
                reference_id=reference_id,
                module_name=module_name,
                reference_count=count,
            )
            for (reference_id, module_name), count in task_counts.items()
        ]

        # Sort by module_name, then reference_id for deterministic output
        task_references.sort(key=lambda tr: (tr.module_name, tr.reference_id))

        return tuple(task_references)

    def compose(
        self,
        summaries: Mapping[str, str],
        modules: ModulePolicy,
        repository_name: str,
        accepted_commits: Iterable[ClassifiedCommit],
        task_patterns: Optional[dict[str, re.Pattern]] = None,
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

        # Extract task references
        task_references = self.extract_task_references(commits, task_patterns)
        task_section: Optional[TaskReferenceSection] = None
        if task_references:
            task_section = TaskReferenceSection(references=task_references)

        change_start, change_end = _date_range(commits)
        return ReleaseDocument(
            title="Release Notes",
            repository_name=repository_name,
            qualifying_change_count=len(commits),
            change_start_date=change_start,
            change_end_date=change_end,
            sections=sections,
            task_reference_section=task_section,
            empty_message=None if sections else "No qualifying changes.",
        )

    def compose_commit_list(
        self,
        modules: ModulePolicy,
        repository_name: str,
        accepted_commits: Iterable[ClassifiedCommit],
        task_patterns: Optional[dict[str, re.Pattern]] = None,
        database_matches: tuple[DatabaseChangeMatch, ...] = (),
    ) -> ReleaseDocument:
        """Compose configured modules from exact accepted commit metadata.
        
        Args:
            modules: Module policy with configured modules and sections.
            repository_name: Name of the repository.
            accepted_commits: Classified commits to include.
            task_patterns: Optional task pattern regexes.
            database_matches: Optional database change matches. If empty, database_change_section is None.
        
        Returns:
            ReleaseDocument with optional DatabaseChangeSection.
        """
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

        # Extract task references
        task_references = self.extract_task_references(commits, task_patterns)
        task_section: Optional[TaskReferenceSection] = None
        if task_references:
            task_section = TaskReferenceSection(references=task_references)

        # Build database change section from matches
        database_change_section: Optional[DatabaseChangeSection] = None
        if database_matches:
            # Group matches by module name in configured module order
            module_order = {mod.name: idx for idx, mod in enumerate(modules.modules)}
            groups_by_module: dict[str, list[DatabaseChangeEntry]] = {}
            
            for match in database_matches:
                module_name = match.commit.module_name
                if module_name not in groups_by_module:
                    groups_by_module[module_name] = []
                groups_by_module[module_name].append(
                    DatabaseChangeEntry(
                        subject=match.commit.subject,
                        commit_hash=match.commit.commit_hash,
                        matched_paths=match.matched_paths,
                    )
                )
            
            # Build groups in configured module order
            ordered_groups = tuple(
                DatabaseChangeModuleGroup(
                    name=module_name,
                    entries=tuple(groups_by_module[module_name]),
                )
                for module_name in sorted(
                    groups_by_module.keys(),
                    key=lambda name: module_order.get(name, len(module_order)),
                )
            )
            
            if ordered_groups:
                database_change_section = DatabaseChangeSection(
                    title=DATABASE_CHANGES_SECTION_TITLE,
                    groups=ordered_groups,
                )

        change_start, change_end = _date_range(commits)
        return ReleaseDocument(
            title="Release Commit Report",
            repository_name=repository_name,
            qualifying_change_count=len(commits),
            change_start_date=change_start,
            change_end_date=change_end,
            sections=sections,
            task_reference_section=task_section,
            empty_message=None if sections else "No qualifying changes.",
            database_change_section=database_change_section,
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

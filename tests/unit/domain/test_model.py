import dataclasses
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from release_notes_generator.domain.analysis import AnalysisPaths, DiffArtifact
from release_notes_generator.domain.configuration import (
    ClaudeCodeAISettings,
    ContributorPolicy,
    ModuleDefinition,
    ModulePolicy,
    WorkflowConfiguration,
)
from release_notes_generator.domain.release_document import (
    DATABASE_CHANGES_SECTION_TITLE,
    DatabaseChangeEntry,
    DatabaseChangeModuleGroup,
    DatabaseChangeSection,
    ReleaseCommitEntry,
    ReleaseDocument,
    ReleaseModuleCommitList,
)
from release_notes_generator.domain.repository import RepositoryRelation, RepositoryStatus


class DomainModelTests(unittest.TestCase):
    def test_domain_values_are_immutable(self) -> None:
        artifact = DiffArtifact("Payments", Path("diff.md"))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            artifact.module_name = "Other"  # type: ignore[misc]

    def test_commit_entry_and_commit_list_module_are_immutable(self) -> None:
        entry = ReleaseCommitEntry(
            "Pix: committed feature",
            "0123456789abcdef0123456789abcdef01234567",
        )
        module = ReleaseModuleCommitList(
            "Pix",
            (entry,),
            qualifying_change_count=1,
            change_start_date=date(2026, 1, 3),
            change_end_date=date(2026, 1, 3),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            entry.subject = "changed"  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            module.commits = ()  # type: ignore[misc]

    def test_repository_status_exposes_pure_dirty_and_freshness_behavior(self) -> None:
        status = RepositoryStatus(
            staged_count=1,
            unstaged_count=0,
            untracked_count=0,
            branch="main",
            upstream="origin/main",
            upstream_resolved=True,
            relation=RepositoryRelation.EQUAL,
            ahead_count=0,
            behind_count=0,
            checkout_head_sha="abc",
            refreshed_refs=("refs/remotes/origin/main",),
            freshness_checked_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.assertTrue(status.is_dirty)
        self.assertEqual(
            status.freshness_for("refs/remotes/origin/main"), "fresh_as_of_fetch"
        )
        self.assertEqual(status.freshness_for("refs/remotes/origin/dev"), "unknown")

    def test_release_document_calculates_iso_year_weeks_without_dependencies(self) -> None:
        document = ReleaseDocument(
            "Release Notes",
            "repository",
            1,
            date(2025, 12, 29),
            date(2026, 1, 4),
            (),
        )
        self.assertEqual(document.change_start_iso_week, "2026-W01")
        self.assertEqual(document.change_end_iso_week, "2026-W01")

    def test_workflow_configuration_keeps_policies_and_settings_explicit(self) -> None:
        configuration = WorkflowConfiguration(
            repository_path=Path("/repo"),
            contributors=ContributorPolicy(("dev@example.com",)),
            modules=ModulePolicy((ModuleDefinition("Pay", ("PAY:",), "Payments"),)),
            ai=ClaudeCodeAISettings("sonnet", "Summarize.", 1000),
            temp_diff_dir=Path("/tmp/diffs"),
            output_path=Path("/tmp/release.pdf"),
            head_ref="main",
            base_ref="v1",
            release_marker=None,
        )
        self.assertEqual(configuration.modules.module_tags, {"Pay": ("PAY:",)})
        self.assertEqual(configuration.contributors.approved_author_emails, ("dev@example.com",))

    def test_database_change_section_title_equals_database_changes(self) -> None:
        section = DatabaseChangeSection()
        self.assertEqual(section.title, "Database Changes")
        self.assertEqual(section.title, DATABASE_CHANGES_SECTION_TITLE)

    def test_database_change_types_are_frozen(self) -> None:
        entry = DatabaseChangeEntry(
            subject="Pix: add feature",
            commit_hash="0123456789abcdef0123456789abcdef01234567",
            matched_paths=("vas/globalloyalty/database/PixDatabase.kt",),
        )
        group = DatabaseChangeModuleGroup(
            name="Pix",
            entries=(entry,),
        )
        section = DatabaseChangeSection(
            title="Database Changes",
            groups=(group,),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            entry.subject = "changed"  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            group.name = "Other"  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            section.title = "Other"  # type: ignore[misc]

    def test_release_document_with_existing_style_construction(self) -> None:
        document = ReleaseDocument(
            "Release Notes",
            "repository",
            1,
            date(2025, 12, 29),
            date(2026, 1, 4),
            (),
        )
        self.assertIsNone(document.database_change_section)

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from reportlab.platypus import Paragraph

from release_notes_generator.domain.release_document import (
    DatabaseChangeEntry,
    DatabaseChangeModuleGroup,
    DatabaseChangeSection,
    ReleaseCommitEntry,
    ReleaseDocument,
    ReleaseModuleCommitList,
    ReleaseModuleSummary,
    ReleaseSection,
    TaskReferenceSection,
    TaskReference,
)
from release_notes_generator.infrastructure.reportlab_pdf import (
    build_pdf_story,
    export_release_pdf,
)
from release_notes_generator.services.errors import PDFGenerationError


class PDFStoryTests(unittest.TestCase):
    def test_story_renders_exact_escaped_commit_bullet_with_monospaced_full_id(self) -> None:
        commit_hash = "0123456789abcdef" * 4
        subject = "Pix: protect <unsafe> & café ação"
        document = ReleaseDocument(
            title="Release Commit Report",
            repository_name="payments <core> & services",
            qualifying_change_count=1,
            change_start_date=date(2026, 1, 3),
            change_end_date=date(2026, 1, 3),
            sections=(
                ReleaseSection(
                    title="Payments & Transfers",
                    modules=(
                        ReleaseModuleCommitList(
                            "Pix",
                            (ReleaseCommitEntry(subject, commit_hash),),
                            qualifying_change_count=1,
                            change_start_date=date(2026, 1, 3),
                            change_end_date=date(2026, 1, 3),
                        ),
                    ),
                ),
            ),
        )

        story = build_pdf_story(document)

        paragraphs = [flowable for flowable in story if isinstance(flowable, Paragraph)]
        plain_text = [paragraph.getPlainText() for paragraph in paragraphs]
        commit_paragraph = next(
            paragraph
            for paragraph in paragraphs
            if getattr(paragraph, "bulletText", None) == "•"
        )
        self.assertEqual(plain_text[0], "Release Commit Report")
        self.assertIn("Repository: payments <core> & services", plain_text)
        self.assertIn("Qualifying changes: 1", plain_text)
        self.assertIn("Change dates (UTC): 2026-01-03", plain_text)
        self.assertIn("ISO weeks: 2026-W01", plain_text)
        self.assertIn("Payments & Transfers", plain_text)
        self.assertIn("Pix", plain_text)
        self.assertIn("1 qualifying change · 2026-01-03 (UTC)", plain_text)
        self.assertEqual(
            commit_paragraph.getPlainText(), f"{subject} — {commit_hash}"
        )
        self.assertIn("Pix: protect &lt;unsafe&gt; &amp; café ação", commit_paragraph.text)
        hash_fragments = [
            fragment
            for fragment in commit_paragraph.frags
            if getattr(fragment, "text", "") == commit_hash
        ]
        self.assertEqual(len(hash_fragments), 1)
        self.assertEqual(hash_fragments[0].fontName, "Courier")
        _, wrapped_height = commit_paragraph.wrap(120, 1000)
        self.assertGreater(wrapped_height, commit_paragraph.style.leading)

    def test_story_maps_context_structure_bullets_and_escaped_text(self) -> None:
        document = ReleaseDocument(
            title="Release <Notes>",
            repository_name="payments <core> & services",
            qualifying_change_count=3,
            change_start_date=date(2026, 1, 3),
            change_end_date=date(2026, 2, 2),
            sections=(
                ReleaseSection(
                    title="Customer & Global",
                    modules=(
                        ReleaseModuleSummary(
                            "Payments",
                            "- Added café payments\nA paragraph with <unsafe> & text.\n* Fixed ação.",
                            qualifying_change_count=2,
                            change_start_date=date(2026, 1, 3),
                            change_end_date=date(2026, 2, 2),
                        ),
                        ReleaseModuleSummary(
                            "Rewards",
                            "- Added points.",
                            qualifying_change_count=1,
                            change_start_date=date(2026, 1, 12),
                            change_end_date=date(2026, 1, 12),
                        ),
                    ),
                ),
            ),
        )

        story = build_pdf_story(document)

        paragraphs = [flowable for flowable in story if isinstance(flowable, Paragraph)]
        plain_text = [paragraph.getPlainText() for paragraph in paragraphs]
        bullet_text = [
            paragraph.getPlainText()
            for paragraph in paragraphs
            if getattr(paragraph, "bulletText", None) == "•"
        ]
        self.assertEqual(plain_text[0], "Release <Notes>")
        self.assertIn("Repository: payments <core> & services", plain_text)
        self.assertIn("Qualifying changes: 3", plain_text)
        self.assertIn("Change dates (UTC): 2026-01-03 – 2026-02-02", plain_text)
        self.assertIn("ISO weeks: 2026-W01 – 2026-W06", plain_text)
        self.assertIn("Customer & Global", plain_text)
        self.assertIn("Payments", plain_text)
        self.assertIn(
            "2 qualifying changes · 2026-01-03 – 2026-02-02 (UTC)",
            plain_text,
        )
        self.assertIn("Rewards", plain_text)
        self.assertIn("1 qualifying change · 2026-01-12 (UTC)", plain_text)
        self.assertIn("A paragraph with <unsafe> & text.", plain_text)
        self.assertEqual(
            bullet_text,
            ["Added café payments", "Fixed ação.", "Added points."],
        )
        self.assertTrue(
            any(
                "payments &lt;core&gt; &amp; services" in paragraph.text
                for paragraph in paragraphs
            )
        )
        self.assertTrue(
            any("&lt;unsafe&gt; &amp; text." in paragraph.text for paragraph in paragraphs)
        )

    def test_story_renders_descriptive_no_qualifying_changes_message(self) -> None:
        story = build_pdf_story(
            ReleaseDocument(
                title="Release Notes",
                repository_name="empty-repository",
                qualifying_change_count=0,
                change_start_date=None,
                change_end_date=None,
                sections=(),
                empty_message="No qualifying changes.",
            )
        )

        plain_text = [
            flowable.getPlainText()
            for flowable in story
            if isinstance(flowable, Paragraph)
        ]
        self.assertEqual(
            plain_text,
            [
                "Release Notes",
                "Repository: empty-repository",
                "Qualifying changes: 0",
                "No qualifying changes.",
            ],
        )
        self.assertFalse(any(text.startswith("Change dates") for text in plain_text))
        self.assertFalse(any(text.startswith("ISO weeks") for text in plain_text))


class PDFDatabaseChangeStoryTests(unittest.TestCase):
    """Tests for database changes section rendering (tasks 7.1-7.5)."""

    def test_path_style_is_registered_and_distinct_from_commit_style(self) -> None:
        """Task 7.1: Verify path style exists and is distinct from commit style."""
        from release_notes_generator.infrastructure.reportlab_pdf import _document_styles

        styles = _document_styles()

        self.assertIn("path", styles)
        self.assertIn("commit", styles)
        self.assertNotEqual(styles["path"], styles["commit"])
        self.assertEqual(styles["path"].fontName, "Courier")
        self.assertEqual(styles["commit"].fontName, "ReleaseNotesVera")

    def test_database_change_flowables_renders_heading_and_module_groups(self) -> None:
        """Task 7.2: Verify database changes section renders with heading and groups."""
        commit_hash = "abcdef0123456789" * 4
        document = ReleaseDocument(
            title="Release Commit Report",
            repository_name="payments",
            qualifying_change_count=2,
            change_start_date=date(2026, 1, 3),
            change_end_date=date(2026, 1, 3),
            sections=(
                ReleaseSection(
                    title="Payments",
                    modules=(
                        ReleaseModuleCommitList(
                            "Pix",
                            (ReleaseCommitEntry("Pix: add support", commit_hash),),
                            qualifying_change_count=1,
                            change_start_date=date(2026, 1, 3),
                            change_end_date=date(2026, 1, 3),
                        ),
                    ),
                ),
            ),
            database_change_section=DatabaseChangeSection(
                groups=(
                    DatabaseChangeModuleGroup(
                        name="Pix",
                        entries=(
                            DatabaseChangeEntry(
                                subject="Pix: add schema migration",
                                commit_hash=commit_hash,
                                matched_paths=("db/migrations/001.sql", "db/schema.sql"),
                            ),
                        ),
                    ),
                ),
            ),
        )

        story = build_pdf_story(document)
        paragraphs = [f for f in story if isinstance(f, Paragraph)]
        plain_text = [p.getPlainText() for p in paragraphs]

        self.assertIn("Database Changes", plain_text)
        self.assertIn("Pix", plain_text)
        commit_text = next(t for t in plain_text if "Pix: add schema migration" in t)
        self.assertIn(commit_hash, commit_text)
        self.assertIn("db/migrations/001.sql", plain_text)
        self.assertIn("db/schema.sql", plain_text)

    def test_database_change_flowables_renders_full_object_id(self) -> None:
        """Task 7.2: Verify full untruncated object ID is rendered."""
        commit_hash = "0123456789abcdef" * 4
        document = ReleaseDocument(
            title="Release Report",
            repository_name="repo",
            qualifying_change_count=1,
            change_start_date=date(2026, 1, 1),
            change_end_date=date(2026, 1, 1),
            sections=(
                ReleaseSection(
                    title="Main",
                    modules=(
                        ReleaseModuleCommitList(
                            "Core",
                            (ReleaseCommitEntry("Core: init", commit_hash),),
                            qualifying_change_count=1,
                            change_start_date=date(2026, 1, 1),
                            change_end_date=date(2026, 1, 1),
                        ),
                    ),
                ),
            ),
            database_change_section=DatabaseChangeSection(
                groups=(
                    DatabaseChangeModuleGroup(
                        name="Core",
                        entries=(
                            DatabaseChangeEntry(
                                subject="Core: update schema",
                                commit_hash=commit_hash,
                                matched_paths=("db/core.sql",),
                            ),
                        ),
                    ),
                ),
            ),
        )

        story = build_pdf_story(document)
        paragraphs = [f for f in story if isinstance(f, Paragraph)]

        commit_paragraph = next(
            p for p in paragraphs
            if "Core: update schema" in p.getPlainText()
        )

        hash_fragments = [
            frag for frag in commit_paragraph.frags
            if getattr(frag, "text", "") == commit_hash
        ]
        self.assertEqual(len(hash_fragments), 1)
        self.assertEqual(hash_fragments[0].fontName, "Courier")

    def test_database_change_flowables_order_groups_and_paths(self) -> None:
        """Task 7.2: Verify groups appear in order and paths in configured order."""
        commit_hash = "a" * 64
        document = ReleaseDocument(
            title="Release Report",
            repository_name="repo",
            qualifying_change_count=1,
            change_start_date=date(2026, 1, 1),
            change_end_date=date(2026, 1, 1),
            sections=(
                ReleaseSection(
                    title="Main",
                    modules=(
                        ReleaseModuleCommitList(
                            "Core",
                            (ReleaseCommitEntry("Core: init", commit_hash),),
                            qualifying_change_count=1,
                            change_start_date=date(2026, 1, 1),
                            change_end_date=date(2026, 1, 1),
                        ),
                    ),
                ),
            ),
            database_change_section=DatabaseChangeSection(
                groups=(
                    DatabaseChangeModuleGroup(
                        name="ModuleA",
                        entries=(
                            DatabaseChangeEntry(
                                subject="A: change 1",
                                commit_hash=commit_hash,
                                matched_paths=("path/a1.sql", "path/a2.sql"),
                            ),
                        ),
                    ),
                    DatabaseChangeModuleGroup(
                        name="ModuleB",
                        entries=(
                            DatabaseChangeEntry(
                                subject="B: change 1",
                                commit_hash=commit_hash,
                                matched_paths=("path/b1.sql",),
                            ),
                        ),
                    ),
                ),
            ),
        )

        story = build_pdf_story(document)
        paragraphs = [f for f in story if isinstance(f, Paragraph)]
        plain_text = [p.getPlainText() for p in paragraphs]

        module_a_idx = plain_text.index("ModuleA")
        module_b_idx = plain_text.index("ModuleB")
        self.assertLess(module_a_idx, module_b_idx)

        a1_idx = plain_text.index("path/a1.sql")
        a2_idx = plain_text.index("path/a2.sql")
        self.assertLess(a1_idx, a2_idx)

    def test_database_change_section_none_adds_no_flowables(self) -> None:
        """Task 7.3 & 7.4: Verify None database_change_section adds no flowables."""
        document = ReleaseDocument(
            title="Release Report",
            repository_name="repo",
            qualifying_change_count=0,
            change_start_date=None,
            change_end_date=None,
            sections=(
                ReleaseSection(
                    title="Main",
                    modules=(
                        ReleaseModuleCommitList(
                            "Core",
                            (ReleaseCommitEntry("Core: init", "c" * 64),),
                            qualifying_change_count=1,
                            change_start_date=date(2026, 1, 1),
                            change_end_date=date(2026, 1, 1),
                        ),
                    ),
                ),
            ),
            database_change_section=None,
        )

        story = build_pdf_story(document)
        paragraphs = [f for f in story if isinstance(f, Paragraph)]
        plain_text = [p.getPlainText() for p in paragraphs]

        self.assertNotIn("Database Changes", plain_text)

    def test_database_change_section_empty_groups_renders_nothing(self) -> None:
        """Task 7.4: Verify a section with no groups renders no heading or content."""
        document = ReleaseDocument(
            title="Release Report",
            repository_name="repo",
            qualifying_change_count=0,
            change_start_date=None,
            change_end_date=None,
            sections=(
                ReleaseSection(
                    title="Main",
                    modules=(
                        ReleaseModuleCommitList(
                            "Core",
                            (ReleaseCommitEntry("Core: init", "c" * 64),),
                            qualifying_change_count=1,
                            change_start_date=date(2026, 1, 1),
                            change_end_date=date(2026, 1, 1),
                        ),
                    ),
                ),
            ),
            database_change_section=DatabaseChangeSection(groups=()),
        )

        story = build_pdf_story(document)
        paragraphs = [f for f in story if isinstance(f, Paragraph)]
        plain_text = [p.getPlainText() for p in paragraphs]

        self.assertNotIn("Database Changes", plain_text)

    def test_database_change_escaping_and_font_safety(self) -> None:
        """Task 7.5: Verify escaping and font safety for special characters."""
        commit_hash = "b" * 64
        document = ReleaseDocument(
            title="Release Report",
            repository_name="repo",
            qualifying_change_count=1,
            change_start_date=date(2026, 1, 1),
            change_end_date=date(2026, 1, 1),
            sections=(
                ReleaseSection(
                    title="Main",
                    modules=(
                        ReleaseModuleCommitList(
                            "Core",
                            (ReleaseCommitEntry("Core: init", commit_hash),),
                            qualifying_change_count=1,
                            change_start_date=date(2026, 1, 1),
                            change_end_date=date(2026, 1, 1),
                        ),
                    ),
                ),
            ),
            database_change_section=DatabaseChangeSection(
                groups=(
                    DatabaseChangeModuleGroup(
                        name="DB <unsafe> & café",
                        entries=(
                            DatabaseChangeEntry(
                                subject="DB: fix <bug> & add ação",
                                commit_hash=commit_hash,
                                matched_paths=("db/path <special> & café.sql",),
                            ),
                        ),
                    ),
                ),
            ),
        )

        story = build_pdf_story(document)
        paragraphs = [f for f in story if isinstance(f, Paragraph)]
        plain_text = [p.getPlainText() for p in paragraphs]

        db_module_idx = plain_text.index("DB <unsafe> & café")
        self.assertGreater(db_module_idx, plain_text.index("Database Changes"))

        commit_paragraph = next(
            p for p in paragraphs if "DB: fix" in p.getPlainText()
        )
        self.assertIn("&lt;bug&gt;", commit_paragraph.text)
        self.assertIn("&amp;", commit_paragraph.text)
        self.assertIn("ação", commit_paragraph.text)
        self.assertIn("<bug>", commit_paragraph.getPlainText())

        path_paragraph = next(
            p for p in paragraphs if "db/path" in p.getPlainText()
        )
        self.assertIn("&lt;special&gt;", path_paragraph.text)
        self.assertIn("&amp;", path_paragraph.text)
        self.assertIn("café", path_paragraph.text)
        self.assertIn("<special>", path_paragraph.getPlainText())
        self.assertEqual(path_paragraph.style.fontName, "Courier")


class PDFExportTests(unittest.TestCase):
    def test_export_creates_parent_and_atomically_replaces_destination(self) -> None:
        document = _document()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "release.pdf"
            with patch(
                "release_notes_generator.infrastructure.reportlab_pdf.os.replace",
                wraps=os.replace,
            ) as replace:
                result = export_release_pdf(document, output_path)

            files = tuple(output_path.parent.iterdir())
            pdf_header = output_path.read_bytes()[:5]

        self.assertEqual(result, output_path)
        self.assertEqual(files, (output_path,))
        self.assertEqual(pdf_header, b"%PDF-")
        replace.assert_called_once()
        self.assertEqual(Path(replace.call_args.args[1]), output_path)

    def test_export_preserves_existing_destination_and_cleans_temp_on_render_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "release.pdf"
            output_path.write_bytes(b"existing-pdf")
            with patch(
                "release_notes_generator.infrastructure.reportlab_pdf.SimpleDocTemplate"
            ) as document_cls:
                document_cls.return_value.build.side_effect = RuntimeError("render failed")

                with self.assertRaises(PDFGenerationError) as error:
                    export_release_pdf(_document(), output_path)

            remaining_files = tuple(Path(temp_dir).iterdir())
            existing_content = output_path.read_bytes()

        self.assertIn("Unable to generate PDF", str(error.exception))
        self.assertEqual(existing_content, b"existing-pdf")
        self.assertEqual(remaining_files, (output_path,))

    def test_export_renders_commit_list_with_full_sha256_style_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "commit-list.pdf"

            result = export_release_pdf(_commit_list_document(), output_path)

            self.assertEqual(result, output_path)
            self.assertEqual(output_path.read_bytes()[:5], b"%PDF-")


def _document() -> ReleaseDocument:
    return ReleaseDocument(
        title="Release Notes",
        repository_name="payments",
        qualifying_change_count=1,
        change_start_date=date(2026, 1, 3),
        change_end_date=date(2026, 1, 3),
        sections=(
            ReleaseSection(
                title="Global Features",
                modules=(
                    ReleaseModuleSummary(
                        "Payments",
                        "- Added café support",
                        qualifying_change_count=1,
                        change_start_date=date(2026, 1, 3),
                        change_end_date=date(2026, 1, 3),
                    ),
                ),
            ),
        ),
    )


def _commit_list_document() -> ReleaseDocument:
    return ReleaseDocument(
        title="Release Commit Report",
        repository_name="payments",
        qualifying_change_count=1,
        change_start_date=date(2026, 1, 3),
        change_end_date=date(2026, 1, 3),
        sections=(
            ReleaseSection(
                title="Payments",
                modules=(
                    ReleaseModuleCommitList(
                        "Pix",
                        (
                            ReleaseCommitEntry(
                                "Pix: add café support", "abcdef0123456789" * 4
                            ),
                        ),
                        qualifying_change_count=1,
                        change_start_date=date(2026, 1, 3),
                        change_end_date=date(2026, 1, 3),
                    ),
                ),
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reportlab.platypus import Paragraph

from release_notes_generator.composition import (
    ReleaseDocument,
    ReleaseModuleSummary,
    ReleaseSection,
)
from release_notes_generator.pdf_export import (
    PDFGenerationError,
    build_pdf_story,
    export_release_pdf,
)


class PDFStoryTests(unittest.TestCase):
    def test_story_maps_document_structure_bullets_paragraphs_and_escaped_text(self) -> None:
        document = ReleaseDocument(
            title="Release <Notes>",
            sections=(
                ReleaseSection(
                    title="Customer & Global",
                    modules=(
                        ReleaseModuleSummary(
                            "Payments",
                            "- Added café payments\nA paragraph with <unsafe> & text.\n* Fixed ação.",
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
        self.assertIn("Customer & Global", plain_text)
        self.assertIn("Payments", plain_text)
        self.assertIn("A paragraph with <unsafe> & text.", plain_text)
        self.assertEqual(bullet_text, ["Added café payments", "Fixed ação."])
        self.assertTrue(
            any("&lt;unsafe&gt; &amp; text." in paragraph.text for paragraph in paragraphs)
        )

    def test_story_renders_no_qualifying_changes_message(self) -> None:
        story = build_pdf_story(
            ReleaseDocument(
                title="Release Notes",
                sections=(),
                empty_message="No qualifying changes.",
            )
        )

        plain_text = [
            flowable.getPlainText()
            for flowable in story
            if isinstance(flowable, Paragraph)
        ]
        self.assertEqual(plain_text, ["Release Notes", "No qualifying changes."])


class PDFExportTests(unittest.TestCase):
    def test_export_creates_parent_and_atomically_replaces_destination(self) -> None:
        document = _document()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "release.pdf"
            with patch("release_notes_generator.pdf_export.os.replace", wraps=os.replace) as replace:
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
            with patch("release_notes_generator.pdf_export.SimpleDocTemplate") as document_cls:
                document_cls.return_value.build.side_effect = RuntimeError("render failed")

                with self.assertRaises(PDFGenerationError) as error:
                    export_release_pdf(_document(), output_path)

            remaining_files = tuple(Path(temp_dir).iterdir())
            existing_content = output_path.read_bytes()

        self.assertIn("Unable to generate PDF", str(error.exception))
        self.assertEqual(existing_content, b"existing-pdf")
        self.assertEqual(remaining_files, (output_path,))


def _document() -> ReleaseDocument:
    return ReleaseDocument(
        title="Release Notes",
        sections=(
            ReleaseSection(
                title="Global Features",
                modules=(
                    ReleaseModuleSummary("Payments", "- Added café support"),
                ),
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()

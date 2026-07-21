"""PDF rendering and atomic export for structured release notes."""

from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path
from typing import List

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from release_notes_generator.composition import ReleaseDocument


class PDFGenerationError(RuntimeError):
    """Raised when the final release-notes PDF cannot be generated."""


_FONT_REGULAR = "ReleaseNotesVera"
_FONT_BOLD = "ReleaseNotesVeraBold"
_FONT_ITALIC = "ReleaseNotesVeraItalic"
_FONT_BOLD_ITALIC = "ReleaseNotesVeraBoldItalic"


def build_pdf_story(document: ReleaseDocument) -> List[Flowable]:
    """Map the supported release-document structure to ReportLab flowables."""
    _register_fonts()
    styles = _document_styles()
    story: List[Flowable] = [
        Paragraph(html.escape(document.title), styles["title"]),
        Spacer(1, 3 * mm),
        Paragraph(
            html.escape(f"Repository: {document.repository_name}"),
            styles["metadata"],
        ),
        Paragraph(
            html.escape(f"Qualifying changes: {document.qualifying_change_count}"),
            styles["metadata"],
        ),
    ]

    if document.change_start_date is not None and document.change_end_date is not None:
        story.append(
            Paragraph(
                html.escape(
                    "Change dates (UTC): "
                    f"{_format_range(document.change_start_date, document.change_end_date)}"
                ),
                styles["metadata"],
            )
        )
    if (
        document.change_start_iso_week is not None
        and document.change_end_iso_week is not None
    ):
        story.append(
            Paragraph(
                html.escape(
                    "ISO weeks: "
                    f"{_format_range(document.change_start_iso_week, document.change_end_iso_week)}"
                ),
                styles["metadata"],
            )
        )
    story.append(Spacer(1, 8 * mm))

    if not document.sections:
        if document.empty_message:
            story.append(Paragraph(html.escape(document.empty_message), styles["body"]))
        return story

    for section in document.sections:
        story.append(Paragraph(html.escape(section.title), styles["section"]))
        story.append(Spacer(1, 3 * mm))
        for module in section.modules:
            story.append(Paragraph(html.escape(module.name), styles["module"]))
            change_label = (
                "qualifying change"
                if module.qualifying_change_count == 1
                else "qualifying changes"
            )
            module_context = (
                f"{module.qualifying_change_count} {change_label} · "
                f"{_format_range(module.change_start_date, module.change_end_date)} (UTC)"
            )
            story.append(
                Paragraph(html.escape(module_context), styles["module_context"])
            )
            story.extend(_summary_flowables(module.summary, styles))
            story.append(Spacer(1, 3 * mm))
        story.append(Spacer(1, 3 * mm))
    return story


def export_release_pdf(document: ReleaseDocument, output_path: Path) -> Path:
    """Render a PDF beside its destination and atomically replace the output."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)

    try:
        pdf = SimpleDocTemplate(
            str(temporary_path),
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=document.title,
        )
        pdf.build(build_pdf_story(document))
        if temporary_path.read_bytes()[:5] != b"%PDF-":
            raise PDFGenerationError("Generated output was not a PDF document.")
        os.replace(temporary_path, path)
    except Exception as exc:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        if isinstance(exc, PDFGenerationError):
            raise
        raise PDFGenerationError(f"Unable to generate PDF: {path}") from exc

    return path


def _summary_flowables(
    summary: str,
    styles: dict[str, ParagraphStyle],
) -> List[Flowable]:
    flowables: List[Flowable] = []
    for raw_line in summary.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ")):
            flowables.append(
                Paragraph(
                    html.escape(line[2:].strip()),
                    styles["bullet"],
                    bulletText="•",
                )
            )
        else:
            flowables.append(Paragraph(html.escape(line), styles["body"]))
    return flowables


def _register_fonts() -> None:
    if _FONT_REGULAR in pdfmetrics.getRegisteredFontNames():
        return
    font_dir = Path(reportlab.__file__).resolve().parent / "fonts"
    pdfmetrics.registerFont(TTFont(_FONT_REGULAR, str(font_dir / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(font_dir / "VeraBd.ttf")))
    pdfmetrics.registerFont(TTFont(_FONT_ITALIC, str(font_dir / "VeraIt.ttf")))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD_ITALIC, str(font_dir / "VeraBI.ttf")))
    pdfmetrics.registerFontFamily(
        _FONT_REGULAR,
        normal=_FONT_REGULAR,
        bold=_FONT_BOLD,
        italic=_FONT_ITALIC,
        boldItalic=_FONT_BOLD_ITALIC,
    )


def _document_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReleaseTitle",
            parent=sample["Title"],
            fontName=_FONT_BOLD,
            alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "ReleaseSection",
            parent=sample["Heading1"],
            fontName=_FONT_BOLD,
        ),
        "module": ParagraphStyle(
            "ReleaseModule",
            parent=sample["Heading2"],
            fontName=_FONT_BOLD,
        ),
        "metadata": ParagraphStyle(
            "ReleaseMetadata",
            parent=sample["BodyText"],
            fontName=_FONT_REGULAR,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#425466"),
            spaceAfter=2,
        ),
        "module_context": ParagraphStyle(
            "ReleaseModuleContext",
            parent=sample["BodyText"],
            fontName=_FONT_ITALIC,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#5B6675"),
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "ReleaseBody",
            parent=sample["BodyText"],
            fontName=_FONT_REGULAR,
            leading=14,
            spaceAfter=5,
        ),
        "bullet": ParagraphStyle(
            "ReleaseBullet",
            parent=sample["BodyText"],
            fontName=_FONT_REGULAR,
            leftIndent=12,
            firstLineIndent=0,
            bulletIndent=0,
            leading=14,
            spaceAfter=4,
        ),
    }


def _format_range(start: object, end: object) -> str:
    if start == end:
        return str(start)
    return f"{start} – {end}"

"""Final Markdown release-notes composition."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


GLOBAL_FEATURE_MODULES = ("GlobalLoyalty", "TransitOpenLoop")
PIX_MODULE = "Pix"


def compose_release_notes(summaries: Mapping[str, str]) -> str:
    """Compose AI-generated module summaries into the final release notes Markdown."""
    global_feature_summaries = []
    for module_name in GLOBAL_FEATURE_MODULES:
        summary = summaries.get(module_name, "").strip()
        if summary:
            global_feature_summaries.append(summary)
    pix_summary = summaries.get(PIX_MODULE, "").strip()

    sections = [
        "# Release Notes",
        "",
        "## Global Features",
        "",
        *_join_section_summaries(global_feature_summaries),
        "## Pix",
        "",
        pix_summary,
    ]
    return "\n".join(sections).rstrip() + "\n"


def export_release_notes(summaries: Mapping[str, str], output_path: Path) -> Path:
    """Write the final release notes Markdown to one explicit output file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(compose_release_notes(summaries), encoding="utf-8")
    return path


def _join_section_summaries(summaries: list[str]) -> list[str]:
    if not summaries:
        return [""]
    lines: list[str] = []
    for summary in summaries:
        if lines:
            lines.append("")
        lines.append(summary)
    lines.append("")
    return lines

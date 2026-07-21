"""Output-independent structured release-notes composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from release_notes_generator.configuration import ModuleConfig


@dataclass(frozen=True)
class ReleaseModuleSummary:
    """One configured module and its generated summary."""

    name: str
    summary: str


@dataclass(frozen=True)
class ReleaseSection:
    """One configured release-notes section."""

    title: str
    modules: tuple[ReleaseModuleSummary, ...]


@dataclass(frozen=True)
class ReleaseDocument:
    """Ordered release-note content independent from an output format."""

    title: str
    sections: tuple[ReleaseSection, ...]
    empty_message: Optional[str] = None


def compose_release_document(
    summaries: Mapping[str, str],
    module_config: ModuleConfig,
) -> ReleaseDocument:
    """Compose configured module summaries into ordered, non-empty sections."""
    section_modules: dict[str, list[ReleaseModuleSummary]] = {}
    for module in module_config.modules:
        summary = summaries.get(module.name, "").strip()
        if not summary:
            continue
        section_modules.setdefault(module.section, []).append(
            ReleaseModuleSummary(module.name, summary)
        )

    sections = tuple(
        ReleaseSection(title, tuple(modules))
        for title, modules in section_modules.items()
    )
    return ReleaseDocument(
        title="Release Notes",
        sections=sections,
        empty_message=None if sections else "No qualifying changes.",
    )

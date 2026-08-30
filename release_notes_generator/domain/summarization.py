"""Immutable summarization results."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SummarizationProvenance:
    """Secret-free identity of a completed summarization backend."""

    backend: str
    model: str
    claude_code_version: Optional[str] = None


@dataclass(frozen=True)
class SummarizationOutcome:
    """Ordered module summaries and their execution provenance."""

    module_summaries: tuple[tuple[str, str], ...]
    provenance: Optional[SummarizationProvenance]

    @property
    def summaries(self) -> dict[str, str]:
        return dict(self.module_summaries)

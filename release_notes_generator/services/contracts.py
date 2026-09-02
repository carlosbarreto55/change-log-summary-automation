"""Narrow ports required by application services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence

from release_notes_generator.domain.analysis import AnalysisPaths, DiffArtifact
from release_notes_generator.domain.configuration import AISettings, WorkflowConfiguration
from release_notes_generator.domain.release_document import ReleaseDocument
from release_notes_generator.domain.repository import Commit, ReleaseRange, RepositoryStatus
from release_notes_generator.domain.summarization import SummarizationProvenance


class JSONReader(Protocol):
    def read_object(self, path: Path) -> Mapping[str, Any]:
        """Read one JSON object or raise a configuration error."""


class GitGateway(Protocol):
    def inspect(self, repository_path: Path, analysis_head_ref: str) -> RepositoryStatus:
        """Inspect checkout state without mutating it."""

    def update(
        self,
        repository_path: Path,
        configuration: WorkflowConfiguration,
        status: RepositoryStatus,
    ) -> RepositoryStatus:
        """Apply the configured repository update mode."""

    def resolve_release_range(
        self,
        repository_path: Path,
        head_ref: str,
        *,
        base_ref: Optional[str],
        release_marker: Optional[str],
    ) -> ReleaseRange:
        """Resolve and freeze both release boundaries."""

    def commits_in_range(
        self, repository_path: Path, release_range: ReleaseRange
    ) -> tuple[Commit, ...]:
        """Extract commits from a frozen range, oldest first."""

    def show(self, repository_path: Path, commit_hash: str) -> str:
        """Return the patch for one frozen commit hash."""

    def changed_files(self, repository_path: Path, commit_hash: str) -> tuple[str, ...]:
        """Return repository-relative paths changed by one frozen commit hash."""


class PathValidator(Protocol):
    def validate(self, configuration: WorkflowConfiguration) -> AnalysisPaths:
        """Validate configured paths without creating destinations."""

    def prepare(self, paths: AnalysisPaths) -> AnalysisPaths:
        """Create destinations and revalidate their identities."""

    def revalidate(self, paths: AnalysisPaths) -> AnalysisPaths:
        """Repeat containment checks immediately before export."""


class ArtifactStore(Protocol):
    def write_diff(self, directory: Path, module_name: str, content: str) -> DiffArtifact:
        """Write one module diff artifact."""

    def read_text(self, artifact: DiffArtifact) -> str:
        """Read one generated artifact."""

    def delete(self, artifacts: Sequence[DiffArtifact]) -> None:
        """Delete only the supplied generated artifacts."""


class SummaryClient(Protocol):
    def summarize(self, module_name: str, diff_content: str) -> str:
        """Summarize one bounded module diff payload."""

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        """Reduce bounded partial summaries for one module."""


class SummaryClientFactory(Protocol):
    def create(self, settings: AISettings, env_file: Optional[Path]) -> SummaryClient:
        """Create only the client selected by the settings."""


class ProvenanceSource(Protocol):
    def execution_provenance(self) -> SummarizationProvenance:
        """Return secret-free provenance for completed requests."""


class PDFExporter(Protocol):
    def export(self, document: ReleaseDocument, output_path: Path) -> Path:
        """Atomically export a release document to PDF."""

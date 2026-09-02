"""Manual dependency composition for the release-notes use case."""

from typing import Callable, Optional

from release_notes_generator.infrastructure.artifacts import LocalArtifactStore
from release_notes_generator.infrastructure.git import GitAdapter
from release_notes_generator.infrastructure.json_reader import FileJSONReader
from release_notes_generator.infrastructure.openai import SummaryClientFactoryAdapter
from release_notes_generator.infrastructure.path_safety import PathSafetyAdapter
from release_notes_generator.infrastructure.reportlab_pdf import ReportLabPDFExporter
from release_notes_generator.services.commit_selection import CommitSelectionService
from release_notes_generator.services.configuration import ConfigurationService
from release_notes_generator.services.contracts import SummaryClient
from release_notes_generator.services.database_changes import DatabaseChangeDetectionService
from release_notes_generator.services.diff_generation import DiffGenerationService
from release_notes_generator.services.release_document import ReleaseDocumentService
from release_notes_generator.services.release_notes import ReleaseNotesService
from release_notes_generator.services.repository_analysis import RepositoryAnalysisService
from release_notes_generator.services.summarization import SummarizationService


def compose_release_notes_service(
    summary_client: Optional[SummaryClient] = None,
    warning_handler: Optional[Callable[[str], None]] = None,
) -> ReleaseNotesService:
    """Wire concrete adapters to application services without a DI framework."""
    git = GitAdapter()
    artifacts = LocalArtifactStore()
    return ReleaseNotesService(
        configuration=ConfigurationService(FileJSONReader()),
        paths=PathSafetyAdapter(),
        repositories=RepositoryAnalysisService(git),
        commits=CommitSelectionService(),
        diffs=DiffGenerationService(git, artifacts),
        summarization=SummarizationService(
            artifacts, SummaryClientFactoryAdapter(), summary_client
        ),
        documents=ReleaseDocumentService(),
        pdf=ReportLabPDFExporter(),
        database_detection=DatabaseChangeDetectionService(git),
        warning_handler=warning_handler,
    )

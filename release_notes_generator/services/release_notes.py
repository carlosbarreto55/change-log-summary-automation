"""Release-notes generation use case."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from release_notes_generator.domain.configuration import ReportMode
from release_notes_generator.services.commit_selection import CommitSelectionService
from release_notes_generator.services.configuration import ConfigurationService
from release_notes_generator.services.contracts import PDFExporter, PathValidator
from release_notes_generator.services.diff_generation import DiffGenerationService
from release_notes_generator.services.errors import ConfigurationError
from release_notes_generator.services.release_document import (
    ReleaseDocumentService,
    build_task_patterns_from_config,
)
from release_notes_generator.services.repository_analysis import RepositoryAnalysisService
from release_notes_generator.services.summarization import SummarizationService


WORKFLOW_STEPS = (
    "load and validate all configuration",
    "validate external analysis paths",
    "inspect target repository",
    "apply selected repository update mode",
    "freeze release-range boundaries",
    "capture commits from frozen range",
    "filter and classify commits",
    "prepare validated report destinations",
    "produce configured report content",
    "compose configured release document",
    "revalidate and export final PDF report",
    "clean up report-specific temporary artifacts",
)


class ReleaseNotesService:
    """Application entry point for one configured release-notes run."""

    def __init__(
        self,
        configuration: ConfigurationService,
        paths: PathValidator,
        repositories: RepositoryAnalysisService,
        commits: CommitSelectionService,
        diffs: DiffGenerationService,
        summarization: SummarizationService,
        documents: ReleaseDocumentService,
        pdf: PDFExporter,
        warning_handler: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._configuration = configuration
        self._paths = paths
        self._repositories = repositories
        self._commits = commits
        self._diffs = diffs
        self._summarization = summarization
        self._documents = documents
        self._pdf = pdf
        self._warning_handler = warning_handler

    def step_names(self) -> list[str]:
        return list(WORKFLOW_STEPS)

    def generate(self, config_path: Path) -> Path:
        """Generate release notes and return the final PDF path."""
        configuration = self._configuration.load(config_path)
        if configuration.report_mode is ReportMode.AI_SUMMARY and (
            configuration.ai is None or configuration.temp_diff_dir is None
        ):
            raise ConfigurationError(
                "ai_summary mode requires AI settings and a temporary diff path."
            )
        paths = self._paths.validate(configuration)
        status = self._repositories.inspect(paths.repository_root, configuration.head_ref)
        status = self._repositories.update(paths.repository_root, configuration, status)
        if self._warning_handler is not None:
            for warning in status.warnings:
                self._warning_handler(warning)

        release_range = self._repositories.freeze_range(
            paths.repository_root, configuration
        )
        extracted = self._repositories.extract(paths.repository_root, release_range)
        accepted = self._commits.select(
            extracted, configuration.contributors, configuration.modules
        )

        if configuration.report_mode is ReportMode.COMMIT_LIST:
            paths = self._paths.prepare(paths)
            task_patterns = build_task_patterns_from_config(
                configuration.modules.task_patterns
            )
            document = self._documents.compose_commit_list(
                configuration.modules,
                paths.repository_root.name,
                accepted,
                task_patterns,
            )
            paths = self._paths.revalidate(paths)
            return self._pdf.export(document, paths.output_path)

        if configuration.report_mode is not ReportMode.AI_SUMMARY:
            raise ConfigurationError(
                f"Unsupported report mode: {configuration.report_mode!r}."
            )
        if paths.temp_diff_dir is None:
            raise ConfigurationError(
                "ai_summary mode requires AI settings and a temporary diff path."
            )

        grouped = self._commits.group(accepted)
        paths = self._paths.prepare(paths)

        artifacts = ()
        try:
            artifacts = self._diffs.generate(
                paths.repository_root, grouped, paths.temp_diff_dir
            )
            outcome = self._summarization.summarize(
                artifacts, configuration.ai, configuration.env_file_path
            )
            task_patterns = build_task_patterns_from_config(
                configuration.modules.task_patterns
            )
            document = self._documents.compose(
                outcome.summaries,
                configuration.modules,
                paths.repository_root.name,
                accepted,
                task_patterns,
            )
            paths = self._paths.revalidate(paths)
            return self._pdf.export(document, paths.output_path)
        finally:
            self._diffs.cleanup(artifacts)

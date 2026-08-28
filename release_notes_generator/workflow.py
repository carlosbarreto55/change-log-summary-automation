"""Runtime flow definition for release notes generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

from release_notes_generator.commits import (
    GitCommitExtractor,
    filter_commits,
    group_commit_hashes_by_module,
    inspect_repository,
    update_repository,
)
from release_notes_generator.composition import compose_release_document
from release_notes_generator.configuration import (
    load_ai_config,
    load_module_config,
    load_release_marker_config,
    load_runtime_config,
    load_user_config,
)
from release_notes_generator.diffs import delete_diff_files, generate_diff_files
from release_notes_generator.pdf_export import export_release_pdf
from release_notes_generator.repository_safety import validate_analysis_paths
from release_notes_generator.summarization import (
    SummaryClient,
    create_summary_client,
    summarize_diff_files_with_provenance,
)


@dataclass(frozen=True)
class WorkflowStep:
    """A named step in the release notes generation flow."""

    name: str


DEFAULT_WORKFLOW_STEPS: Tuple[WorkflowStep, ...] = (
    WorkflowStep("load runtime configuration"),
    WorkflowStep("load selected lower-boundary configuration"),
    WorkflowStep("load approved users"),
    WorkflowStep("load supported modules"),
    WorkflowStep("load AI settings"),
    WorkflowStep("validate external analysis paths"),
    WorkflowStep("inspect target repository"),
    WorkflowStep("apply selected repository update mode"),
    WorkflowStep("freeze release-range boundaries"),
    WorkflowStep("capture commits from frozen range"),
    WorkflowStep("filter commits by approved users"),
    WorkflowStep("classify commits by module tag"),
    WorkflowStep("discard unauthorized or unmapped commits"),
    WorkflowStep("group accepted commits by category"),
    WorkflowStep("prepare validated external destinations"),
    WorkflowStep("generate category diff files"),
    WorkflowStep("send category diffs to AI API"),
    WorkflowStep("receive category summaries"),
    WorkflowStep("compose configured release document"),
    WorkflowStep("export final PDF release notes"),
    WorkflowStep("delete temporary diff files"),
)


class ReleaseNotesWorkflow:
    """Coordinates the release notes generation flow."""

    def __init__(
        self,
        steps: Optional[Iterable[WorkflowStep]] = None,
        summary_client: Optional[SummaryClient] = None,
        warning_handler: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._steps = tuple(steps) if steps is not None else DEFAULT_WORKFLOW_STEPS
        self._summary_client = summary_client
        self._warning_handler = warning_handler

    def step_names(self) -> List[str]:
        """Return the configured runtime flow in execution order."""
        return [step.name for step in self._steps]

    def run(self, config_path: Path) -> int:
        """Execute the configured release notes workflow once."""
        runtime_config = load_runtime_config(config_path)
        release_marker_config = (
            load_release_marker_config(runtime_config.release_marker_config_path)
            if runtime_config.release_marker_config_path is not None
            else None
        )
        user_config = load_user_config(runtime_config.user_config_path)
        module_config = load_module_config(runtime_config.module_config_path)
        ai_config = load_ai_config(runtime_config.ai_config_path)

        analysis_paths = validate_analysis_paths(
            repository_path=runtime_config.repository_path,
            temp_diff_dir=runtime_config.temp_diff_dir,
            output_path=runtime_config.output_path,
            repository_update_mode=runtime_config.repository_update_mode,
        )
        repository_status = inspect_repository(
            analysis_paths.repository_root,
            runtime_config.head_ref,
        )
        repository_status = update_repository(
            analysis_paths.repository_root,
            runtime_config.repository_update_mode.value,
            status=repository_status,
            remote=runtime_config.refresh_remote,
            refspecs=runtime_config.refresh_refspecs,
        )
        if self._warning_handler is not None:
            for warning in repository_status.warnings:
                self._warning_handler(warning)

        extractor = GitCommitExtractor(analysis_paths.repository_root)
        release_range = extractor.resolve_release_range(
            runtime_config.head_ref,
            base_ref=runtime_config.base_ref,
            release_marker=(
                release_marker_config.marker
                if release_marker_config is not None
                else None
            ),
        )
        commits = extractor.commits_in_range(release_range)
        accepted_commits = filter_commits(
            commits,
            user_config.approved_author_emails,
            module_config.module_tags,
        )
        grouped_commit_hashes = group_commit_hashes_by_module(accepted_commits)
        analysis_paths.prepare()
        diff_files = {}
        try:
            diff_files = generate_diff_files(
                analysis_paths.repository_root,
                grouped_commit_hashes,
                analysis_paths.temp_diff_dir,
            )

            summaries = {}
            if diff_files:
                client = self._summary_client or create_summary_client(
                    ai_config,
                    env_file=runtime_config.env_file_path,
                )
                summarization_outcome = summarize_diff_files_with_provenance(
                    diff_files,
                    client,
                    ai_config.max_diff_characters_per_request,
                )
                summaries = summarization_outcome.summaries

            document = compose_release_document(
                summaries,
                module_config,
                repository_name=analysis_paths.repository_root.name,
                accepted_commits=accepted_commits,
            )
            analysis_paths.revalidate()
            export_release_pdf(document, analysis_paths.output_path)
        finally:
            delete_diff_files(diff_files.values())
        return 0

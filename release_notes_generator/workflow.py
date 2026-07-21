"""Runtime flow definition for release notes generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from release_notes_generator.commits import (
    GitCommitExtractor,
    filter_commits,
    group_commit_hashes_by_module,
    synchronize_repository,
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
from release_notes_generator.summarization import (
    OpenAIChatClient,
    SummaryClient,
    summarize_diff_files,
)


@dataclass(frozen=True)
class WorkflowStep:
    """A named step in the release notes generation flow."""

    name: str


DEFAULT_WORKFLOW_STEPS: Tuple[WorkflowStep, ...] = (
    WorkflowStep("load runtime configuration"),
    WorkflowStep("load release marker"),
    WorkflowStep("load approved users"),
    WorkflowStep("load supported modules"),
    WorkflowStep("load AI settings"),
    WorkflowStep("synchronize target repository"),
    WorkflowStep("locate release marker"),
    WorkflowStep("capture commits after release marker"),
    WorkflowStep("filter commits by approved users"),
    WorkflowStep("classify commits by module tag"),
    WorkflowStep("discard unauthorized or unmapped commits"),
    WorkflowStep("group accepted commits by category"),
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
    ) -> None:
        self._steps = tuple(steps) if steps is not None else DEFAULT_WORKFLOW_STEPS
        self._summary_client = summary_client

    def step_names(self) -> List[str]:
        """Return the configured runtime flow in execution order."""
        return [step.name for step in self._steps]

    def run(self, config_path: Path) -> int:
        """Execute the configured release notes workflow once."""
        runtime_config = load_runtime_config(config_path)
        release_marker_config = load_release_marker_config(
            runtime_config.release_marker_config_path
        )
        user_config = load_user_config(runtime_config.user_config_path)
        module_config = load_module_config(runtime_config.module_config_path)
        ai_config = load_ai_config(runtime_config.ai_config_path)

        synchronize_repository(runtime_config.repository_path)

        commits = GitCommitExtractor(
            runtime_config.repository_path
        ).commits_after_latest_release_marker(release_marker_config.marker)
        accepted_commits = filter_commits(
            commits,
            user_config.approved_author_emails,
            module_config.module_tags,
        )
        grouped_commit_hashes = group_commit_hashes_by_module(accepted_commits)
        diff_files = generate_diff_files(
            runtime_config.repository_path,
            grouped_commit_hashes,
            runtime_config.temp_diff_dir,
        )

        summaries = {}
        if diff_files:
            client = self._summary_client or OpenAIChatClient.from_config(
                ai_config,
                env_file=runtime_config.env_file_path,
            )
            summaries = summarize_diff_files(
                diff_files,
                client,
                ai_config.max_diff_characters_per_request,
            )

        document = compose_release_document(
            summaries,
            module_config,
            repository_name=runtime_config.repository_path.name,
            accepted_commits=accepted_commits,
        )
        export_release_pdf(document, runtime_config.output_path)
        delete_diff_files(diff_files.values())
        return 0

"""Repository inspection, update, range freezing, and commit extraction."""

from pathlib import Path

from release_notes_generator.domain.configuration import WorkflowConfiguration
from release_notes_generator.domain.repository import Commit, ReleaseRange, RepositoryStatus
from release_notes_generator.services.contracts import GitGateway


class RepositoryAnalysisService:
    """Orchestrate repository operations through a Git port."""

    def __init__(self, git: GitGateway) -> None:
        self._git = git

    def inspect(
        self, repository_path: Path, analysis_head_ref: str
    ) -> RepositoryStatus:
        return self._git.inspect(repository_path, analysis_head_ref)

    def update(
        self,
        repository_path: Path,
        configuration: WorkflowConfiguration,
        status: RepositoryStatus,
    ) -> RepositoryStatus:
        return self._git.update(repository_path, configuration, status)

    def freeze_range(
        self, repository_path: Path, configuration: WorkflowConfiguration
    ) -> ReleaseRange:
        return self._git.resolve_release_range(
            repository_path,
            configuration.head_ref,
            base_ref=configuration.base_ref,
            release_marker=configuration.release_marker,
        )

    def extract(
        self, repository_path: Path, release_range: ReleaseRange
    ) -> tuple[Commit, ...]:
        return self._git.commits_in_range(repository_path, release_range)

"""Ordered per-module diff generation."""

from pathlib import Path
from typing import Mapping, Sequence

from release_notes_generator.domain.analysis import DiffArtifact
from release_notes_generator.services.contracts import ArtifactStore, GitGateway
from release_notes_generator.services.errors import DiffGenerationError


class DiffGenerationService:
    """Retrieve frozen commits in order and persist temporary module artifacts."""

    def __init__(self, git: GitGateway, artifacts: ArtifactStore) -> None:
        self._git = git
        self._artifacts = artifacts

    def generate(
        self,
        repository_path: Path,
        grouped_commit_hashes: Mapping[str, Sequence[str]],
        output_dir: Path,
    ) -> tuple[DiffArtifact, ...]:
        generated: list[DiffArtifact] = []
        try:
            for module_name, commit_hashes in grouped_commit_hashes.items():
                if not commit_hashes:
                    continue
                outputs = [
                    self._git.show(repository_path, commit_hash)
                    for commit_hash in commit_hashes
                ]
                generated.append(
                    self._artifacts.write_diff(
                        output_dir,
                        module_name,
                        _join_diff_outputs(outputs),
                    )
                )
        except DiffGenerationError:
            self._artifacts.delete(generated)
            raise
        except Exception as exc:
            self._artifacts.delete(generated)
            raise DiffGenerationError("Unable to generate temporary diff files.") from exc
        return tuple(generated)

    def cleanup(self, artifacts: Sequence[DiffArtifact]) -> None:
        self._artifacts.delete(artifacts)


def _join_diff_outputs(diff_outputs: Sequence[str]) -> str:
    return "\n\n".join(output.rstrip("\n") for output in diff_outputs) + "\n"

"""Local temporary diff-artifact storage."""

from pathlib import Path
from typing import Sequence

from release_notes_generator.domain.analysis import DiffArtifact
from release_notes_generator.services.errors import DiffGenerationError


class LocalArtifactStore:
    """Persist and delete only explicitly generated module diff files."""

    def write_diff(
        self, directory: Path, module_name: str, content: str
    ) -> DiffArtifact:
        output_dir = Path(directory)
        path = output_dir / _diff_file_name(module_name)
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            try:
                path.unlink()
            except OSError:
                pass
            raise DiffGenerationError(
                f"Unable to write temporary diff files under: {output_dir}"
            ) from exc
        return DiffArtifact(module_name, path)

    def read_text(self, artifact: DiffArtifact) -> str:
        return artifact.path.read_text(encoding="utf-8")

    def delete(self, artifacts: Sequence[DiffArtifact]) -> None:
        for artifact in artifacts:
            try:
                artifact.path.unlink()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise DiffGenerationError(
                    f"Unable to delete temporary diff file: {artifact.path}"
                ) from exc


def _diff_file_name(module_name: str) -> str:
    safe_name = "".join(
        character.lower() if character.isascii() and character.isalnum() else "_"
        for character in module_name
    ).strip("_")
    if not safe_name:
        raise DiffGenerationError(
            "Module name cannot be converted into a diff file name."
        )
    return f"diff_{safe_name}.md"

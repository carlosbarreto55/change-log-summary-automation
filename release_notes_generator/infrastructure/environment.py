"""Environment-file adapter that never mutates the process environment."""

from pathlib import Path
from typing import Optional

from release_notes_generator.services.errors import AISummarizationError


class EnvironmentFileAdapter:
    """Read simple KEY=VALUE entries from an optional local file."""

    def load(self, env_file_path: Optional[Path]) -> dict[str, str]:
        if env_file_path is None:
            return {}
        path = Path(env_file_path)
        if not path.exists():
            return {}
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise AISummarizationError(f"Unable to read env file: {path}") from exc

        values: dict[str, str] = {}
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            if key:
                values[key] = value.strip().strip('"').strip("'")
        return values

"""JSON object reader adapter."""

import json
from pathlib import Path
from typing import Any, Mapping

from release_notes_generator.services.errors import ConfigurationError


class FileJSONReader:
    """Read UTF-8 JSON objects from the local filesystem."""

    def read_object(self, path: Path) -> Mapping[str, Any]:
        config_path = Path(path)
        try:
            with config_path.open(encoding="utf-8") as config_file:
                data = json.load(config_file)
        except OSError as exc:
            raise ConfigurationError(
                f"Unable to read configuration file: {config_path}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                f"Invalid JSON configuration file: {config_path}"
            ) from exc
        if not isinstance(data, dict):
            raise ConfigurationError("Configuration file must contain a JSON object.")
        return data

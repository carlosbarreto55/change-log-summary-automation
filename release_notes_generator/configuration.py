"""JSON configuration loading for the release notes workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from release_notes_generator.paths import (
    DEFAULT_MODULE_CONFIG_PATH,
    DEFAULT_RELEASE_MARKER_CONFIG_PATH,
    DEFAULT_USER_CONFIG_PATH,
)


class ConfigurationError(ValueError):
    """Raised when a JSON configuration file cannot be loaded or used."""


@dataclass(frozen=True)
class UserConfig:
    """Approved users loaded from JSON configuration."""

    approved_author_emails: tuple[str, ...]


@dataclass(frozen=True)
class ModuleConfig:
    """Supported module tags loaded from JSON configuration."""

    module_tags: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class ReleaseMarkerConfig:
    """Release marker settings loaded from JSON configuration."""

    marker: str


def load_user_config(config_path: Path = DEFAULT_USER_CONFIG_PATH) -> UserConfig:
    """Load approved author emails from the users JSON file."""
    data = _load_json_object(config_path)
    emails = data.get("approved_author_emails")
    if not _is_string_list(emails):
        raise ConfigurationError(
            "Users configuration must define approved_author_emails as a list of strings."
        )
    return UserConfig(approved_author_emails=tuple(emails))


def load_module_config(config_path: Path = DEFAULT_MODULE_CONFIG_PATH) -> ModuleConfig:
    """Load supported module tags from the modules JSON file."""
    data = _load_json_object(config_path)
    modules = data.get("modules")
    if not isinstance(modules, list):
        raise ConfigurationError("Modules configuration must define modules as a list.")

    module_tags: dict[str, tuple[str, ...]] = {}
    for module in modules:
        if not isinstance(module, dict):
            raise ConfigurationError("Each module configuration entry must be an object.")

        name = module.get("name")
        tags = module.get("tags")
        if not isinstance(name, str) or not name:
            raise ConfigurationError("Each module configuration entry must define a name.")
        if not _is_string_list(tags):
            raise ConfigurationError(
                "Each module configuration entry must define tags as a list of strings."
            )

        module_tags[name] = tuple(tags)

    return ModuleConfig(module_tags=module_tags)


def load_release_marker_config(
    config_path: Path = DEFAULT_RELEASE_MARKER_CONFIG_PATH,
) -> ReleaseMarkerConfig:
    """Load the commit-message marker that identifies releases."""
    data = _load_json_object(config_path)
    marker = data.get("marker")
    if not isinstance(marker, str) or not marker:
        raise ConfigurationError("Release marker configuration must define a marker string.")
    return ReleaseMarkerConfig(marker=marker)


def _load_json_object(config_path: Path) -> dict[str, Any]:
    path = Path(config_path)
    try:
        with path.open(encoding="utf-8") as config_file:
            data = json.load(config_file)
    except OSError as exc:
        raise ConfigurationError(f"Unable to read configuration file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON configuration file: {path}") from exc

    if not isinstance(data, dict):
        raise ConfigurationError("Configuration file must contain a JSON object.")
    return data


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)

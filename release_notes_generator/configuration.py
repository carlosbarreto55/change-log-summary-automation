"""JSON configuration loading for the release notes workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from release_notes_generator.paths import (
    DEFAULT_AI_CONFIG_PATH,
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


@dataclass(frozen=True)
class AIConfig:
    """AI API settings loaded from JSON configuration without secret values."""

    api_url: str
    model: str
    api_key_env_var: str
    prompt: str


@dataclass(frozen=True)
class RuntimeConfig:
    """End-to-end workflow paths loaded from one runtime JSON file."""

    repository_path: Path
    user_config_path: Path
    module_config_path: Path
    release_marker_config_path: Path
    ai_config_path: Path
    temp_diff_dir: Path
    output_path: Path
    env_file_path: Optional[Path] = None


def load_runtime_config(config_path: Path) -> RuntimeConfig:
    """Load the end-to-end workflow configuration from one JSON file."""
    path = Path(config_path).expanduser()
    data = _load_json_object(path)
    base_dir = path.resolve(strict=False).parent

    output_path = _required_path(data, "output_path", base_dir)
    if output_path.suffix.lower() != ".md":
        raise ConfigurationError("Runtime configuration output_path must be a .md file.")

    return RuntimeConfig(
        repository_path=_required_path(data, "repository_path", base_dir),
        user_config_path=_required_path(data, "user_config_path", base_dir),
        module_config_path=_required_path(data, "module_config_path", base_dir),
        release_marker_config_path=_required_path(
            data,
            "release_marker_config_path",
            base_dir,
        ),
        ai_config_path=_required_path(data, "ai_config_path", base_dir),
        temp_diff_dir=_required_path(data, "temp_diff_dir", base_dir),
        output_path=output_path,
        env_file_path=_optional_path(data, "env_file_path", base_dir),
    )


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


def load_ai_config(config_path: Path = DEFAULT_AI_CONFIG_PATH) -> AIConfig:
    """Load AI API settings from JSON while keeping secrets in the environment."""
    data = _load_json_object(config_path)
    if "api_key" in data:
        raise ConfigurationError(
            "AI configuration must reference api_key_env_var instead of storing api_key."
        )

    api_url = data.get("api_url")
    model = data.get("model")
    api_key_env_var = data.get("api_key_env_var")
    prompt = data.get("prompt")
    if not isinstance(api_url, str) or not api_url:
        raise ConfigurationError("AI configuration must define an api_url string.")
    if not isinstance(model, str) or not model:
        raise ConfigurationError("AI configuration must define a model string.")
    if not isinstance(api_key_env_var, str) or not api_key_env_var:
        raise ConfigurationError("AI configuration must define an api_key_env_var string.")
    if not isinstance(prompt, str) or not prompt:
        raise ConfigurationError("AI configuration must define a prompt string.")

    return AIConfig(
        api_url=api_url,
        model=model,
        api_key_env_var=api_key_env_var,
        prompt=prompt,
    )


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


def _required_path(data: Mapping[str, Any], field_name: str, base_dir: Path) -> Path:
    value = data.get(field_name)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(
            f"Runtime configuration must define {field_name} as a string."
        )
    return _resolve_path(value, base_dir)


def _optional_path(data: Mapping[str, Any], field_name: str, base_dir: Path) -> Optional[Path]:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ConfigurationError(
            f"Runtime configuration {field_name} must be a string when provided."
        )
    return _resolve_path(value, base_dir)


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve(strict=False)
    return (base_dir / path).resolve(strict=False)

"""JSON configuration loading for the release notes workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from release_notes_generator.paths import (
    DEFAULT_AI_CONFIG_PATH,
    DEFAULT_MODULE_CONFIG_PATH,
    DEFAULT_RELEASE_MARKER_CONFIG_PATH,
    DEFAULT_USER_CONFIG_PATH,
)


class ConfigurationError(ValueError):
    """Raised when a JSON configuration file cannot be loaded or used."""


class RepositoryUpdateMode(str, Enum):
    """Supported repository update behavior before release analysis."""

    READ_ONLY = "read_only"
    REFRESH_REMOTE_REFS = "refresh_remote_refs"
    LEGACY_IN_PLACE_SYNC = "legacy_in_place_sync"


@dataclass(frozen=True)
class UserConfig:
    """Approved users loaded from JSON configuration."""

    approved_author_emails: tuple[str, ...]


@dataclass(frozen=True)
class ModuleDefinition:
    """One configured module and its release-notes section."""

    name: str
    tags: tuple[str, ...]
    section: str


@dataclass(frozen=True)
class ModuleConfig:
    """Ordered module definitions loaded from JSON configuration."""

    modules: tuple[ModuleDefinition, ...]

    @property
    def module_tags(self) -> Mapping[str, tuple[str, ...]]:
        """Return configured tags keyed by module name in configuration order."""
        return {module.name: module.tags for module in self.modules}


@dataclass(frozen=True)
class ReleaseMarkerConfig:
    """Release marker settings loaded from JSON configuration."""

    marker: str


class AIBackend(str, Enum):
    """Supported AI summarization backends selectable in JSON configuration."""

    OPENAI_COMPATIBLE = "openai_compatible"
    CLAUDE_CODE = "claude_code"


@dataclass(frozen=True)
class OpenAICompatibleAIConfig:
    """OpenAI-compatible AI settings loaded from JSON without secret values."""

    api_url: str
    model: str
    api_key_env_var: str
    prompt: str
    max_diff_characters_per_request: int

    @property
    def backend(self) -> AIBackend:
        return AIBackend.OPENAI_COMPATIBLE


@dataclass(frozen=True)
class ClaudeCodeAIConfig:
    """Keyless Claude Code AI settings loaded from JSON configuration."""

    model: str
    prompt: str
    max_diff_characters_per_request: int

    @property
    def backend(self) -> AIBackend:
        return AIBackend.CLAUDE_CODE


AIConfig = Union[OpenAICompatibleAIConfig, ClaudeCodeAIConfig]


@dataclass(frozen=True)
class RuntimeConfig:
    """End-to-end workflow paths loaded from one runtime JSON file."""

    repository_path: Path
    user_config_path: Path
    module_config_path: Path
    release_marker_config_path: Optional[Path]
    ai_config_path: Path
    temp_diff_dir: Path
    output_path: Path
    head_ref: str
    base_ref: Optional[str]
    repository_update_mode: RepositoryUpdateMode = RepositoryUpdateMode.READ_ONLY
    refresh_remote: Optional[str] = None
    refresh_refspecs: tuple[str, ...] = ()
    env_file_path: Optional[Path] = None


def load_runtime_config(config_path: Path) -> RuntimeConfig:
    """Load the end-to-end workflow configuration from one JSON file."""
    path = Path(config_path).expanduser()
    data = _load_json_object(path)
    base_dir = path.resolve(strict=False).parent

    head_ref = _required_non_blank_string(data, "head_ref")
    base_ref = _optional_non_blank_string(data, "base_ref")
    release_marker_config_path = _optional_selector_path(
        data,
        "release_marker_config_path",
        base_dir,
    )
    if (base_ref is None) == (release_marker_config_path is None):
        raise ConfigurationError(
            "Runtime configuration must define exactly one of base_ref or "
            "release_marker_config_path."
        )

    repository_update_mode = _repository_update_mode(data)
    refresh_remote, refresh_refspecs = _refresh_configuration(
        data,
        repository_update_mode,
    )

    output_path = _required_path(data, "output_path", base_dir)
    if output_path.suffix.lower() != ".pdf":
        raise ConfigurationError("Runtime configuration output_path must be a .pdf file.")

    return RuntimeConfig(
        repository_path=_required_path(data, "repository_path", base_dir),
        user_config_path=_required_path(data, "user_config_path", base_dir),
        module_config_path=_required_path(data, "module_config_path", base_dir),
        release_marker_config_path=release_marker_config_path,
        ai_config_path=_required_path(data, "ai_config_path", base_dir),
        temp_diff_dir=_required_path(data, "temp_diff_dir", base_dir),
        output_path=output_path,
        head_ref=head_ref,
        base_ref=base_ref,
        repository_update_mode=repository_update_mode,
        refresh_remote=refresh_remote,
        refresh_refspecs=refresh_refspecs,
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

    module_definitions: list[ModuleDefinition] = []
    for module in modules:
        if not isinstance(module, dict):
            raise ConfigurationError("Each module configuration entry must be an object.")

        name = module.get("name")
        tags = module.get("tags")
        section = module.get("section")
        if not isinstance(name, str) or not name:
            raise ConfigurationError("Each module configuration entry must define a name.")
        if not _is_non_empty_string_list(tags):
            raise ConfigurationError(
                "Each module configuration entry must define non-empty tags as a list of strings."
            )
        if not isinstance(section, str) or not section:
            raise ConfigurationError("Each module configuration entry must define a section.")

        module_definitions.append(ModuleDefinition(name, tuple(tags), section))

    return ModuleConfig(modules=tuple(module_definitions))


def load_release_marker_config(
    config_path: Path = DEFAULT_RELEASE_MARKER_CONFIG_PATH,
) -> ReleaseMarkerConfig:
    """Load the commit-message marker that identifies releases."""
    data = _load_json_object(config_path)
    marker = data.get("marker")
    if not isinstance(marker, str) or not marker.strip():
        raise ConfigurationError("Release marker configuration must define a marker string.")
    return ReleaseMarkerConfig(marker=marker)


def load_ai_config(config_path: Path = DEFAULT_AI_CONFIG_PATH) -> AIConfig:
    """Load backend-specific AI settings from JSON while keeping secrets outside it."""
    data = _load_json_object(config_path)
    if "api_key" in data:
        raise ConfigurationError(
            "AI configuration must reference api_key_env_var instead of storing api_key."
        )

    backend = _ai_backend(data)
    if backend is AIBackend.CLAUDE_CODE:
        return _claude_code_ai_config(data)
    return _openai_compatible_ai_config(data)


def _ai_backend(data: Mapping[str, Any]) -> AIBackend:
    value = data.get("backend", AIBackend.OPENAI_COMPATIBLE.value)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            "AI configuration backend must be a non-empty string when provided."
        )
    try:
        return AIBackend(value)
    except ValueError as exc:
        raise ConfigurationError(f"Unsupported AI configuration backend: {value}") from exc


def _openai_compatible_ai_config(data: Mapping[str, Any]) -> OpenAICompatibleAIConfig:
    api_url = data.get("api_url")
    api_key_env_var = data.get("api_key_env_var")
    if not isinstance(api_url, str) or not api_url:
        raise ConfigurationError("AI configuration must define an api_url string.")
    if not isinstance(api_key_env_var, str) or not api_key_env_var:
        raise ConfigurationError("AI configuration must define an api_key_env_var string.")

    model, prompt, max_diff_characters_per_request = _ai_model_prompt_and_limit(data)
    return OpenAICompatibleAIConfig(
        api_url=api_url,
        model=model,
        api_key_env_var=api_key_env_var,
        prompt=prompt,
        max_diff_characters_per_request=max_diff_characters_per_request,
    )


def _claude_code_ai_config(data: Mapping[str, Any]) -> ClaudeCodeAIConfig:
    for field_name in ("api_url", "api_key_env_var"):
        if field_name in data:
            raise ConfigurationError(
                f"AI configuration {field_name} is not valid for the claude_code backend."
            )

    model, prompt, max_diff_characters_per_request = _ai_model_prompt_and_limit(data)
    return ClaudeCodeAIConfig(
        model=model,
        prompt=prompt,
        max_diff_characters_per_request=max_diff_characters_per_request,
    )


def _ai_model_prompt_and_limit(data: Mapping[str, Any]) -> tuple[str, str, int]:
    model = data.get("model")
    prompt = data.get("prompt")
    max_diff_characters_per_request = data.get("max_diff_characters_per_request")
    if not isinstance(model, str) or not model:
        raise ConfigurationError("AI configuration must define a model string.")
    if not isinstance(prompt, str) or not prompt:
        raise ConfigurationError("AI configuration must define a prompt string.")
    if (
        isinstance(max_diff_characters_per_request, bool)
        or not isinstance(max_diff_characters_per_request, int)
        or max_diff_characters_per_request <= 0
    ):
        raise ConfigurationError(
            "AI configuration must define max_diff_characters_per_request "
            "as a positive integer."
        )
    return model, prompt, max_diff_characters_per_request


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


def _is_non_empty_string_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item) for item in value)
    )


def _required_non_blank_string(data: Mapping[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            f"Runtime configuration must define {field_name} as a non-empty string."
        )
    return value


def _optional_non_blank_string(
    data: Mapping[str, Any],
    field_name: str,
) -> Optional[str]:
    if field_name not in data:
        return None
    return _required_non_blank_string(data, field_name)


def _repository_update_mode(data: Mapping[str, Any]) -> RepositoryUpdateMode:
    value = data.get("repository_update_mode", RepositoryUpdateMode.READ_ONLY.value)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            "Runtime configuration repository_update_mode must be a non-empty string."
        )
    try:
        return RepositoryUpdateMode(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"Unknown repository_update_mode: {value}"
        ) from exc


def _refresh_configuration(
    data: Mapping[str, Any],
    repository_update_mode: RepositoryUpdateMode,
) -> tuple[Optional[str], tuple[str, ...]]:
    refresh_fields = ("refresh_remote", "refresh_refspecs")
    if repository_update_mode is not RepositoryUpdateMode.REFRESH_REMOTE_REFS:
        if any(field_name in data for field_name in refresh_fields):
            raise ConfigurationError(
                "Runtime configuration refresh fields are only valid for "
                "refresh_remote_refs mode."
            )
        return None, ()

    refresh_remote = _required_non_blank_string(data, "refresh_remote")
    refresh_refspecs = data.get("refresh_refspecs")
    if not isinstance(refresh_refspecs, list) or not refresh_refspecs:
        raise ConfigurationError(
            "Runtime configuration must define refresh_refspecs as a non-empty list."
        )

    destination_prefix = f"refs/remotes/{refresh_remote}/"
    for refspec in refresh_refspecs:
        if not isinstance(refspec, str) or not refspec.strip():
            raise ConfigurationError(
                "Runtime configuration refresh_refspecs must contain non-empty strings."
            )
        if refspec.count(":") != 1:
            raise ConfigurationError(
                "Each refresh refspec must define an explicit source:destination."
            )
        source, destination = refspec.split(":")
        source_without_force = source.removeprefix("+")
        if not source_without_force.strip() or not destination.strip():
            raise ConfigurationError(
                "Each refresh refspec must define a non-empty source and destination."
            )
        if not destination.startswith(destination_prefix):
            raise ConfigurationError(
                "Refresh refspec destinations must be under the configured remote's "
                "tracking namespace."
            )

    return refresh_remote, tuple(refresh_refspecs)


def _required_path(data: Mapping[str, Any], field_name: str, base_dir: Path) -> Path:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            f"Runtime configuration must define {field_name} as a string."
        )
    return _resolve_path(value, base_dir)


def _optional_path(data: Mapping[str, Any], field_name: str, base_dir: Path) -> Optional[Path]:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            f"Runtime configuration {field_name} must be a string when provided."
        )
    return _resolve_path(value, base_dir)


def _optional_selector_path(
    data: Mapping[str, Any],
    field_name: str,
    base_dir: Path,
) -> Optional[Path]:
    if field_name not in data:
        return None
    return _required_path(data, field_name, base_dir)


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve(strict=False)
    return (base_dir / path).resolve(strict=False)

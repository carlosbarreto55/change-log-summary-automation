"""Workflow configuration loading and validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Optional

from release_notes_generator.domain.configuration import (
    AIBackend,
    ClaudeCodeAISettings,
    ContributorPolicy,
    DatabasePathPolicy,
    ModuleDefinition,
    ModulePolicy,
    OpenAICompatibleAISettings,
    ReportMode,
    RepositoryUpdateMode,
    TaskPatternConfig,
    WorkflowConfiguration,
)
from release_notes_generator.services.contracts import JSONReader
from release_notes_generator.services.errors import ConfigurationError


class ConfigurationService:
    """Load a runtime manifest and validate all referenced JSON before side effects."""

    def __init__(self, json_reader: JSONReader) -> None:
        self._json_reader = json_reader

    def load(self, config_path: Path) -> WorkflowConfiguration:
        path = Path(config_path).expanduser()
        runtime = self._json_reader.read_object(path)
        base_dir = path.resolve(strict=False).parent
        report_mode = _report_mode(runtime)

        head_ref = _required_non_blank_string(runtime, "head_ref")
        base_ref = _optional_non_blank_string(runtime, "base_ref")
        release_marker_path = _optional_selector_path(
            runtime, "release_marker_config_path", base_dir
        )
        if (base_ref is None) == (release_marker_path is None):
            raise ConfigurationError(
                "Runtime configuration must define exactly one of base_ref or "
                "release_marker_config_path."
            )

        update_mode = _repository_update_mode(runtime)
        refresh_remote, refresh_refspecs = _refresh_configuration(runtime, update_mode)
        output_path = _required_path(runtime, "output_path", base_dir)
        if output_path.suffix.lower() != ".pdf":
            raise ConfigurationError(
                "Runtime configuration output_path must be a .pdf file."
            )

        repository_path = _required_path(runtime, "repository_path", base_dir)
        user_path = _required_path(runtime, "user_config_path", base_dir)
        module_path = _required_path(runtime, "module_config_path", base_dir)

        ai = None
        ai_path = None
        temp_diff_dir = None
        env_file_path = None
        if report_mode is ReportMode.AI_SUMMARY:
            ai_path = _required_path(runtime, "ai_config_path", base_dir)
            temp_diff_dir = _required_path(runtime, "temp_diff_dir", base_dir)
            env_file_path = _optional_path(runtime, "env_file_path", base_dir)

        release_marker = None
        if release_marker_path is not None:
            release_marker = _release_marker(
                self._json_reader.read_object(release_marker_path)
            )
        contributors = _contributor_policy(self._json_reader.read_object(user_path))
        modules = _module_policy(self._json_reader.read_object(module_path))
        if ai_path is not None:
            ai = _ai_settings(self._json_reader.read_object(ai_path))

        database_paths: Optional[DatabasePathPolicy] = None
        if report_mode is ReportMode.COMMIT_LIST:
            database_paths_config_path = _optional_path(
                runtime, "database_paths_config_path", base_dir
            )
            if database_paths_config_path is not None:
                database_paths = _database_path_policy(
                    self._json_reader.read_object(database_paths_config_path)
                )

        return WorkflowConfiguration(
            repository_path=repository_path,
            contributors=contributors,
            modules=modules,
            ai=ai,
            temp_diff_dir=temp_diff_dir,
            output_path=output_path,
            head_ref=head_ref,
            base_ref=base_ref,
            release_marker=release_marker,
            repository_update_mode=update_mode,
            refresh_remote=refresh_remote,
            refresh_refspecs=refresh_refspecs,
            env_file_path=env_file_path,
            report_mode=report_mode,
            database_paths=database_paths,
        )


def _contributor_policy(data: Mapping[str, Any]) -> ContributorPolicy:
    emails = data.get("approved_author_emails")
    if not _is_string_list(emails):
        raise ConfigurationError(
            "Users configuration must define approved_author_emails as a list of strings."
        )
    return ContributorPolicy(tuple(emails))


def _module_policy(data: Mapping[str, Any]) -> ModulePolicy:
    modules = data.get("modules")
    if not isinstance(modules, list):
        raise ConfigurationError("Modules configuration must define modules as a list.")

    definitions: list[ModuleDefinition] = []
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
            raise ConfigurationError(
                "Each module configuration entry must define a section."
            )
        definitions.append(ModuleDefinition(name, tuple(tags), section))

    # Load optional task patterns configuration
    task_patterns = None
    if "task_patterns" in data:
        task_patterns_data = data["task_patterns"]
        if not isinstance(task_patterns_data, dict):
            raise ConfigurationError(
                "Module configuration task_patterns must be an object."
            )

        # Validate and extract pattern strings
        wlt = None
        wltm = None
        plm = None

        if "wlt" in task_patterns_data:
            wlt = task_patterns_data["wlt"]
            if not isinstance(wlt, str) or not wlt:
                raise ConfigurationError(
                    "Task pattern 'wlt' must be a non-empty string."
                )
            # Validate regex compiles
            try:
                import re
                re.compile(wlt)
            except re.error as exc:
                raise ConfigurationError(
                    f"Task pattern 'wlt' is not a valid regex: {exc}"
                ) from exc

        if "wltm" in task_patterns_data:
            wltm = task_patterns_data["wltm"]
            if not isinstance(wltm, str) or not wltm:
                raise ConfigurationError(
                    "Task pattern 'wltm' must be a non-empty string."
                )
            try:
                import re
                re.compile(wltm)
            except re.error as exc:
                raise ConfigurationError(
                    f"Task pattern 'wltm' is not a valid regex: {exc}"
                ) from exc

        if "plm" in task_patterns_data:
            plm = task_patterns_data["plm"]
            if not isinstance(plm, str) or not plm:
                raise ConfigurationError(
                    "Task pattern 'plm' must be a non-empty string."
                )
            try:
                import re
                re.compile(plm)
            except re.error as exc:
                raise ConfigurationError(
                    f"Task pattern 'plm' is not a valid regex: {exc}"
                ) from exc

        # Only create TaskPatternConfig if at least one pattern is defined
        if wlt is not None or wltm is not None or plm is not None:
            task_patterns = TaskPatternConfig(wlt=wlt, wltm=wltm, plm=plm)

    return ModulePolicy(tuple(definitions), task_patterns=task_patterns)


def _release_marker(data: Mapping[str, Any]) -> str:
    marker = data.get("marker")
    if not isinstance(marker, str) or not marker.strip():
        raise ConfigurationError(
            "Release marker configuration must define a marker string."
        )
    return marker


def _ai_settings(data: Mapping[str, Any]):
    if "api_key" in data:
        raise ConfigurationError(
            "AI configuration must reference api_key_env_var instead of storing api_key."
        )
    backend_value = data.get("backend", AIBackend.OPENAI_COMPATIBLE.value)
    if not isinstance(backend_value, str) or not backend_value.strip():
        raise ConfigurationError(
            "AI configuration backend must be a non-empty string when provided."
        )
    try:
        backend = AIBackend(backend_value)
    except ValueError as exc:
        raise ConfigurationError(
            f"Unsupported AI configuration backend: {backend_value}"
        ) from exc

    if backend is AIBackend.CLAUDE_CODE:
        for field_name in ("api_url", "api_key_env_var"):
            if field_name in data:
                raise ConfigurationError(
                    f"AI configuration {field_name} is not valid for the claude_code backend."
                )
        model, prompt, limit = _ai_model_prompt_and_limit(data)
        return ClaudeCodeAISettings(model, prompt, limit)

    api_url = data.get("api_url")
    api_key_env_var = data.get("api_key_env_var")
    if not isinstance(api_url, str) or not api_url:
        raise ConfigurationError("AI configuration must define an api_url string.")
    if not isinstance(api_key_env_var, str) or not api_key_env_var:
        raise ConfigurationError(
            "AI configuration must define an api_key_env_var string."
        )
    model, prompt, limit = _ai_model_prompt_and_limit(data)
    return OpenAICompatibleAISettings(
        api_url, model, api_key_env_var, prompt, limit
    )


def _ai_model_prompt_and_limit(data: Mapping[str, Any]) -> tuple[str, str, int]:
    model = data.get("model")
    prompt = data.get("prompt")
    limit = data.get("max_diff_characters_per_request")
    if not isinstance(model, str) or not model:
        raise ConfigurationError("AI configuration must define a model string.")
    if not isinstance(prompt, str) or not prompt:
        raise ConfigurationError("AI configuration must define a prompt string.")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ConfigurationError(
            "AI configuration must define max_diff_characters_per_request "
            "as a positive integer."
        )
    return model, prompt, limit


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
    data: Mapping[str, Any], field_name: str
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
        raise ConfigurationError(f"Unknown repository_update_mode: {value}") from exc


def _report_mode(data: Mapping[str, Any]) -> ReportMode:
    value = data.get("report_mode", ReportMode.AI_SUMMARY.value)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            "Runtime configuration report_mode must be a non-empty string."
        )
    try:
        return ReportMode(value)
    except ValueError as exc:
        raise ConfigurationError(f"Unknown report_mode: {value}") from exc


def _refresh_configuration(
    data: Mapping[str, Any], update_mode: RepositoryUpdateMode
) -> tuple[Optional[str], tuple[str, ...]]:
    fields = ("refresh_remote", "refresh_refspecs")
    if update_mode is not RepositoryUpdateMode.REFRESH_REMOTE_REFS:
        if any(field in data for field in fields):
            raise ConfigurationError(
                "Runtime configuration refresh fields are only valid for "
                "refresh_remote_refs mode."
            )
        return None, ()

    remote = _required_non_blank_string(data, "refresh_remote")
    refspecs = data.get("refresh_refspecs")
    if not isinstance(refspecs, list) or not refspecs:
        raise ConfigurationError(
            "Runtime configuration must define refresh_refspecs as a non-empty list."
        )
    prefix = f"refs/remotes/{remote}/"
    for refspec in refspecs:
        if not isinstance(refspec, str) or not refspec.strip():
            raise ConfigurationError(
                "Runtime configuration refresh_refspecs must contain non-empty strings."
            )
        if refspec.count(":") != 1:
            raise ConfigurationError(
                "Each refresh refspec must define an explicit source:destination."
            )
        source, destination = refspec.split(":")
        if not source.removeprefix("+").strip() or not destination.strip():
            raise ConfigurationError(
                "Each refresh refspec must define a non-empty source and destination."
            )
        if not destination.startswith(prefix):
            raise ConfigurationError(
                "Refresh refspec destinations must be under the configured remote's "
                "tracking namespace."
            )
    return remote, tuple(refspecs)


def _required_path(data: Mapping[str, Any], field_name: str, base_dir: Path) -> Path:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            f"Runtime configuration must define {field_name} as a string."
        )
    return _resolve_path(value, base_dir)


def _optional_path(
    data: Mapping[str, Any], field_name: str, base_dir: Path
) -> Optional[Path]:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(
            f"Runtime configuration {field_name} must be a string when provided."
        )
    return _resolve_path(value, base_dir)


def _optional_selector_path(
    data: Mapping[str, Any], field_name: str, base_dir: Path
) -> Optional[Path]:
    if field_name not in data:
        return None
    return _required_path(data, field_name, base_dir)


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve(strict=False)
    return (base_dir / path).resolve(strict=False)


def _validate_database_path(path: str) -> None:
    """Reject a database path that is not repository-relative or cannot match."""
    if re.match(r"^[A-Za-z]:", path):
        raise ConfigurationError(
            f"Database path must be repository-relative; absolute Windows path not allowed: {path}"
        )
    if "\\" in path:
        raise ConfigurationError(
            f"Database path must use forward slashes; backslash not allowed: {path}"
        )
    if path.startswith("/"):
        raise ConfigurationError(
            f"Database path must be repository-relative; absolute path not allowed: {path}"
        )
    for segment in path.split("/"):
        if not segment or segment != segment.strip():
            raise ConfigurationError(
                f"Database path must not contain empty or padded segments; "
                f"found '{segment}' in: {path}"
            )
        if segment in (".", ".."):
            raise ConfigurationError(
                f"Database path must not contain traversal segments; found '{segment}' in: {path}"
            )


def _database_path_policy(data: Mapping[str, Any]) -> DatabasePathPolicy:
    """Load and validate database path policy from JSON data."""
    paths_value = data.get("paths")
    if paths_value is None:
        raise ConfigurationError(
            "Database paths configuration must define a 'paths' key."
        )
    if not isinstance(paths_value, list):
        raise ConfigurationError(
            "Database paths configuration 'paths' must be a list."
        )

    seen: set[str] = set()
    validated: list[str] = []
    for i, entry in enumerate(paths_value):
        if not isinstance(entry, str):
            raise ConfigurationError(
                f"Database paths configuration entry {i} must be a string."
            )
        if not entry.strip():
            raise ConfigurationError(
                f"Database paths configuration entry {i} must be non-blank."
            )
        _validate_database_path(entry)
        if entry not in seen:
            seen.add(entry)
            validated.append(entry)

    return DatabasePathPolicy(paths=tuple(validated))

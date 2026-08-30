"""Immutable configuration values used by the release-notes workflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Optional, Union


class RepositoryUpdateMode(str, Enum):
    """Supported repository update behavior before release analysis."""

    READ_ONLY = "read_only"
    REFRESH_REMOTE_REFS = "refresh_remote_refs"
    LEGACY_IN_PLACE_SYNC = "legacy_in_place_sync"


class AIBackend(str, Enum):
    """Supported summarization backends."""

    OPENAI_COMPATIBLE = "openai_compatible"
    CLAUDE_CODE = "claude_code"


@dataclass(frozen=True)
class ContributorPolicy:
    """Exact Git author emails approved for release notes."""

    approved_author_emails: tuple[str, ...]


@dataclass(frozen=True)
class ModuleDefinition:
    """One configured module and its release-notes section."""

    name: str
    tags: tuple[str, ...]
    section: str


@dataclass(frozen=True)
class ModulePolicy:
    """Ordered module classification definitions."""

    modules: tuple[ModuleDefinition, ...]

    @property
    def module_tags(self) -> Mapping[str, tuple[str, ...]]:
        """Return tags keyed by module name in configuration order."""
        return {module.name: module.tags for module in self.modules}


@dataclass(frozen=True)
class OpenAICompatibleAISettings:
    """OpenAI-compatible settings without secret values."""

    api_url: str
    model: str
    api_key_env_var: str
    prompt: str
    max_diff_characters_per_request: int

    @property
    def backend(self) -> AIBackend:
        return AIBackend.OPENAI_COMPATIBLE


@dataclass(frozen=True)
class ClaudeCodeAISettings:
    """Keyless Claude Code summarization settings."""

    model: str
    prompt: str
    max_diff_characters_per_request: int

    @property
    def backend(self) -> AIBackend:
        return AIBackend.CLAUDE_CODE


AISettings = Union[OpenAICompatibleAISettings, ClaudeCodeAISettings]


@dataclass(frozen=True)
class WorkflowConfiguration:
    """Validated configuration for one complete release-notes run."""

    repository_path: Path
    contributors: ContributorPolicy
    modules: ModulePolicy
    ai: AISettings
    temp_diff_dir: Path
    output_path: Path
    head_ref: str
    base_ref: Optional[str]
    release_marker: Optional[str]
    repository_update_mode: RepositoryUpdateMode = RepositoryUpdateMode.READ_ONLY
    refresh_remote: Optional[str] = None
    refresh_refspecs: tuple[str, ...] = ()
    env_file_path: Optional[Path] = None

"""AI summarization for category-specific release-note diff files."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Protocol

from release_notes_generator.configuration import (
    AIConfig,
    ClaudeCodeAIConfig,
    OpenAICompatibleAIConfig,
)


DEFAULT_USER_AGENT = "change-log-summary/0.1"

REDUCTION_SYSTEM_PROMPT = (
    "Combine the partial release-note summaries into one concise summary. "
    "Preserve user-visible facts and return Markdown bullets."
)


class AISummarizationError(RuntimeError):
    """Raised when AI summarization cannot be completed."""


@dataclass(frozen=True)
class SummarizationProvenance:
    """Secret-free record of which backend produced completed summaries."""

    backend: str
    model: str
    claude_code_version: Optional[str] = None


@dataclass(frozen=True)
class SummarizationOutcome:
    """Immutable completed summarization result with execution provenance."""

    module_summaries: tuple[tuple[str, str], ...]
    provenance: Optional[SummarizationProvenance]

    @property
    def summaries(self) -> dict[str, str]:
        """Return the ordered module summaries as a mapping."""
        return dict(self.module_summaries)


class SummaryClient(Protocol):
    """Client capable of summarizing one category-specific diff payload."""

    def summarize(self, module_name: str, diff_content: str) -> str:
        """Return the standalone summary for one module diff payload."""

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        """Combine partial summaries for one module into a smaller summary."""


class OpenAIChatClient:
    """OpenAI-compatible chat-completions summarization client."""

    def __init__(
        self,
        api_url: str,
        model: str,
        api_key: str,
        prompt: str,
        timeout_seconds: int = 120,
    ) -> None:
        self._api_url = api_url
        self._model = model
        self._api_key = api_key
        self._prompt = prompt
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_config(
        cls,
        config: OpenAICompatibleAIConfig,
        environ: Optional[Mapping[str, str]] = None,
        env_file: Optional[Path] = None,
    ) -> "OpenAIChatClient":
        """Build a client using an API key from process environment or an env file."""
        resolved_environment = load_env_file(env_file) if env_file is not None else {}
        resolved_environment.update(os.environ if environ is None else environ)
        api_key = resolved_environment.get(config.api_key_env_var)
        if not api_key:
            raise AISummarizationError(
                f"Missing AI API key environment variable: {config.api_key_env_var}"
            )

        return cls(
            api_url=config.api_url,
            model=config.model,
            api_key=api_key,
            prompt=config.prompt,
        )

    def summarize(self, module_name: str, diff_content: str) -> str:
        return self._complete(
            system_prompt=self._prompt,
            user_content=f"Module: {module_name}\n\nDiff:\n{diff_content}",
        )

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        return self._complete(
            system_prompt=REDUCTION_SYSTEM_PROMPT,
            user_content=(
                f"Module: {module_name}\n\nPartial summaries:\n{partial_summaries}"
            ),
        )

    def execution_provenance(self) -> SummarizationProvenance:
        """Return the secret-free backend identity used for completed requests."""
        return SummarizationProvenance(backend="openai_compatible", model=self._model)

    def _complete(self, system_prompt: str, user_content: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        request = urllib.request.Request(
            self._api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": DEFAULT_USER_AGENT,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise AISummarizationError("AI summarization request failed.") from exc

        try:
            summary = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AISummarizationError("AI summarization response was not usable.") from exc

        if not isinstance(summary, str) or not summary.strip():
            raise AISummarizationError("AI summarization response was empty.")
        return summary.strip()


def create_summary_client(
    ai_config: AIConfig,
    environ: Optional[Mapping[str, str]] = None,
    env_file: Optional[Path] = None,
) -> SummaryClient:
    """Construct only the summary client selected by the backend configuration."""
    if isinstance(ai_config, ClaudeCodeAIConfig):
        from release_notes_generator.claude_code import ClaudeCodeClient

        return ClaudeCodeClient(ai_config)
    if isinstance(ai_config, OpenAICompatibleAIConfig):
        return OpenAIChatClient.from_config(ai_config, environ=environ, env_file=env_file)
    raise AISummarizationError(
        f"Unsupported AI backend configuration: {type(ai_config).__name__}"
    )


def summarize_diff_files_with_provenance(
    diff_files: Mapping[str, Path],
    client: SummaryClient,
    max_characters_per_request: int,
) -> SummarizationOutcome:
    """Summarize bounded module diffs and return the completed immutable outcome."""
    summaries = summarize_diff_files(diff_files, client, max_characters_per_request)
    return SummarizationOutcome(
        module_summaries=tuple(summaries.items()),
        provenance=_client_execution_provenance(client),
    )


def _client_execution_provenance(
    client: SummaryClient,
) -> Optional[SummarizationProvenance]:
    provenance_source = getattr(client, "execution_provenance", None)
    if not callable(provenance_source):
        return None
    provenance = provenance_source()
    if not isinstance(provenance, SummarizationProvenance):
        raise AISummarizationError(
            "Summary client returned unusable execution provenance."
        )
    return provenance


def summarize_diff_files(
    diff_files: Mapping[str, Path],
    client: SummaryClient,
    max_characters_per_request: int,
) -> dict[str, str]:
    """Summarize bounded chunks and reduce them to one summary per module."""
    summaries: dict[str, str] = {}
    for module_name, diff_file_path in diff_files.items():
        try:
            diff_content = Path(diff_file_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise AISummarizationError(f"Unable to read diff file: {diff_file_path}") from exc

        try:
            partial_summaries = [
                client.summarize(module_name, chunk)
                for chunk in split_diff_content(diff_content, max_characters_per_request)
            ]
            summaries[module_name] = _reduce_summaries(
                module_name,
                partial_summaries,
                client,
                max_characters_per_request,
            )
        except AISummarizationError:
            raise
        except Exception as exc:
            raise AISummarizationError(
                f"AI summarization failed for module: {module_name}"
            ) from exc

    return summaries


def split_diff_content(diff_content: str, max_characters: int) -> tuple[str, ...]:
    """Split diff text losslessly, preferring commit and then line boundaries."""
    if max_characters <= 0:
        raise AISummarizationError("AI request character limit must be positive.")
    if len(diff_content) <= max_characters:
        return (diff_content,)

    segments = _commit_segments(diff_content)
    pieces: list[str] = []
    for segment in segments:
        pieces.extend(_bounded_text_pieces(segment, max_characters))
    return _pack_exact_pieces(pieces, max_characters)


def _commit_segments(content: str) -> tuple[str, ...]:
    boundaries = [0]
    offset = 0
    for line in content.splitlines(keepends=True):
        if offset and line.startswith("commit "):
            boundaries.append(offset)
        offset += len(line)
    boundaries.append(len(content))
    return tuple(
        content[start:end]
        for start, end in zip(boundaries, boundaries[1:])
        if end > start
    ) or (content,)


def _bounded_text_pieces(content: str, max_characters: int) -> tuple[str, ...]:
    if len(content) <= max_characters:
        return (content,)

    pieces: list[str] = []
    current = ""
    for line in content.splitlines(keepends=True):
        while len(line) > max_characters:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(line[:max_characters])
            line = line[max_characters:]
        if current and len(current) + len(line) > max_characters:
            pieces.append(current)
            current = ""
        current += line
    if current:
        pieces.append(current)
    return tuple(pieces)


def _pack_exact_pieces(
    pieces: list[str],
    max_characters: int,
) -> tuple[str, ...]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) > max_characters:
            chunks.append(current)
            current = ""
        current += piece
    if current or not chunks:
        chunks.append(current)
    return tuple(chunks)


def _reduce_summaries(
    module_name: str,
    partial_summaries: list[str],
    client: SummaryClient,
    max_characters: int,
) -> str:
    current = partial_summaries
    for _ in range(20):
        if len(current) == 1:
            return current[0]
        payloads = _pack_summary_payloads(current, max_characters)
        current = [client.reduce(module_name, payload) for payload in payloads]
    raise AISummarizationError(
        f"AI summary reduction did not converge for module: {module_name}"
    )


def _pack_summary_payloads(
    summaries: list[str],
    max_characters: int,
) -> tuple[str, ...]:
    pieces: list[str] = []
    for summary in summaries:
        pieces.extend(_bounded_text_pieces(summary, max_characters))

    payloads: list[str] = []
    current = ""
    for piece in pieces:
        separator = "\n\n" if current else ""
        if current and len(current) + len(separator) + len(piece) > max_characters:
            payloads.append(current)
            current = piece
        else:
            current = f"{current}{separator}{piece}"
    if current:
        payloads.append(current)
    return tuple(payloads)


def load_env_file(env_file_path: Optional[Path]) -> dict[str, str]:
    """Load simple KEY=VALUE entries from an env file without mutating process env."""
    if env_file_path is None:
        return {}

    path = Path(env_file_path)
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AISummarizationError(f"Unable to read env file: {path}") from exc

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")

    return values

"""AI summarization for category-specific release-note diff files."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Mapping, Optional, Protocol

from release_notes_generator.configuration import AIConfig


DEFAULT_USER_AGENT = "change-log-summary/0.1"


class AISummarizationError(RuntimeError):
    """Raised when AI summarization cannot be completed."""


class SummaryClient(Protocol):
    """Client capable of summarizing one category-specific diff payload."""

    def summarize(self, module_name: str, diff_content: str) -> str:
        """Return the standalone summary for one module diff payload."""


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
        config: AIConfig,
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
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": self._prompt},
                {
                    "role": "user",
                    "content": f"Module: {module_name}\n\nDiff:\n{diff_content}",
                },
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


def summarize_diff_files(
    diff_files: Mapping[str, Path],
    client: SummaryClient,
) -> dict[str, str]:
    """Read each category diff file and request one standalone AI summary per file."""
    summaries: dict[str, str] = {}
    for module_name, diff_file_path in diff_files.items():
        try:
            diff_content = Path(diff_file_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise AISummarizationError(f"Unable to read diff file: {diff_file_path}") from exc

        try:
            summaries[module_name] = client.summarize(module_name, diff_content)
        except AISummarizationError:
            raise
        except Exception as exc:
            raise AISummarizationError(f"AI summarization failed for module: {module_name}") from exc

    return summaries


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

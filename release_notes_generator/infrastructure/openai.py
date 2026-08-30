"""OpenAI-compatible HTTP client and backend client factory."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Mapping, Optional

from release_notes_generator.domain.configuration import (
    AISettings,
    ClaudeCodeAISettings,
    OpenAICompatibleAISettings,
)
from release_notes_generator.domain.summarization import SummarizationProvenance
from release_notes_generator.infrastructure.claude_code import ClaudeCodeClient
from release_notes_generator.infrastructure.environment import EnvironmentFileAdapter
from release_notes_generator.services.contracts import SummaryClient
from release_notes_generator.services.errors import AISummarizationError
from release_notes_generator.services.summarization import REDUCTION_SYSTEM_PROMPT


DEFAULT_USER_AGENT = "change-log-summary/0.1"


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

    def summarize(self, module_name: str, diff_content: str) -> str:
        return self._complete(
            self._prompt, f"Module: {module_name}\n\nDiff:\n{diff_content}"
        )

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        return self._complete(
            REDUCTION_SYSTEM_PROMPT,
            f"Module: {module_name}\n\nPartial summaries:\n{partial_summaries}",
        )

    def execution_provenance(self) -> SummarizationProvenance:
        return SummarizationProvenance("openai_compatible", self._model)

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
            with urllib.request.urlopen(
                request, timeout=self._timeout_seconds
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise AISummarizationError("AI summarization request failed.") from exc

        try:
            summary = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AISummarizationError(
                "AI summarization response was not usable."
            ) from exc
        if not isinstance(summary, str) or not summary.strip():
            raise AISummarizationError("AI summarization response was empty.")
        return summary.strip()


class SummaryClientFactoryAdapter:
    """Construct only the configured provider client, resolving secrets lazily."""

    def __init__(
        self,
        environ: Optional[Mapping[str, str]] = None,
        environment_files: Optional[EnvironmentFileAdapter] = None,
    ) -> None:
        self._environ = environ
        self._environment_files = environment_files or EnvironmentFileAdapter()

    def create(
        self, settings: AISettings, env_file: Optional[Path]
    ) -> SummaryClient:
        if isinstance(settings, ClaudeCodeAISettings):
            return ClaudeCodeClient(settings)
        if isinstance(settings, OpenAICompatibleAISettings):
            resolved = self._environment_files.load(env_file)
            resolved.update(os.environ if self._environ is None else self._environ)
            api_key = resolved.get(settings.api_key_env_var)
            if not api_key:
                raise AISummarizationError(
                    "Missing AI API key environment variable: "
                    f"{settings.api_key_env_var}"
                )
            return OpenAIChatClient(
                settings.api_url,
                settings.model,
                api_key,
                settings.prompt,
            )
        raise AISummarizationError(
            f"Unsupported AI backend configuration: {type(settings).__name__}"
        )

"""Restricted Claude Code CLI adapter for release-note summarization.

The contract implemented here was recorded in the change design after the
2026-08-28 compatibility spike: minimum supported executable version
``2.1.251``, the fixed restricted argument vector, and the single JSON result
envelope whose ``structured_output`` field carries the schema-valid summary.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, Sequence

from release_notes_generator.configuration import ClaudeCodeAIConfig
from release_notes_generator.summarization import (
    AISummarizationError,
    REDUCTION_SYSTEM_PROMPT,
    SummarizationProvenance,
)


CLAUDE_EXECUTABLE = "claude"

MINIMUM_SUPPORTED_CLAUDE_CODE_VERSION = "2.1.251"

SUMMARY_JSON_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string", "minLength": 1}},
    "required": ["summary"],
    "additionalProperties": False,
}

_SUMMARY_SCHEMA_ARGUMENT = json.dumps(SUMMARY_JSON_SCHEMA, sort_keys=True)

DEFAULT_VERSION_TIMEOUT_SECONDS = 60
DEFAULT_REQUEST_TIMEOUT_SECONDS = 600

_VERSION_PATTERN = re.compile(r"^(\d+(?:\.\d+)+)")


@dataclass(frozen=True)
class ProcessResult:
    """Completed process facts crossing the process-runner boundary."""

    returncode: int
    stdout: str
    stderr: str


class ProcessRunner(Protocol):
    """Runs one argument vector to completion without a command shell."""

    def __call__(
        self,
        args: Sequence[str],
        *,
        stdin_text: str,
        cwd: Path,
        timeout_seconds: int,
    ) -> ProcessResult:
        ...


def run_claude_process(
    args: Sequence[str],
    *,
    stdin_text: str,
    cwd: Path,
    timeout_seconds: int,
) -> ProcessResult:
    """Run one shell-free subprocess that inherits the operator's environment."""
    completed = subprocess.run(
        list(args),
        input=stdin_text,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    return ProcessResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(component) for component in version.split("."))


def parse_claude_version_output(output: str) -> str:
    """Return the supported dotted version from ``claude --version`` output."""
    match = _VERSION_PATTERN.match(output.strip())
    if match is None:
        raise AISummarizationError(
            "Claude Code version output was not recognized as a version."
        )
    version = match.group(1)
    if _version_key(version) < _version_key(MINIMUM_SUPPORTED_CLAUDE_CODE_VERSION):
        raise AISummarizationError(
            f"Claude Code version {version} is below the minimum supported "
            f"version {MINIMUM_SUPPORTED_CLAUDE_CODE_VERSION}."
        )
    return version


def parse_structured_summary_envelope(raw_output: str) -> str:
    """Extract the schema-valid summary from one Claude Code result envelope."""
    try:
        envelope = json.loads(raw_output)
    except json.JSONDecodeError:
        raise AISummarizationError(
            "Claude Code did not return a parseable JSON result envelope."
        ) from None

    if not isinstance(envelope, dict):
        raise AISummarizationError(
            "Claude Code result envelope was not a JSON object."
        )
    if (
        envelope.get("type") != "result"
        or envelope.get("subtype") != "success"
        or envelope.get("is_error") is not False
    ):
        raise AISummarizationError(
            "Claude Code result envelope did not report a successful result."
        )

    structured_output = envelope.get("structured_output")
    if not isinstance(structured_output, dict):
        raise AISummarizationError(
            "Claude Code result envelope did not include structured output."
        )
    if set(structured_output) != {"summary"}:
        raise AISummarizationError(
            "Claude Code structured output did not match the summary schema."
        )
    summary = structured_output["summary"]
    if not isinstance(summary, str) or not summary.strip():
        raise AISummarizationError(
            "Claude Code structured output contained an empty summary."
        )
    return summary.strip()


class ClaudeCodeClient:
    """Summarizes bounded module payloads through fresh restricted `claude -p` processes."""

    def __init__(
        self,
        config: ClaudeCodeAIConfig,
        process_runner: Optional[ProcessRunner] = None,
        version_timeout_seconds: int = DEFAULT_VERSION_TIMEOUT_SECONDS,
        request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._config = config
        self._process_runner: ProcessRunner = (
            run_claude_process if process_runner is None else process_runner
        )
        self._version_timeout_seconds = version_timeout_seconds
        self._request_timeout_seconds = request_timeout_seconds
        self._version: Optional[str] = None

    def summarize(self, module_name: str, diff_content: str) -> str:
        return self._request(
            system_prompt=self._config.prompt,
            user_content=f"Module: {module_name}\n\nDiff:\n{diff_content}",
        )

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        return self._request(
            system_prompt=REDUCTION_SYSTEM_PROMPT,
            user_content=(
                f"Module: {module_name}\n\nPartial summaries:\n{partial_summaries}"
            ),
        )

    def execution_provenance(self) -> SummarizationProvenance:
        """Return the secret-free backend, detected version, and requested model."""
        return SummarizationProvenance(
            backend="claude_code",
            model=self._config.model,
            claude_code_version=self._ensure_version(),
        )

    def _ensure_version(self) -> str:
        if self._version is None:
            result = self._run(
                (CLAUDE_EXECUTABLE, "--version"),
                stdin_text="",
                timeout_seconds=self._version_timeout_seconds,
                purpose="version probe",
            )
            if result.returncode != 0:
                raise AISummarizationError(
                    "Claude Code version probe exited with a nonzero status."
                )
            self._version = parse_claude_version_output(result.stdout)
        return self._version

    def _request(self, system_prompt: str, user_content: str) -> str:
        self._ensure_version()
        args = (
            CLAUDE_EXECUTABLE,
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            _SUMMARY_SCHEMA_ARGUMENT,
            "--model",
            self._config.model,
            "--safe-mode",
            "--disable-slash-commands",
            "--tools",
            "",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--system-prompt",
            system_prompt,
        )
        result = self._run(
            args,
            stdin_text=user_content,
            timeout_seconds=self._request_timeout_seconds,
            purpose="summarization request",
        )
        if result.returncode != 0:
            raise AISummarizationError(
                "Claude Code summarization request exited with a nonzero status. "
                "Verify the Claude Code login and usage limits independently."
            )
        return parse_structured_summary_envelope(result.stdout)

    def _run(
        self,
        args: Sequence[str],
        *,
        stdin_text: str,
        timeout_seconds: int,
        purpose: str,
    ) -> ProcessResult:
        working_dir = Path(tempfile.mkdtemp(prefix="claude-code-request-"))
        try:
            try:
                return self._process_runner(
                    tuple(args),
                    stdin_text=stdin_text,
                    cwd=working_dir,
                    timeout_seconds=timeout_seconds,
                )
            except FileNotFoundError:
                raise AISummarizationError(
                    f"Claude Code executable '{CLAUDE_EXECUTABLE}' was not found."
                ) from None
            except subprocess.TimeoutExpired:
                raise AISummarizationError(
                    f"Claude Code {purpose} timed out after "
                    f"{timeout_seconds} seconds."
                ) from None
            except OSError:
                raise AISummarizationError(
                    f"Claude Code {purpose} process could not be started."
                ) from None
        finally:
            shutil.rmtree(working_dir, ignore_errors=True)

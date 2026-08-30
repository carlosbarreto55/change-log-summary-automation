"""Unit tests for the restricted Claude Code summarization client."""

import dataclasses
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.infrastructure.claude_code import (
    CLAUDE_EXECUTABLE,
    ClaudeCodeClient,
    ProcessResult,
    run_claude_process,
)
from release_notes_generator.domain.configuration import ClaudeCodeAISettings
from release_notes_generator.services.summarization import (
    AISummarizationError,
    REDUCTION_SYSTEM_PROMPT,
    SummarizationProvenance,
)


VERSION_OUTPUT = "2.1.251 (Claude Code)\n"

EXPECTED_SCHEMA_ARGUMENT = json.dumps(
    {
        "type": "object",
        "properties": {"summary": {"type": "string", "minLength": 1}},
        "required": ["summary"],
        "additionalProperties": False,
    },
    sort_keys=True,
)

FORBIDDEN_FLAGS = (
    "--resume",
    "--continue",
    "--session-id",
    "--fork-session",
    "--plugin",
    "--mcp-config",
    "--permission-mode",
    "--dangerously-skip-permissions",
    "--browser",
    "--remote",
    "--bare",
)


def _success_result() -> ProcessResult:
    return ProcessResult(returncode=0, stdout=VERSION_OUTPUT, stderr="")


def _envelope_result(summary: str = "- Sanitized summary.") -> ProcessResult:
    envelope = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "session_id": "00000000-0000-0000-0000-000000000000",
        "result": json.dumps({"summary": summary}),
        "structured_output": {"summary": summary},
    }
    return ProcessResult(returncode=0, stdout=json.dumps(envelope), stderr="")


class RecordingProcessRunner:
    """Recording stand-in for the injected process-runner boundary."""

    def __init__(self, script) -> None:
        self._script = list(script)
        self.invocations: list[dict] = []

    def __call__(self, args, *, stdin_text, cwd, timeout_seconds) -> ProcessResult:
        working_dir = Path(cwd)
        self.invocations.append(
            {
                "args": tuple(args),
                "stdin_text": stdin_text,
                "cwd": working_dir,
                "cwd_existed": working_dir.is_dir(),
                "cwd_entries": (
                    tuple(entry.name for entry in working_dir.iterdir())
                    if working_dir.is_dir()
                    else None
                ),
                "timeout_seconds": timeout_seconds,
            }
        )
        outcome = self._script.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    @property
    def request_invocations(self) -> list[dict]:
        return [
            invocation
            for invocation in self.invocations
            if invocation["args"][1:2] != ("--version",)
        ]

    @property
    def version_invocations(self) -> list[dict]:
        return [
            invocation
            for invocation in self.invocations
            if invocation["args"][1:] == ("--version",)
        ]


def _client(runner, model: str = "claude-model", prompt: str = "Summarize.") -> ClaudeCodeClient:
    config = ClaudeCodeAISettings(
        model=model,
        prompt=prompt,
        max_diff_characters_per_request=1000,
    )
    return ClaudeCodeClient(config, process_runner=runner)


class ClaudeCodeVersionProbeTests(unittest.TestCase):
    def test_version_probe_uses_fixed_executable_and_arguments(self) -> None:
        runner = RecordingProcessRunner([_success_result(), _envelope_result()])

        _client(runner).summarize("Pix", "pix diff")

        self.assertEqual(runner.invocations[0]["args"], (CLAUDE_EXECUTABLE, "--version"))
        self.assertEqual(CLAUDE_EXECUTABLE, "claude")

    def test_version_probe_runs_once_per_client(self) -> None:
        runner = RecordingProcessRunner(
            [
                _success_result(),
                _envelope_result(),
                _envelope_result(),
                _envelope_result(),
            ]
        )
        client = _client(runner)

        client.summarize("Pix", "first diff")
        client.summarize("Pix", "second diff")
        client.reduce("Pix", "partials")

        self.assertEqual(len(runner.version_invocations), 1)
        self.assertEqual(len(runner.request_invocations), 3)

    def test_missing_executable_is_a_summarization_error(self) -> None:
        runner = RecordingProcessRunner([FileNotFoundError("claude")])

        with self.assertRaises(AISummarizationError):
            _client(runner).summarize("Pix", "pix diff")

    def test_version_probe_timeout_is_a_summarization_error(self) -> None:
        runner = RecordingProcessRunner(
            [subprocess.TimeoutExpired(cmd="claude", timeout=1)]
        )

        with self.assertRaises(AISummarizationError):
            _client(runner).summarize("Pix", "pix diff")

    def test_version_probe_nonzero_status_is_a_summarization_error(self) -> None:
        runner = RecordingProcessRunner(
            [ProcessResult(returncode=1, stdout="", stderr="probe failed")]
        )

        with self.assertRaises(AISummarizationError):
            _client(runner).summarize("Pix", "pix diff")

    def test_version_probe_empty_output_is_a_summarization_error(self) -> None:
        runner = RecordingProcessRunner(
            [ProcessResult(returncode=0, stdout="", stderr="")]
        )

        with self.assertRaises(AISummarizationError):
            _client(runner).summarize("Pix", "pix diff")


class ClaudeCodeInvocationTests(unittest.TestCase):
    def test_summarize_uses_exact_restricted_argument_vector(self) -> None:
        runner = RecordingProcessRunner([_success_result(), _envelope_result()])

        _client(runner).summarize("Pix", "pix diff")

        self.assertEqual(
            runner.request_invocations[0]["args"],
            (
                "claude",
                "-p",
                "--output-format",
                "json",
                "--json-schema",
                EXPECTED_SCHEMA_ARGUMENT,
                "--model",
                "claude-model",
                "--safe-mode",
                "--disable-slash-commands",
                "--tools",
                "",
                "--strict-mcp-config",
                "--no-session-persistence",
                "--system-prompt",
                "Summarize.",
            ),
        )

    def test_reduce_uses_reduction_prompt_and_same_restrictions(self) -> None:
        runner = RecordingProcessRunner([_success_result(), _envelope_result()])

        _client(runner).reduce("Pix", "- part one\n- part two")

        arguments = runner.request_invocations[0]["args"]
        self.assertEqual(arguments[-2:], ("--system-prompt", REDUCTION_SYSTEM_PROMPT))
        self.assertEqual(arguments[:5], ("claude", "-p", "--output-format", "json", "--json-schema"))
        for restriction in (
            "--safe-mode",
            "--disable-slash-commands",
            "--tools",
            "--strict-mcp-config",
            "--no-session-persistence",
        ):
            self.assertIn(restriction, arguments)

    def test_source_content_is_confined_to_standard_input(self) -> None:
        diff = 'SECRET-DIFF $(rm -rf /) `whoami` | tee --resume "quoted"\nsecond line'
        runner = RecordingProcessRunner([_success_result(), _envelope_result()])

        _client(runner).summarize("Pix", diff)

        invocation = runner.request_invocations[0]
        self.assertNotIn("SECRET-DIFF", " ".join(invocation["args"]))
        self.assertFalse(any("Pix" in argument for argument in invocation["args"]))
        self.assertIn("Module: Pix", invocation["stdin_text"])
        self.assertIn(diff, invocation["stdin_text"])

    def test_no_forbidden_session_or_permission_flag_is_used(self) -> None:
        runner = RecordingProcessRunner(
            [_success_result(), _envelope_result(), _envelope_result()]
        )
        client = _client(runner)

        client.summarize("Pix", "pix diff")
        client.reduce("Pix", "partials")

        for invocation in runner.invocations:
            for forbidden in FORBIDDEN_FLAGS:
                self.assertNotIn(forbidden, invocation["args"])

    def test_requests_run_in_fresh_empty_temporary_directories(self) -> None:
        runner = RecordingProcessRunner(
            [_success_result(), _envelope_result(), _envelope_result()]
        )
        client = _client(runner)

        client.summarize("Pix", "pix diff")
        client.reduce("Pix", "partials")

        working_dirs = [invocation["cwd"] for invocation in runner.invocations]
        self.assertEqual(len(set(working_dirs)), len(working_dirs))
        for invocation in runner.invocations:
            self.assertTrue(invocation["cwd_existed"])
            self.assertEqual(invocation["cwd_entries"], ())
            self.assertNotEqual(invocation["cwd"], Path.cwd())
        for working_dir in working_dirs:
            self.assertFalse(working_dir.exists())

    def test_temporary_directory_is_cleaned_after_failures(self) -> None:
        failures = (
            ProcessResult(returncode=1, stdout="", stderr="denied"),
            subprocess.TimeoutExpired(cmd="claude", timeout=1),
            FileNotFoundError("claude"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                runner = RecordingProcessRunner([_success_result(), failure])
                client = _client(runner)

                with self.assertRaises(AISummarizationError):
                    client.summarize("Pix", "pix diff")

                for invocation in runner.invocations:
                    self.assertFalse(invocation["cwd"].exists())

    def test_production_runner_uses_shell_false_and_inherited_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("release_notes_generator.infrastructure.claude_code.subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = VERSION_OUTPUT
                run.return_value.stderr = ""

                result = run_claude_process(
                    ("claude", "--version"),
                    stdin_text="stdin payload",
                    cwd=Path(temp_dir),
                    timeout_seconds=5,
                )

        self.assertEqual(result, ProcessResult(0, VERSION_OUTPUT, ""))
        self.assertEqual(run.call_args.args[0], ["claude", "--version"])
        kwargs = run.call_args.kwargs
        self.assertFalse(kwargs.get("shell", False))
        self.assertEqual(kwargs["input"], "stdin payload")
        self.assertEqual(kwargs["cwd"], str(Path(temp_dir)))
        self.assertEqual(kwargs["timeout"], 5)
        self.assertTrue(kwargs["capture_output"])
        self.assertNotIn("env", kwargs)


class ClaudeCodeIsolationTests(unittest.TestCase):
    def test_every_request_creates_a_distinct_non_persistent_process(self) -> None:
        runner = RecordingProcessRunner(
            [
                _success_result(),
                _envelope_result("- first"),
                _envelope_result("- second"),
                _envelope_result("- reduced"),
            ]
        )
        client = _client(runner)

        client.summarize("Pix", "first diff")
        client.summarize("GlobalLoyalty", "second diff")
        client.reduce("Pix", "partials")

        self.assertEqual(len(runner.request_invocations), 3)
        working_dirs = {
            invocation["cwd"] for invocation in runner.request_invocations
        }
        self.assertEqual(len(working_dirs), 3)
        for invocation in runner.invocations:
            self.assertNotIn("--resume", invocation["args"])
            self.assertNotIn("--continue", invocation["args"])
            self.assertIn(
                "--no-session-persistence",
                invocation["args"] if invocation["args"][1:] != ("--version",) else ("--no-session-persistence",),
            )

    def test_no_prompt_response_or_module_state_crosses_requests(self) -> None:
        runner = RecordingProcessRunner(
            [
                _success_result(),
                _envelope_result("- FIRST-RESPONSE"),
                _envelope_result("- second response"),
                _envelope_result("- reduced"),
            ]
        )
        client = _client(runner)

        first = client.summarize("Pix", "FIRST-PAYLOAD")
        client.summarize("GlobalLoyalty", "SECOND-PAYLOAD")
        client.reduce("GlobalLoyalty", "- partials only")

        self.assertEqual(first, "- FIRST-RESPONSE")
        second_request = runner.request_invocations[1]
        reduce_request = runner.request_invocations[2]
        self.assertEqual(
            second_request["stdin_text"],
            "Module: GlobalLoyalty\n\nDiff:\nSECOND-PAYLOAD",
        )
        self.assertEqual(
            reduce_request["stdin_text"],
            "Module: GlobalLoyalty\n\nPartial summaries:\n- partials only",
        )
        for later_request in (second_request, reduce_request):
            self.assertNotIn("FIRST-PAYLOAD", later_request["stdin_text"])
            self.assertNotIn("FIRST-RESPONSE", later_request["stdin_text"])
            self.assertNotIn("Module: Pix", later_request["stdin_text"])


class ClaudeCodeOutputTests(unittest.TestCase):
    def test_schema_valid_structured_output_is_returned(self) -> None:
        runner = RecordingProcessRunner(
            [_success_result(), _envelope_result("  - Bullet summary.  ")]
        )

        summary = _client(runner).summarize("Pix", "pix diff")

        self.assertEqual(summary, "- Bullet summary.")

    def test_unusable_process_results_are_rejected(self) -> None:
        def envelope_with(structured_output) -> ProcessResult:
            envelope = json.loads(_envelope_result().stdout)
            if structured_output is None:
                envelope.pop("structured_output")
            else:
                envelope["structured_output"] = structured_output
            return ProcessResult(0, json.dumps(envelope), "")

        failures = (
            ("timeout", subprocess.TimeoutExpired(cmd="claude", timeout=1)),
            ("nonzero-status", ProcessResult(1, "", "usage limit reached")),
            ("malformed-json", ProcessResult(0, "not json", "")),
            ("missing-structured-output", envelope_with(None)),
            ("additional-field", envelope_with({"summary": "ok", "extra": 1})),
            ("non-string-summary", envelope_with({"summary": 42})),
            ("empty-summary", envelope_with({"summary": "   "})),
        )
        for name, outcome in failures:
            with self.subTest(name=name):
                runner = RecordingProcessRunner([_success_result(), outcome])

                with self.assertRaises(AISummarizationError):
                    _client(runner).summarize("Pix", "pix diff")


class ClaudeCodeErrorSanitizationTests(unittest.TestCase):
    def test_error_messages_omit_payloads_outputs_and_environment(self) -> None:
        diff = "SECRET-STDIN-PAYLOAD"
        failures = (
            ("timeout", subprocess.TimeoutExpired(cmd="claude", timeout=1)),
            (
                "nonzero-status",
                ProcessResult(1, "SECRET-STDOUT", "SECRET-STDERR /login required"),
            ),
            ("malformed-json", ProcessResult(0, "SECRET-STDOUT not json", "SECRET-STDERR")),
            (
                "invalid-structured-output",
                ProcessResult(
                    0,
                    json.dumps(
                        {
                            "type": "result",
                            "subtype": "success",
                            "is_error": False,
                            "structured_output": {"summary": ""},
                            "result": "SECRET-STDOUT",
                        }
                    ),
                    "SECRET-STDERR",
                ),
            ),
            ("missing-executable", FileNotFoundError("SECRET-PATH")),
        )
        with patch.dict(os.environ, {"CLAUDE_TEST_TOKEN": "SECRET-ENV-VALUE"}):
            for name, outcome in failures:
                with self.subTest(name=name):
                    runner = RecordingProcessRunner([_success_result(), outcome])

                    with self.assertRaises(AISummarizationError) as context:
                        _client(runner).summarize("Pix", diff)

                    message = str(context.exception)
                    for secret in (
                        "SECRET-STDIN-PAYLOAD",
                        "SECRET-STDOUT",
                        "SECRET-STDERR",
                        "SECRET-ENV-VALUE",
                        "SECRET-PATH",
                        "Traceback",
                    ):
                        self.assertNotIn(secret, message)

    def test_expected_failures_do_not_chain_payload_bearing_causes(self) -> None:
        timeout = subprocess.TimeoutExpired(cmd="claude", timeout=1)
        runner = RecordingProcessRunner([_success_result(), timeout])

        with self.assertRaises(AISummarizationError) as context:
            _client(runner).summarize("Pix", "SECRET-STDIN-PAYLOAD")

        self.assertIsNone(context.exception.__cause__)


class ClaudeCodeProvenanceTests(unittest.TestCase):
    def test_provenance_contains_only_backend_version_and_model(self) -> None:
        runner = RecordingProcessRunner([_success_result(), _envelope_result()])
        client = _client(runner, model="claude-model")

        client.summarize("Pix", "pix diff")
        provenance = client.execution_provenance()

        self.assertEqual(
            provenance,
            SummarizationProvenance(
                backend="claude_code",
                model="claude-model",
                claude_code_version="2.1.251",
            ),
        )
        self.assertEqual(
            {field.name for field in dataclasses.fields(provenance)},
            {"backend", "model", "claude_code_version"},
        )

    def test_provenance_is_immutable(self) -> None:
        runner = RecordingProcessRunner([_success_result(), _envelope_result()])
        client = _client(runner)
        client.summarize("Pix", "pix diff")

        provenance = client.execution_provenance()

        with self.assertRaises(dataclasses.FrozenInstanceError):
            provenance.model = "other"  # type: ignore[misc]

    def test_provenance_reuses_the_single_version_probe(self) -> None:
        runner = RecordingProcessRunner([_success_result(), _envelope_result()])
        client = _client(runner)
        client.summarize("Pix", "pix diff")

        client.execution_provenance()
        client.execution_provenance()

        self.assertEqual(len(runner.version_invocations), 1)


if __name__ == "__main__":
    unittest.main()

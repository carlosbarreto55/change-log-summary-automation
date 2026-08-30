"""Context coverage for the real Claude Code subprocess boundary."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.infrastructure.claude_code import ClaudeCodeClient
from release_notes_generator.domain.configuration import ClaudeCodeAISettings
from release_notes_generator.services.errors import AISummarizationError
from tests.context.application import ReleaseNotesRunner
from tests.claude_code_harness import (
    installed_fake_claude,
    load_fake_claude_records,
)
from tests.context.workflow_fixture import (
    create_repository,
    write_runtime_configuration,
)


EXPECTED_REQUEST_ARGUMENT_NAMES = [
    "-p",
    "--output-format",
    "--json-schema",
    "--model",
    "--safe-mode",
    "--disable-slash-commands",
    "--tools",
    "--strict-mcp-config",
    "--no-session-persistence",
    "--system-prompt",
]


def _claude_config(max_characters: int = 12_000) -> ClaudeCodeAISettings:
    return ClaudeCodeAISettings(
        model="claude-model",
        prompt="Summarize release-note diffs.",
        max_diff_characters_per_request=max_characters,
    )


def _write_claude_config(root: Path) -> None:
    (root / "config" / "ai.json").write_text(
        json.dumps(
            {
                "backend": "claude_code",
                "model": "claude-model",
                "prompt": "Summarize release-note diffs.",
                "max_diff_characters_per_request": 12_000,
            }
        ),
        encoding="utf-8",
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ClaudeCodeRealSubprocessTests(unittest.TestCase):
    def test_real_runner_keeps_source_on_stdin_and_uses_fresh_restricted_processes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sentinel = root / "shell-metacharacters-must-remain-inert"
            diff = (
                f'$(touch "{sentinel}"); `touch "{sentinel}"`; '
                f'| touch "{sentinel}" && source text'
            )
            summarize_payload = f"Module: Pix\n\nDiff:\n{diff}"
            reduction = "- first\n- second"
            reduce_payload = f"Module: Pix\n\nPartial summaries:\n{reduction}"
            working_directories: list[Path] = []
            real_mkdtemp = tempfile.mkdtemp

            def recording_mkdtemp(*args, **kwargs) -> str:
                path = Path(real_mkdtemp(*args, **kwargs))
                working_directories.append(path)
                return str(path)

            with (
                installed_fake_claude(root) as record_path,
                patch(
                    "release_notes_generator.infrastructure.claude_code.tempfile.mkdtemp",
                    side_effect=recording_mkdtemp,
                ),
            ):
                client = ClaudeCodeClient(_claude_config())
                self.assertTrue(client.summarize("Pix", diff))
                self.assertTrue(client.reduce("Pix", reduction))

            records = load_fake_claude_records(record_path)

        self.assertFalse(sentinel.exists())
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["argument_names"], ["--version"])
        self.assertEqual(records[0]["payload_size"], 0)
        self.assertEqual(
            [record["argument_names"] for record in records[1:]],
            [EXPECTED_REQUEST_ARGUMENT_NAMES, EXPECTED_REQUEST_ARGUMENT_NAMES],
        )
        self.assertEqual(
            [record["payload_sha256"] for record in records[1:]],
            [_sha256(summarize_payload), _sha256(reduce_payload)],
        )
        self.assertEqual(
            [record["payload_size"] for record in records[1:]],
            [len(summarize_payload.encode("utf-8")), len(reduce_payload.encode("utf-8"))],
        )
        self.assertEqual(
            len({record["process_id"] for record in records}),
            len(records),
        )
        self.assertTrue(
            all(
                record["working_directory"]
                == {
                    "exists": True,
                    "is_directory": True,
                    "is_empty": True,
                    "contains_git_entry": False,
                }
                for record in records
            )
        )
        self.assertEqual(len(working_directories), len(records))
        self.assertTrue(all(not path.exists() for path in working_directories))
        allowed_record_fields = {
            "version",
            "argument_names",
            "payload_sha256",
            "payload_size",
            "process_id",
            "working_directory",
        }
        self.assertTrue(all(set(record) == allowed_record_fields for record in records))


class ClaudeCodeRealSubprocessFailureTests(unittest.TestCase):
    def test_fake_process_failures_are_sanitized_and_preserve_workflow_artifacts(
        self,
    ) -> None:
        for mode in (
            "timeout",
            "nonzero",
            "malformed",
            "login_failure",
            "usage_limit",
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                repository, _, _ = create_repository(root)
                runtime_path = write_runtime_configuration(root, repository)
                _write_claude_config(root)
                output_path = root / "analysis" / "release.pdf"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"existing pdf content")
                client = ClaudeCodeClient(
                    _claude_config(),
                    request_timeout_seconds=1,
                )

                with (
                    installed_fake_claude(root, mode=mode),
                    self.assertRaises(AISummarizationError) as context,
                ):
                    ReleaseNotesRunner(summary_client=client).run(runtime_path)

                self.assertEqual(output_path.read_bytes(), b"existing pdf content")
                self.assertEqual(
                    tuple((root / "analysis" / "diffs").glob("diff_*.md")),
                    (),
                )
                message = str(context.exception)
                for sensitive_value in (
                    "committed feature",
                    "FAKE-SENSITIVE-DIAGNOSTIC",
                    "FAKE-SENSITIVE-ACCOUNT",
                    "FAKE-SENSITIVE-QUOTA",
                    "FAKE-SENSITIVE-RAW-OUTPUT",
                ):
                    self.assertNotIn(sensitive_value, message)


if __name__ == "__main__":
    unittest.main()

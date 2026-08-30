"""Compatibility contract tests for the Claude Code drafting backend.

These tests pin the contract recorded in the change design after the
2026-08-28 spike: minimum supported executable version ``2.1.251`` and the
single JSON result envelope whose ``structured_output`` field carries the
schema-valid summary object. They are intentionally added before the
production adapter exists and must fail until it is implemented.
"""

import json
import unittest
from pathlib import Path

from release_notes_generator.infrastructure.claude_code import (
    MINIMUM_SUPPORTED_CLAUDE_CODE_VERSION,
    parse_claude_version_output,
    parse_structured_summary_envelope,
)
from release_notes_generator.services.summarization import AISummarizationError


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "claude_code"


def _fixture_envelope() -> dict[str, object]:
    with (FIXTURE_DIR / "envelope_success.json").open(encoding="utf-8") as file:
        return json.load(file)


class ClaudeCodeVersionContractTests(unittest.TestCase):
    def test_minimum_supported_version_matches_recorded_contract(self) -> None:
        self.assertEqual(MINIMUM_SUPPORTED_CLAUDE_CODE_VERSION, "2.1.251")

    def test_accepts_recorded_version_fixture_output(self) -> None:
        fixture_output = (FIXTURE_DIR / "version_output.txt").read_text(encoding="utf-8")

        self.assertEqual(parse_claude_version_output(fixture_output), "2.1.251")

    def test_accepts_versions_at_or_above_the_contract_floor(self) -> None:
        for output, expected in (
            ("2.1.251 (Claude Code)", "2.1.251"),
            ("2.1.252 (Claude Code)", "2.1.252"),
            ("2.2.0 (Claude Code)", "2.2.0"),
            ("3.0.0 (Claude Code)", "3.0.0"),
        ):
            with self.subTest(output=output):
                self.assertEqual(parse_claude_version_output(output), expected)

    def test_rejects_versions_below_the_contract_floor(self) -> None:
        for output in (
            "2.1.250 (Claude Code)",
            "2.0.999 (Claude Code)",
            "1.9.9 (Claude Code)",
            "0.2.125 (Claude Code)",
        ):
            with self.subTest(output=output):
                with self.assertRaises(AISummarizationError):
                    parse_claude_version_output(output)

    def test_rejects_unparseable_version_output(self) -> None:
        for output in ("", "   ", "\n", "Claude Code", "version unknown", "v2.one.0"):
            with self.subTest(output=repr(output)):
                with self.assertRaises(AISummarizationError):
                    parse_claude_version_output(output)


class ClaudeCodeEnvelopeContractTests(unittest.TestCase):
    def test_accepts_recorded_schema_valid_success_envelope(self) -> None:
        raw = (FIXTURE_DIR / "envelope_success.json").read_text(encoding="utf-8")

        self.assertEqual(
            parse_structured_summary_envelope(raw),
            "Sanitized example summary.",
        )

    def test_rejects_malformed_envelope_json(self) -> None:
        for raw in ("", "not json", "[]", '"result"', "{"):
            with self.subTest(raw=repr(raw)):
                with self.assertRaises(AISummarizationError):
                    parse_structured_summary_envelope(raw)

    def test_rejects_envelopes_outside_the_result_success_contract(self) -> None:
        divergent_envelopes = (
            ("error-flag", {"is_error": True}),
            ("wrong-type", {"type": "message"}),
            ("wrong-subtype", {"subtype": "error_during_execution"}),
            ("missing-type", {"type": None}),
        )
        for name, overrides in divergent_envelopes:
            with self.subTest(name=name):
                envelope = _fixture_envelope()
                for key, value in overrides.items():
                    if value is None:
                        envelope.pop(key, None)
                    else:
                        envelope[key] = value

                with self.assertRaises(AISummarizationError):
                    parse_structured_summary_envelope(json.dumps(envelope))

    def test_rejects_missing_or_invalid_structured_output(self) -> None:
        divergent_outputs = (
            ("missing", None),
            ("non-object", "summary text"),
            ("empty-object", {}),
            ("additional-field", {"summary": "ok", "extra": "field"}),
            ("non-string-summary", {"summary": 42}),
            ("empty-summary", {"summary": ""}),
            ("blank-summary", {"summary": "   "}),
        )
        for name, structured_output in divergent_outputs:
            with self.subTest(name=name):
                envelope = _fixture_envelope()
                if structured_output is None:
                    envelope.pop("structured_output", None)
                else:
                    envelope["structured_output"] = structured_output

                with self.assertRaises(AISummarizationError):
                    parse_structured_summary_envelope(json.dumps(envelope))

    def test_diagnostic_fields_are_not_release_content(self) -> None:
        envelope = _fixture_envelope()
        envelope.pop("structured_output", None)
        envelope["result"] = '{"summary":"Only structured output is trusted."}'

        with self.assertRaises(AISummarizationError):
            parse_structured_summary_envelope(json.dumps(envelope))


if __name__ == "__main__":
    unittest.main()

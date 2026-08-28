import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.claude_code import ClaudeCodeClient
from release_notes_generator.configuration import (
    ClaudeCodeAIConfig,
    OpenAICompatibleAIConfig,
)
from release_notes_generator.summarization import (
    AISummarizationError,
    OpenAIChatClient,
    SummarizationOutcome,
    SummarizationProvenance,
    create_summary_client,
    split_diff_content,
    summarize_diff_files,
    summarize_diff_files_with_provenance,
)


class RecordingSummaryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.reduction_calls: list[tuple[str, str]] = []

    def summarize(self, module_name: str, diff_content: str) -> str:
        self.calls.append((module_name, diff_content))
        return f"{module_name} summary"

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        self.reduction_calls.append((module_name, partial_summaries))
        return f"{module_name} reduced summary"


class SummarizationTests(unittest.TestCase):
    def test_ai_summarization_receives_separate_category_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pix_diff_path = Path(temp_dir) / "diff_pix.md"
            global_diff_path = Path(temp_dir) / "diff_globalloyalty.md"
            pix_diff_path.write_text("pix diff", encoding="utf-8")
            global_diff_path.write_text("global diff", encoding="utf-8")
            client = RecordingSummaryClient()

            summaries = summarize_diff_files(
                {"Pix": pix_diff_path, "GlobalLoyalty": global_diff_path},
                client,
                max_characters_per_request=100,
            )

        self.assertEqual(
            summaries,
            {"Pix": "Pix summary", "GlobalLoyalty": "GlobalLoyalty summary"},
        )
        self.assertEqual(
            client.calls,
            [("Pix", "pix diff"), ("GlobalLoyalty", "global diff")],
        )

    def test_no_ai_request_contains_unlisted_or_unmapped_diff_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pix_diff_path = Path(temp_dir) / "diff_pix.md"
            ignored_diff_path = Path(temp_dir) / "diff_ignored.md"
            pix_diff_path.write_text("authorized pix diff", encoding="utf-8")
            ignored_diff_path.write_text("unauthorized ignored diff", encoding="utf-8")
            client = RecordingSummaryClient()

            summarize_diff_files(
                {"Pix": pix_diff_path}, client, max_characters_per_request=100
            )

        self.assertEqual(client.calls, [("Pix", "authorized pix diff")])

    def test_missing_diff_file_raises_summarization_error(self) -> None:
        with self.assertRaises(AISummarizationError):
            summarize_diff_files(
                {"Pix": Path("missing-diff.md")},
                RecordingSummaryClient(),
                max_characters_per_request=100,
            )

    def test_in_limit_diff_remains_one_lossless_chunk(self) -> None:
        content = "commit a1\nsmall diff\n"

        chunks = split_diff_content(content, max_characters=100)

        self.assertEqual(chunks, (content,))

    def test_diff_chunks_prefer_commit_boundaries_and_preserve_exact_content(self) -> None:
        content = "commit a1\nfirst\n\ncommit b2\nsecond\n\ncommit c3\nthird\n"

        chunks = split_diff_content(content, max_characters=30)

        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), content)
        self.assertTrue(all(len(chunk) <= 30 for chunk in chunks))
        self.assertTrue(any(chunk.startswith("commit b2") for chunk in chunks))

    def test_one_oversized_commit_is_split_losslessly_at_line_boundaries(self) -> None:
        content = "commit a1\n" + "line one\n" + ("x" * 25) + "\nline three\n"

        chunks = split_diff_content(content, max_characters=12)

        self.assertEqual("".join(chunks), content)
        self.assertTrue(all(len(chunk) <= 12 for chunk in chunks))
        self.assertGreater(len(chunks), 3)

    def test_multiple_chunks_are_reduced_to_one_bounded_module_summary(self) -> None:
        class ReducingClient:
            def __init__(self) -> None:
                self.summary_calls: list[tuple[str, str]] = []
                self.reduction_calls: list[tuple[str, str]] = []

            def summarize(self, module_name: str, diff_content: str) -> str:
                self.summary_calls.append((module_name, diff_content))
                return f"part-{len(self.summary_calls)}"

            def reduce(self, module_name: str, partial_summaries: str) -> str:
                self.reduction_calls.append((module_name, partial_summaries))
                return "final"

        with tempfile.TemporaryDirectory() as temp_dir:
            diff_path = Path(temp_dir) / "diff_pix.md"
            diff_path.write_text("commit a\n123456789\ncommit b\nabcdefghi\n", encoding="utf-8")
            client = ReducingClient()

            summaries = summarize_diff_files(
                {"Pix": diff_path}, client, max_characters_per_request=20
            )

        self.assertEqual(summaries, {"Pix": "final"})
        self.assertGreater(len(client.summary_calls), 1)
        self.assertTrue(all(module == "Pix" for module, _ in client.summary_calls))
        self.assertTrue(all(len(content) <= 20 for _, content in client.summary_calls))
        self.assertTrue(all(module == "Pix" for module, _ in client.reduction_calls))
        self.assertTrue(all(len(content) <= 20 for _, content in client.reduction_calls))

    def test_reduction_recurses_when_partial_summaries_do_not_fit_together(self) -> None:
        class ShrinkingClient:
            def __init__(self) -> None:
                self.summary_count = 0
                self.reduction_calls: list[str] = []

            def summarize(self, module_name: str, diff_content: str) -> str:
                self.summary_count += 1
                return f"summary{self.summary_count}"

            def reduce(self, module_name: str, partial_summaries: str) -> str:
                self.reduction_calls.append(partial_summaries)
                return "x"

        with tempfile.TemporaryDirectory() as temp_dir:
            diff_path = Path(temp_dir) / "diff.md"
            diff_path.write_text("a" * 30, encoding="utf-8")
            client = ShrinkingClient()

            summaries = summarize_diff_files(
                {"Only": diff_path}, client, max_characters_per_request=10
            )

        self.assertEqual(summaries, {"Only": "x"})
        self.assertGreaterEqual(len(client.reduction_calls), 4)
        self.assertTrue(all(len(content) <= 10 for content in client.reduction_calls))

    def test_openai_chat_client_sends_expected_request_and_returns_summary(self) -> None:
        config = OpenAICompatibleAIConfig(
            api_url="https://api.example.test/v1/chat/completions",
            model="summary-model",
            api_key_env_var="CHANGE_LOG_SUMMARY_AI_API_KEY",
            prompt="Summarize release-note diffs.",
            max_diff_characters_per_request=1000,
        )
        client = OpenAIChatClient.from_config(
            config,
            environ={"CHANGE_LOG_SUMMARY_AI_API_KEY": "test-api-key"},
        )

        with patch("release_notes_generator.summarization.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
                {"choices": [{"message": {"content": "Pix summary"}}]}
            ).encode("utf-8")

            summary = client.summarize("Pix", "pix diff")

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(summary, "Pix summary")
        self.assertEqual(request.full_url, "https://api.example.test/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-api-key")
        self.assertEqual(headers["accept"], "application/json")
        self.assertEqual(headers["user-agent"], "change-log-summary/0.1")
        self.assertEqual(payload["model"], "summary-model")
        self.assertEqual(payload["messages"][0]["content"], "Summarize release-note diffs.")
        self.assertIn("Module: Pix", payload["messages"][1]["content"])
        self.assertIn("pix diff", payload["messages"][1]["content"])

    def test_openai_chat_client_requires_api_key_from_environment(self) -> None:
        config = OpenAICompatibleAIConfig(
            api_url="https://api.example.test/v1/chat/completions",
            model="summary-model",
            api_key_env_var="CHANGE_LOG_SUMMARY_AI_API_KEY",
            prompt="Summarize release-note diffs.",
            max_diff_characters_per_request=1000,
        )

        with self.assertRaises(AISummarizationError):
            OpenAIChatClient.from_config(config, environ={})

    def test_openai_chat_client_can_load_api_key_from_env_file(self) -> None:
        config = OpenAICompatibleAIConfig(
            api_url="https://api.example.test/v1/chat/completions",
            model="summary-model",
            api_key_env_var="CHANGE_LOG_SUMMARY_AI_API_KEY",
            prompt="Summarize release-note diffs.",
            max_diff_characters_per_request=1000,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env.local"
            env_file.write_text("CHANGE_LOG_SUMMARY_AI_API_KEY=test-api-key\n", encoding="utf-8")

            client = OpenAIChatClient.from_config(config, environ={}, env_file=env_file)

        with patch("release_notes_generator.summarization.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
                {"choices": [{"message": {"content": "Pix summary"}}]}
            ).encode("utf-8")

            client.summarize("Pix", "pix diff")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-api-key")


class BackendFactoryTests(unittest.TestCase):
    def test_claude_code_configuration_builds_only_the_claude_client(self) -> None:
        config = ClaudeCodeAIConfig(
            model="claude-model",
            prompt="Summarize.",
            max_diff_characters_per_request=1000,
        )

        with patch.object(OpenAIChatClient, "from_config") as from_config:
            client = create_summary_client(config, environ={})

        self.assertIsInstance(client, ClaudeCodeClient)
        from_config.assert_not_called()

    def test_openai_configuration_builds_only_the_openai_client(self) -> None:
        config = OpenAICompatibleAIConfig(
            api_url="https://api.example.test/v1/chat/completions",
            model="summary-model",
            api_key_env_var="CHANGE_LOG_SUMMARY_AI_API_KEY",
            prompt="Summarize release-note diffs.",
            max_diff_characters_per_request=1000,
        )

        with patch("release_notes_generator.claude_code.ClaudeCodeClient") as claude_client:
            client = create_summary_client(
                config,
                environ={"CHANGE_LOG_SUMMARY_AI_API_KEY": "test-api-key"},
            )

        self.assertIsInstance(client, OpenAIChatClient)
        claude_client.assert_not_called()

    def test_unknown_configuration_type_is_rejected(self) -> None:
        with self.assertRaises(AISummarizationError):
            create_summary_client(object(), environ={})  # type: ignore[arg-type]

    def test_claude_code_construction_requires_no_api_key_environment(self) -> None:
        config = ClaudeCodeAIConfig(
            model="claude-model",
            prompt="Summarize.",
            max_diff_characters_per_request=1000,
        )

        client = create_summary_client(config, environ={})

        self.assertIsInstance(client, ClaudeCodeClient)


class ProvenanceCarryingClient(RecordingSummaryClient):
    def execution_provenance(self) -> SummarizationProvenance:
        return SummarizationProvenance(
            backend="claude_code",
            model="claude-model",
            claude_code_version="2.1.251",
        )


class SummarizationOutcomeTests(unittest.TestCase):
    def test_outcome_contains_ordered_summaries_and_no_provenance_for_plain_clients(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pix_diff_path = Path(temp_dir) / "diff_pix.md"
            global_diff_path = Path(temp_dir) / "diff_globalloyalty.md"
            pix_diff_path.write_text("pix diff", encoding="utf-8")
            global_diff_path.write_text("global diff", encoding="utf-8")
            client = RecordingSummaryClient()

            outcome = summarize_diff_files_with_provenance(
                {"Pix": pix_diff_path, "GlobalLoyalty": global_diff_path},
                client,
                max_characters_per_request=100,
            )

        self.assertEqual(
            outcome.module_summaries,
            (("Pix", "Pix summary"), ("GlobalLoyalty", "GlobalLoyalty summary")),
        )
        self.assertEqual(
            outcome.summaries,
            {"Pix": "Pix summary", "GlobalLoyalty": "GlobalLoyalty summary"},
        )
        self.assertIsNone(outcome.provenance)
        self.assertEqual(
            client.calls,
            [("Pix", "pix diff"), ("GlobalLoyalty", "global diff")],
        )

    def test_outcome_is_immutable(self) -> None:
        outcome = SummarizationOutcome(
            module_summaries=(("Pix", "summary"),),
            provenance=None,
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            outcome.module_summaries = ()  # type: ignore[misc]

    def test_outcome_carries_client_execution_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            diff_path = Path(temp_dir) / "diff_pix.md"
            diff_path.write_text("pix diff", encoding="utf-8")

            outcome = summarize_diff_files_with_provenance(
                {"Pix": diff_path},
                ProvenanceCarryingClient(),
                max_characters_per_request=100,
            )

        self.assertEqual(
            outcome.provenance,
            SummarizationProvenance(
                backend="claude_code",
                model="claude-model",
                claude_code_version="2.1.251",
            ),
        )

    def test_outcome_preserves_bounded_chunking_and_sequential_reduction(self) -> None:
        class ReducingClient:
            def __init__(self) -> None:
                self.summary_calls: list[tuple[str, str]] = []
                self.reduction_calls: list[tuple[str, str]] = []

            def summarize(self, module_name: str, diff_content: str) -> str:
                self.summary_calls.append((module_name, diff_content))
                return f"part-{len(self.summary_calls)}"

            def reduce(self, module_name: str, partial_summaries: str) -> str:
                self.reduction_calls.append((module_name, partial_summaries))
                return "final"

        with tempfile.TemporaryDirectory() as temp_dir:
            diff_path = Path(temp_dir) / "diff_pix.md"
            diff_path.write_text(
                "commit a\n123456789\ncommit b\nabcdefghi\n", encoding="utf-8"
            )
            client = ReducingClient()

            outcome = summarize_diff_files_with_provenance(
                {"Pix": diff_path}, client, max_characters_per_request=20
            )

        self.assertEqual(outcome.summaries, {"Pix": "final"})
        self.assertGreater(len(client.summary_calls), 1)
        self.assertGreaterEqual(len(client.reduction_calls), 1)
        self.assertTrue(all(len(content) <= 20 for _, content in client.summary_calls))
        self.assertTrue(
            all(len(content) <= 20 for _, content in client.reduction_calls)
        )


if __name__ == "__main__":
    unittest.main()

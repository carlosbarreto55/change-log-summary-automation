import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.configuration import AIConfig
from release_notes_generator.summarization import (
    AISummarizationError,
    OpenAIChatClient,
    summarize_diff_files,
)


class RecordingSummaryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def summarize(self, module_name: str, diff_content: str) -> str:
        self.calls.append((module_name, diff_content))
        return f"{module_name} summary"


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

            summarize_diff_files({"Pix": pix_diff_path}, client)

        self.assertEqual(client.calls, [("Pix", "authorized pix diff")])

    def test_missing_diff_file_raises_summarization_error(self) -> None:
        with self.assertRaises(AISummarizationError):
            summarize_diff_files({"Pix": Path("missing-diff.md")}, RecordingSummaryClient())

    def test_openai_chat_client_sends_expected_request_and_returns_summary(self) -> None:
        config = AIConfig(
            api_url="https://api.example.test/v1/chat/completions",
            model="summary-model",
            api_key_env_var="CHANGE_LOG_SUMMARY_AI_API_KEY",
            prompt="Summarize release-note diffs.",
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
        config = AIConfig(
            api_url="https://api.example.test/v1/chat/completions",
            model="summary-model",
            api_key_env_var="CHANGE_LOG_SUMMARY_AI_API_KEY",
            prompt="Summarize release-note diffs.",
        )

        with self.assertRaises(AISummarizationError):
            OpenAIChatClient.from_config(config, environ={})

    def test_openai_chat_client_can_load_api_key_from_env_file(self) -> None:
        config = AIConfig(
            api_url="https://api.example.test/v1/chat/completions",
            model="summary-model",
            api_key_env_var="CHANGE_LOG_SUMMARY_AI_API_KEY",
            prompt="Summarize release-note diffs.",
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


if __name__ == "__main__":
    unittest.main()

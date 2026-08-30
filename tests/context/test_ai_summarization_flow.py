import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from release_notes_generator.domain.analysis import DiffArtifact
from release_notes_generator.domain.configuration import ClaudeCodeAISettings, ModuleDefinition, ModulePolicy
from release_notes_generator.domain.repository import ClassifiedCommit
from release_notes_generator.infrastructure.artifacts import LocalArtifactStore
from release_notes_generator.services.release_document import ReleaseDocumentService
from release_notes_generator.services.summarization import SummarizationService


class RecordingSummaryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def summarize(self, module_name: str, diff_content: str) -> str:
        self.calls.append((module_name, diff_content))
        return f"- Summary part for {module_name}"

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        self.calls.append((module_name, partial_summaries))
        return "- Final"


class UnusedFactory:
    def create(self, settings, env_file):
        raise AssertionError("injected client should bypass backend creation")


def summarize_diff_files(diff_files, client, max_characters_per_request):
    outcome = SummarizationService(
        LocalArtifactStore(), UnusedFactory(), client
    ).summarize(
        tuple(DiffArtifact(name, path) for name, path in diff_files.items()),
        ClaudeCodeAISettings("test", "test", max_characters_per_request),
        None,
    )
    return outcome.summaries


def compose_release_document(summaries, modules, repository_name, accepted_commits):
    return ReleaseDocumentService().compose(
        summaries, modules, repository_name, accepted_commits
    )


class AISummarizationFlowTests(unittest.TestCase):
    def test_pix_global_loyalty_and_transit_summarization_calls_remain_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            diff_dir = Path(temp_dir)
            diff_files = {
                "Pix": diff_dir / "diff_pix.md",
                "GlobalLoyalty": diff_dir / "diff_globalloyalty.md",
                "TransitOpenLoop": diff_dir / "diff_transitopenloop.md",
            }
            diff_files["Pix"].write_text("pix-only diff", encoding="utf-8")
            diff_files["GlobalLoyalty"].write_text("global-loyalty-only diff", encoding="utf-8")
            diff_files["TransitOpenLoop"].write_text("transit-only diff", encoding="utf-8")
            (diff_dir / "diff_unmapped.md").write_text("must not be summarized", encoding="utf-8")
            client = RecordingSummaryClient()

            summaries = summarize_diff_files(
                diff_files, client, max_characters_per_request=100
            )

        self.assertEqual(
            summaries,
            {
                "Pix": "- Summary part for Pix",
                "GlobalLoyalty": "- Summary part for GlobalLoyalty",
                "TransitOpenLoop": "- Summary part for TransitOpenLoop",
            },
        )
        self.assertEqual(
            client.calls,
            [
                ("Pix", "pix-only diff"),
                ("GlobalLoyalty", "global-loyalty-only diff"),
                ("TransitOpenLoop", "transit-only diff"),
            ],
        )

    def test_multiple_chunks_flow_into_final_configured_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            diff_path = Path(temp_dir) / "diff_payments.md"
            diff_path.write_text("commit a\n" + ("x" * 40), encoding="utf-8")
            client = RecordingSummaryClient()

            summaries = summarize_diff_files(
                {"Payments": diff_path}, client, max_characters_per_request=20
            )
            document = compose_release_document(
                summaries,
                ModulePolicy(
                    modules=(
                        ModuleDefinition("Payments", ("PAY:",), "Customer Features"),
                    )
                ),
                repository_name="payments",
                accepted_commits=(
                    ClassifiedCommit(
                        "payment",
                        "approved@example.com",
                        "PAY: change",
                        "Payments",
                        datetime(2026, 1, 3, 12, tzinfo=timezone.utc),
                    ),
                ),
            )

        self.assertGreater(len(client.calls), 2)
        self.assertEqual(document.sections[0].title, "Customer Features")
        self.assertEqual(document.sections[0].modules[0].summary, "- Final")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from release_notes_generator.summarization import summarize_diff_files


class RecordingSummaryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def summarize(self, module_name: str, diff_content: str) -> str:
        self.calls.append((module_name, diff_content))
        return f"Summary for {module_name}"


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

            summaries = summarize_diff_files(diff_files, client)

        self.assertEqual(
            summaries,
            {
                "Pix": "Summary for Pix",
                "GlobalLoyalty": "Summary for GlobalLoyalty",
                "TransitOpenLoop": "Summary for TransitOpenLoop",
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


if __name__ == "__main__":
    unittest.main()

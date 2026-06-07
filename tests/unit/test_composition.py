import tempfile
import unittest
from pathlib import Path

from release_notes_generator.composition import compose_release_notes, export_release_notes


class ReleaseNotesCompositionTests(unittest.TestCase):
    def test_final_markdown_contains_global_features_and_pix_sections(self) -> None:
        markdown = compose_release_notes(
            {
                "Pix": "- Pix summary",
                "GlobalLoyalty": "- Global loyalty summary",
                "TransitOpenLoop": "- Transit summary",
            }
        )

        self.assertIn("## Global Features", markdown)
        self.assertIn("## Pix", markdown)

    def test_global_loyalty_and_transit_summaries_merge_under_global_features(self) -> None:
        markdown = compose_release_notes(
            {
                "Pix": "- Pix summary",
                "GlobalLoyalty": "- Global loyalty summary",
                "TransitOpenLoop": "- Transit summary",
            }
        )

        global_features_index = markdown.index("## Global Features")
        global_loyalty_index = markdown.index("- Global loyalty summary")
        transit_index = markdown.index("- Transit summary")
        pix_section_index = markdown.index("## Pix")

        self.assertLess(global_features_index, global_loyalty_index)
        self.assertLess(global_loyalty_index, pix_section_index)
        self.assertLess(transit_index, pix_section_index)

    def test_pix_summary_is_inserted_under_pix_section(self) -> None:
        markdown = compose_release_notes(
            {
                "Pix": "- Pix summary",
                "GlobalLoyalty": "- Global loyalty summary",
                "TransitOpenLoop": "- Transit summary",
            }
        )

        self.assertLess(markdown.index("## Pix"), markdown.index("- Pix summary"))

    def test_export_release_notes_writes_single_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "release_notes.md"

            result_path = export_release_notes(
                {
                    "Pix": "- Pix summary",
                    "GlobalLoyalty": "- Global loyalty summary",
                    "TransitOpenLoop": "- Transit summary",
                },
                output_path,
            )

            generated_files = tuple(Path(temp_dir).iterdir())
            generated_content = output_path.read_text(encoding="utf-8")

        self.assertEqual(result_path, output_path)
        self.assertEqual(generated_files, (output_path,))
        self.assertEqual(output_path.suffix, ".md")
        self.assertIn("## Global Features", generated_content)


if __name__ == "__main__":
    unittest.main()

import unittest

from release_notes_generator.composition import (
    ReleaseDocument,
    ReleaseModuleSummary,
    ReleaseSection,
    compose_release_document,
)
from release_notes_generator.configuration import ModuleConfig, ModuleDefinition


class ReleaseNotesCompositionTests(unittest.TestCase):
    def test_sections_and_modules_follow_configuration_order(self) -> None:
        document = compose_release_document(
            {
                "Pix": "- Pix summary",
                "GlobalLoyalty": "- Global loyalty summary",
                "TransitOpenLoop": "- Transit summary",
            },
            _module_config(),
        )

        self.assertEqual(
            document,
            ReleaseDocument(
                title="Release Notes",
                sections=(
                    ReleaseSection(
                        title="Global Features",
                        modules=(
                            ReleaseModuleSummary("GlobalLoyalty", "- Global loyalty summary"),
                            ReleaseModuleSummary("TransitOpenLoop", "- Transit summary"),
                        ),
                    ),
                    ReleaseSection(
                        title="Pix",
                        modules=(ReleaseModuleSummary("Pix", "- Pix summary"),),
                    ),
                ),
            ),
        )

    def test_empty_modules_and_sections_are_omitted(self) -> None:
        document = compose_release_document(
            {"Pix": "- Pix summary", "GlobalLoyalty": "", "Unknown": "ignored"},
            _module_config(),
        )

        self.assertEqual(
            document.sections,
            (
                ReleaseSection(
                    title="Pix",
                    modules=(ReleaseModuleSummary("Pix", "- Pix summary"),),
                ),
            ),
        )

    def test_no_qualifying_changes_document_has_clear_message(self) -> None:
        document = compose_release_document({}, _module_config())

        self.assertEqual(document.title, "Release Notes")
        self.assertEqual(document.sections, ())
        self.assertEqual(document.empty_message, "No qualifying changes.")


def _module_config() -> ModuleConfig:
    return ModuleConfig(
        modules=(
            ModuleDefinition("GlobalLoyalty", ("GL:",), "Global Features"),
            ModuleDefinition("TransitOpenLoop", ("TOL:",), "Global Features"),
            ModuleDefinition("Pix", ("Pix:",), "Pix"),
            ModuleDefinition("Unused", ("Unused:",), "Empty Section"),
        )
    )


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from release_notes_generator.configuration import (
    ConfigurationError,
    load_module_config,
    load_release_marker_config,
    load_user_config,
)


class ConfigurationTests(unittest.TestCase):
    def test_load_user_config_reads_default_approved_author_emails(self) -> None:
        config = load_user_config()

        self.assertEqual(config.approved_author_emails, ())

    def test_load_module_config_reads_default_supported_modules(self) -> None:
        config = load_module_config()

        self.assertEqual(
            config.module_tags,
            {
                "Pix": ("Pix",),
                "GlobalLoyalty": ("GlobalLoyalty",),
                "TransitOpenLoop": ("TransitOpenLoop",),
            },
        )

    def test_load_release_marker_config_reads_default_marker(self) -> None:
        config = load_release_marker_config()

        self.assertEqual(config.marker, "[Release]")

    def test_load_user_config_accepts_explicit_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "user.json"
            config_path.write_text(
                json.dumps({"approved_author_emails": ["dev@example.com"]}),
                encoding="utf-8",
            )

            config = load_user_config(config_path)

        self.assertEqual(config.approved_author_emails, ("dev@example.com",))

    def test_missing_configuration_file_raises_error(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_user_config(Path("missing-user-config.json"))

    def test_invalid_configuration_file_raises_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "user.json"
            config_path.write_text("not json", encoding="utf-8")

            with self.assertRaises(ConfigurationError):
                load_user_config(config_path)

    def test_unusable_users_configuration_raises_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "user.json"
            config_path.write_text(
                json.dumps({"approved_author_emails": [1]}),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigurationError):
                load_user_config(config_path)


if __name__ == "__main__":
    unittest.main()

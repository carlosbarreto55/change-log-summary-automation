import json
import tempfile
import unittest
from pathlib import Path

from release_notes_generator.configuration import (
    load_ai_config,
    ConfigurationError,
    load_module_config,
    load_release_marker_config,
    load_runtime_config,
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

    def test_load_ai_config_reads_api_settings_without_secret_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.json"
            config_path.write_text(
                json.dumps(
                    {
                        "api_url": "https://api.example.test/v1/chat/completions",
                        "model": "summary-model",
                        "api_key_env_var": "CHANGE_LOG_SUMMARY_AI_API_KEY",
                        "prompt": "Summarize this diff.",
                    }
                ),
                encoding="utf-8",
            )

            config = load_ai_config(config_path)

        self.assertEqual(config.api_url, "https://api.example.test/v1/chat/completions")
        self.assertEqual(config.model, "summary-model")
        self.assertEqual(config.api_key_env_var, "CHANGE_LOG_SUMMARY_AI_API_KEY")
        self.assertEqual(config.prompt, "Summarize this diff.")
        self.assertFalse(hasattr(config, "api_key"))

    def test_load_runtime_config_resolves_paths_relative_to_runtime_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            runtime_config_path = config_dir / "workflow.json"
            runtime_config_path.write_text(
                json.dumps(
                    {
                        "repository_path": "../target-repo",
                        "user_config_path": "user.json",
                        "module_config_path": "module.json",
                        "release_marker_config_path": "releaseMarker.json",
                        "ai_config_path": "ai.json",
                        "temp_diff_dir": "../tmp/diffs",
                        "output_path": "../output/release_notes.md",
                        "env_file_path": "../.env.local",
                    }
                ),
                encoding="utf-8",
            )

            config = load_runtime_config(runtime_config_path)

        self.assertEqual(config.repository_path, (config_dir / "../target-repo").resolve())
        self.assertEqual(config.user_config_path, (config_dir / "user.json").resolve())
        self.assertEqual(config.module_config_path, (config_dir / "module.json").resolve())
        self.assertEqual(
            config.release_marker_config_path,
            (config_dir / "releaseMarker.json").resolve(),
        )
        self.assertEqual(config.ai_config_path, (config_dir / "ai.json").resolve())
        self.assertEqual(config.temp_diff_dir, (config_dir / "../tmp/diffs").resolve())
        self.assertEqual(config.output_path, (config_dir / "../output/release_notes.md").resolve())
        self.assertEqual(config.env_file_path, (config_dir / "../.env.local").resolve())

    def test_load_runtime_config_requires_markdown_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_config_path = Path(temp_dir) / "workflow.json"
            runtime_config_path.write_text(
                json.dumps(
                    {
                        "repository_path": "repo",
                        "user_config_path": "user.json",
                        "module_config_path": "module.json",
                        "release_marker_config_path": "releaseMarker.json",
                        "ai_config_path": "ai.json",
                        "temp_diff_dir": "tmp/diffs",
                        "output_path": "output/release_notes.txt",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigurationError):
                load_runtime_config(runtime_config_path)

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

    def test_unusable_ai_configuration_raises_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.json"
            config_path.write_text(
                json.dumps({"api_url": "https://api.example.test", "model": ""}),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigurationError):
                load_ai_config(config_path)


if __name__ == "__main__":
    unittest.main()

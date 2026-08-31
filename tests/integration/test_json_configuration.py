from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from release_notes_generator.domain.configuration import (
    AIBackend,
    ReportMode,
    RepositoryUpdateMode,
)
from release_notes_generator.infrastructure.json_reader import FileJSONReader
from release_notes_generator.services.configuration import ConfigurationService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def load_runtime_config(path: Path):
    return ConfigurationService(FileJSONReader()).load(path)


def load_ai_config(ai_path: Path):
    with tempfile.TemporaryDirectory() as temp_dir:
        runtime_path = Path(temp_dir) / "workflow.json"
        runtime_path.write_text(
            json.dumps(
                {
                    "repository_path": "/tmp/repository",
                    "head_ref": "head",
                    "base_ref": "base",
                    "user_config_path": str(CONFIG_DIR / "userIT.json"),
                    "module_config_path": str(CONFIG_DIR / "moduleIT.json"),
                    "ai_config_path": str(ai_path),
                    "temp_diff_dir": "/tmp/diffs",
                    "output_path": "/tmp/release.pdf",
                }
            ),
            encoding="utf-8",
        )
        return load_runtime_config(runtime_path).ai


class CommittedRuntimeConfigurationTests(unittest.TestCase):
    def test_every_committed_runtime_json_declares_safe_explicit_selectors(
        self,
    ) -> None:
        runtime_paths = tuple(sorted(CONFIG_DIR.glob("workflow*.json")))
        self.assertTrue(runtime_paths)

        for runtime_path in runtime_paths:
            with self.subTest(runtime_path=runtime_path):
                config = load_runtime_config(runtime_path)
                self.assertTrue(config.head_ref.strip())
                self.assertNotEqual(
                    config.base_ref is None,
                    config.release_marker is None,
                )
                if config.report_mode is ReportMode.AI_SUMMARY:
                    self.assertIsNotNone(config.temp_diff_dir)
                    temp_diff_dir = config.temp_diff_dir
                    if temp_diff_dir is None:
                        raise AssertionError("AI runtime must retain its diff path.")
                    self.assertNotEqual(temp_diff_dir, config.repository_path)
                    self.assertNotIn(config.repository_path, temp_diff_dir.parents)
                else:
                    raw = json.loads(runtime_path.read_text(encoding="utf-8"))
                    self.assertIsNone(config.ai)
                    self.assertIsNone(config.env_file_path)
                    self.assertIsNone(config.temp_diff_dir)
                    self.assertNotIn("ai_config_path", raw)
                    self.assertNotIn("env_file_path", raw)
                    self.assertNotIn("temp_diff_dir", raw)
                if (
                    config.repository_update_mode
                    is not RepositoryUpdateMode.LEGACY_IN_PLACE_SYNC
                ):
                    self.assertNotEqual(
                        config.output_path,
                        config.repository_path,
                    )
                    self.assertNotIn(
                        config.repository_path,
                        config.output_path.parents,
                    )
                if config.release_marker is not None:
                    self.assertTrue(config.release_marker.strip())

    def test_integration_ai_json_names_its_backend_explicitly(self) -> None:
        ai_path = CONFIG_DIR / "aiIT.json"
        raw = json.loads(ai_path.read_text(encoding="utf-8"))
        config = load_ai_config(ai_path)

        self.assertEqual(raw.get("backend"), "openai_compatible")
        self.assertEqual(config.backend, AIBackend.OPENAI_COMPATIBLE)
        self.assertNotIn("api_key", raw)

    def test_claude_code_integration_json_is_keyless_and_backend_specific(
        self,
    ) -> None:
        ai_path = CONFIG_DIR / "aiClaudeCodeIT.json"
        raw = json.loads(ai_path.read_text(encoding="utf-8"))
        config = load_ai_config(ai_path)

        self.assertEqual(config.backend, AIBackend.CLAUDE_CODE)
        self.assertEqual(raw.get("backend"), "claude_code")
        for forbidden_field in (
            "api_url",
            "api_key_env_var",
            "api_key",
            "oauth_token",
            "credential_path",
        ):
            self.assertNotIn(forbidden_field, raw)

    def test_legacy_no_backend_ai_json_retains_openai_compatible_behavior(self) -> None:
        legacy_path = CONFIG_DIR / "aiLegacyNoBackendIT.json"
        raw = json.loads(legacy_path.read_text(encoding="utf-8"))
        config = load_ai_config(legacy_path)

        self.assertNotIn("backend", raw)
        self.assertEqual(config.backend, AIBackend.OPENAI_COMPATIBLE)
        self.assertTrue(config.api_url)
        self.assertTrue(config.api_key_env_var)
        self.assertNotIn("api_key", raw)

    def test_linux_runtime_intentionally_uses_omitted_read_only_default(
        self,
    ) -> None:
        runtime_path = CONFIG_DIR / "workflowLinuxIT.json"
        raw = runtime_path.read_text(encoding="utf-8")
        config = load_runtime_config(runtime_path)

        self.assertNotIn('"repository_update_mode"', raw)
        self.assertIs(
            config.repository_update_mode,
            RepositoryUpdateMode.READ_ONLY,
        )


if __name__ == "__main__":
    unittest.main()

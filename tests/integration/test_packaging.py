"""Wheel smoke coverage for backend configuration and executable activation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from release_notes_generator.paths import PROJECT_ROOT


class WheelBackendConfigurationTests(unittest.TestCase):
    def test_installed_wheel_loads_both_backends_without_a_claude_sdk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wheel_directory = root / "wheel"
            installed_directory = root / "installed"
            source_directory = root / "source"
            wheel_directory.mkdir()
            source_directory.mkdir()
            shutil.copytree(
                PROJECT_ROOT / "release_notes_generator",
                source_directory / "release_notes_generator",
            )
            shutil.copy2(PROJECT_ROOT / "pyproject.toml", source_directory)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--disable-pip-version-check",
                    "--no-deps",
                    "--wheel-dir",
                    str(wheel_directory),
                    str(source_directory),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
            wheel_path = next(wheel_directory.glob("change_log_summary-*.whl"))
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-deps",
                    "--target",
                    str(installed_directory),
                    str(wheel_path),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )

            openai_path = root / "openai.json"
            openai_path.write_text(
                json.dumps(
                    {
                        "backend": "openai_compatible",
                        "api_url": "https://provider.example/v1/chat/completions",
                        "model": "summary-model",
                        "api_key_env_var": "AI_API_KEY",
                        "prompt": "Summarize.",
                        "max_diff_characters_per_request": 1000,
                    }
                ),
                encoding="utf-8",
            )
            claude_path = root / "claude.json"
            claude_path.write_text(
                json.dumps(
                    {
                        "backend": "claude_code",
                        "model": "claude-model",
                        "prompt": "Summarize.",
                        "max_diff_characters_per_request": 1000,
                    }
                ),
                encoding="utf-8",
            )

            smoke_script = textwrap.dedent(
                """
                import os
                import sys
                from pathlib import Path

                installed = Path(os.environ["INSTALLED_PACKAGE_ROOT"]).resolve()
                sys.path.insert(0, str(installed))

                from release_notes_generator.claude_code import ClaudeCodeClient
                from release_notes_generator.configuration import (
                    AIBackend,
                    load_ai_config,
                )
                from release_notes_generator.summarization import AISummarizationError

                openai_config = load_ai_config(Path(os.environ["OPENAI_CONFIG_PATH"]))
                claude_config = load_ai_config(Path(os.environ["CLAUDE_CONFIG_PATH"]))
                assert openai_config.backend is AIBackend.OPENAI_COMPATIBLE
                assert claude_config.backend is AIBackend.CLAUDE_CODE
                assert installed in Path(__import__("release_notes_generator").__file__).parents

                os.environ["PATH"] = ""
                client = ClaudeCodeClient(claude_config)
                try:
                    client.summarize("Module", "qualifying source")
                except AISummarizationError as error:
                    assert "was not found" in str(error)
                else:
                    raise AssertionError("active Claude drafting unexpectedly found an executable")
                """
            )
            environment = dict(os.environ)
            environment.update(
                {
                    "PYTHONPATH": str(installed_directory),
                    "INSTALLED_PACKAGE_ROOT": str(installed_directory),
                    "OPENAI_CONFIG_PATH": str(openai_path),
                    "CLAUDE_CONFIG_PATH": str(claude_path),
                }
            )
            smoke_result = subprocess.run(
                [sys.executable, "-c", smoke_script],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(smoke_result.returncode, 0, smoke_result.stderr)

            metadata_path = next(
                installed_directory.glob("change_log_summary-*.dist-info/METADATA")
            )
            requirements = [
                line.lower()
                for line in metadata_path.read_text(encoding="utf-8").splitlines()
                if line.startswith("Requires-Dist:")
            ]
            self.assertFalse(
                any("anthropic" in line or "claude" in line for line in requirements)
            )


if __name__ == "__main__":
    unittest.main()

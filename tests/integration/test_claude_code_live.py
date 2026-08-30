"""Explicitly opted-in live Claude Code coverage against the Linux fixture."""

from __future__ import annotations

import os
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from release_notes_generator.infrastructure.artifacts import LocalArtifactStore
from release_notes_generator.infrastructure.claude_code import (
    ClaudeCodeClient,
    parse_claude_version_output,
)
from release_notes_generator.infrastructure.git import GitAdapter
from release_notes_generator.infrastructure.json_reader import FileJSONReader
from release_notes_generator.infrastructure.openai import SummaryClientFactoryAdapter
from release_notes_generator.services.commit_selection import CommitSelectionService
from release_notes_generator.services.configuration import ConfigurationService
from release_notes_generator.services.diff_generation import DiffGenerationService
from release_notes_generator.services.errors import AISummarizationError
from release_notes_generator.services.summarization import SummarizationService
from tests.integration.git_fixture_state import snapshot_linux_fixture


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
LIVE_OPT_IN_ENV_VAR = "RUN_LIVE_CLAUDE_CODE_IT"
LOGIN_ATTESTATION_ENV_VAR = "CLAUDE_CODE_OPERATOR_LOGGED_IN"
WORKFLOW_LINUX_IT_CONFIG_PATH = CONFIG_DIR / "workflowLinuxIT.json"
CLAUDE_AI_IT_CONFIG_PATH = CONFIG_DIR / "aiClaudeCodeIT.json"


def _enabled(value: str) -> bool:
    return value.lower() in {"1", "true", "yes"}


class LiveClaudeCodeLinuxIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not _enabled(os.environ.get(LIVE_OPT_IN_ENV_VAR, "")):
            raise unittest.SkipTest(
                f"Set {LIVE_OPT_IN_ENV_VAR}=1 to run live Claude Code integration."
            )
        if not _enabled(os.environ.get(LOGIN_ATTESTATION_ENV_VAR, "")):
            raise unittest.SkipTest(
                f"Set {LOGIN_ATTESTATION_ENV_VAR}=1 after verifying the operator login."
            )
        if shutil.which("claude") is None:
            raise unittest.SkipTest("Claude Code executable 'claude' was not found.")

        with tempfile.TemporaryDirectory() as temp_dir:
            version_result = subprocess.run(
                ["claude", "--version"],
                input="",
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        if version_result.returncode != 0:
            raise unittest.SkipTest("Claude Code version probe did not succeed.")
        try:
            cls.claude_version = parse_claude_version_output(version_result.stdout)
        except AISummarizationError as exc:
            raise unittest.SkipTest(str(exc)) from None

        cls.runtime_config = ConfigurationService(FileJSONReader()).load(
            WORKFLOW_LINUX_IT_CONFIG_PATH
        )
        cls.linux_repository = cls.runtime_config.repository_path
        if not cls.linux_repository.exists():
            raise unittest.SkipTest(
                f"Linux integration fixture not found at {cls.linux_repository}. "
                "Clone git@github.com:torvalds/linux.git once outside the test run."
            )
        repository_probe = subprocess.run(
            ["git", "-C", str(cls.linux_repository), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        if repository_probe.returncode != 0:
            raise unittest.SkipTest(
                f"Linux integration fixture is not a Git repository: "
                f"{cls.linux_repository}"
            )

    def test_live_claude_summarizes_isolated_linux_module_diffs_without_assets(
        self,
    ) -> None:
        before = snapshot_linux_fixture(self.linux_repository)
        ai_config = _load_ai_settings(CLAUDE_AI_IT_CONFIG_PATH)
        module_config = self.runtime_config.modules
        selected_commits = _one_accepted_commit_per_module(self.runtime_config)

        with tempfile.TemporaryDirectory() as temp_dir:
            diff_directory = Path(temp_dir) / "diffs"
            diff_directory.mkdir()
            store = LocalArtifactStore()
            artifacts = DiffGenerationService(GitAdapter(), store).generate(
                self.linux_repository,
                CommitSelectionService().group(selected_commits),
                diff_directory,
            )
            try:
                outcome = SummarizationService(
                    store, SummaryClientFactoryAdapter(), ClaudeCodeClient(ai_config)
                ).summarize(artifacts, ai_config, None)
            finally:
                store.delete(artifacts)

            self.assertEqual(tuple(diff_directory.glob("diff_*.md")), ())
            self.assertEqual(
                tuple(module for module, _ in outcome.module_summaries),
                tuple(module_config.module_tags),
            )
            self.assertTrue(all(summary for _, summary in outcome.module_summaries))
            self.assertEqual(outcome.provenance.backend, "claude_code")
            self.assertEqual(outcome.provenance.model, ai_config.model)
            self.assertEqual(
                outcome.provenance.claude_code_version,
                self.claude_version,
            )

        self.assertEqual(snapshot_linux_fixture(self.linux_repository), before)


def _one_accepted_commit_per_module(runtime_config):
    if runtime_config.release_marker is None:
        raise AssertionError("Linux live integration requires marker mode.")
    module_config = runtime_config.modules
    git = GitAdapter()
    release_range = git.resolve_release_range(
        runtime_config.repository_path,
        runtime_config.head_ref,
        base_ref=runtime_config.base_ref,
        release_marker=runtime_config.release_marker,
    )
    accepted_commits = CommitSelectionService().select(
        git.commits_in_range(runtime_config.repository_path, release_range),
        runtime_config.contributors,
        module_config,
    )
    selected = {}
    for commit in accepted_commits:
        selected.setdefault(commit.module_name, commit)

    missing_modules = set(module_config.module_tags) - set(selected)
    if missing_modules:
        raise AssertionError(
            f"No accepted Linux commits found for modules: {sorted(missing_modules)}"
        )
    return tuple(selected[module_name] for module_name in module_config.module_tags)


def _load_ai_settings(ai_path: Path):
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
        return ConfigurationService(FileJSONReader()).load(runtime_path).ai


if __name__ == "__main__":
    unittest.main()

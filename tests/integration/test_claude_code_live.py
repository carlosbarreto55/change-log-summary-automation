"""Explicitly opted-in live Claude Code coverage against the Linux fixture."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from release_notes_generator.claude_code import (
    ClaudeCodeClient,
    parse_claude_version_output,
)
from release_notes_generator.commits import (
    GitCommitExtractor,
    filter_commits,
    group_commit_hashes_by_module,
)
from release_notes_generator.configuration import (
    load_ai_config,
    load_module_config,
    load_release_marker_config,
    load_runtime_config,
    load_user_config,
)
from release_notes_generator.diffs import delete_diff_files, generate_diff_files
from release_notes_generator.paths import CONFIG_DIR
from release_notes_generator.summarization import (
    AISummarizationError,
    summarize_diff_files_with_provenance,
)
from tests.integration.git_fixture_state import snapshot_linux_fixture


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

        cls.runtime_config = load_runtime_config(WORKFLOW_LINUX_IT_CONFIG_PATH)
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
        ai_config = load_ai_config(CLAUDE_AI_IT_CONFIG_PATH)
        module_config = load_module_config(self.runtime_config.module_config_path)
        selected_commits = _one_accepted_commit_per_module(self.runtime_config)

        with tempfile.TemporaryDirectory() as temp_dir:
            diff_directory = Path(temp_dir) / "diffs"
            diff_files = generate_diff_files(
                self.linux_repository,
                group_commit_hashes_by_module(selected_commits),
                diff_directory,
            )
            try:
                outcome = summarize_diff_files_with_provenance(
                    diff_files,
                    ClaudeCodeClient(ai_config),
                    ai_config.max_diff_characters_per_request,
                )
            finally:
                delete_diff_files(diff_files.values())

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
    if runtime_config.release_marker_config_path is None:
        raise AssertionError("Linux live integration requires marker mode.")
    marker = load_release_marker_config(runtime_config.release_marker_config_path).marker
    user_config = load_user_config(runtime_config.user_config_path)
    module_config = load_module_config(runtime_config.module_config_path)
    extractor = GitCommitExtractor(runtime_config.repository_path)
    release_range = extractor.resolve_release_range(
        runtime_config.head_ref,
        release_marker=marker,
    )
    accepted_commits = filter_commits(
        extractor.commits_in_range(release_range),
        user_config.approved_author_emails,
        module_config.module_tags,
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


if __name__ == "__main__":
    unittest.main()

"""Temporary JSON-driven Git fixtures for workflow context tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional, Sequence


def create_repository(root: Path) -> tuple[Path, str, str]:
    repository = root / "repository"
    repository.mkdir()
    run_git(repository, ["init", "--quiet", "--initial-branch=main"])
    run_git(repository, ["config", "user.name", "Release Test"])
    run_git(repository, ["config", "user.email", "dev@example.com"])

    source = repository / "source.txt"
    source.write_text("released\n", encoding="utf-8")
    run_git(repository, ["add", "source.txt"])
    run_git(repository, ["commit", "--quiet", "-m", "[Release] 1.0"])
    base_sha = run_git(repository, ["rev-parse", "HEAD"]).strip()

    source.write_text("released\ncommitted feature\n", encoding="utf-8")
    run_git(repository, ["add", "source.txt"])
    run_git(repository, ["commit", "--quiet", "-m", "Pix: committed feature"])
    head_sha = run_git(repository, ["rev-parse", "HEAD"]).strip()
    return repository, base_sha, head_sha


def configure_resolvable_upstream(repository: Path) -> None:
    run_git(repository, ["remote", "add", "origin", str(repository)])
    run_git(
        repository,
        ["fetch", "--no-tags", "origin", "main:refs/remotes/origin/main"],
    )
    run_git(repository, ["branch", "--set-upstream-to=origin/main", "main"])


def write_runtime_configuration(
    root: Path,
    repository: Path,
    *,
    head_ref: str = "refs/heads/main",
    base_ref: Optional[str] = None,
    marker_mode: bool = True,
    update_mode: Optional[str] = None,
    refresh_remote: Optional[str] = None,
    refresh_refspecs: Sequence[str] = (),
    temp_diff_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Path:
    config_dir = root / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "user.json").write_text(
        json.dumps({"approved_author_emails": ["dev@example.com"]}),
        encoding="utf-8",
    )
    (config_dir / "module.json").write_text(
        json.dumps(
            {
                "modules": [
                    {"name": "Pix", "tags": ["Pix:"], "section": "Payments"}
                ]
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "releaseMarker.json").write_text(
        json.dumps({"marker": "[Release]"}),
        encoding="utf-8",
    )
    (config_dir / "ai.json").write_text(
        json.dumps(
            {
                "api_url": "https://api.example.test/v1/chat/completions",
                "model": "summary-model",
                "api_key_env_var": "CHANGE_LOG_SUMMARY_AI_API_KEY",
                "prompt": "Summarize release-note diffs.",
                "max_diff_characters_per_request": 12000,
            }
        ),
        encoding="utf-8",
    )

    runtime_data = {
        "repository_path": str(repository),
        "user_config_path": "user.json",
        "module_config_path": "module.json",
        "ai_config_path": "ai.json",
        "temp_diff_dir": str(temp_diff_dir or (root / "analysis" / "diffs")),
        "output_path": str(output_path or (root / "analysis" / "release.pdf")),
        "head_ref": head_ref,
    }
    if marker_mode:
        runtime_data["release_marker_config_path"] = "releaseMarker.json"
    else:
        runtime_data["base_ref"] = base_ref
    if update_mode is not None:
        runtime_data["repository_update_mode"] = update_mode
    if refresh_remote is not None:
        runtime_data["refresh_remote"] = refresh_remote
    if refresh_refspecs:
        runtime_data["refresh_refspecs"] = list(refresh_refspecs)

    runtime_path = config_dir / "workflow.json"
    runtime_path.write_text(json.dumps(runtime_data, indent=2), encoding="utf-8")
    return runtime_path


def run_git(repository: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip() or result.stdout.strip())
    return result.stdout

"""Git commit extraction and filtering for release notes generation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional


_FIELD_SEPARATOR = "\x1f"


class GitHistoryError(RuntimeError):
    """Raised when Git history cannot be read for release note generation."""


@dataclass(frozen=True)
class GitCommit:
    """A commit extracted from Git history."""

    commit_hash: str
    author_email: str
    subject: str


@dataclass(frozen=True)
class ClassifiedCommit:
    """A commit accepted by author and module filtering."""

    commit_hash: str
    author_email: str
    subject: str
    module_name: str


class GitCommitExtractor:
    """Extracts release-range commits from a local Git repository."""

    def __init__(self, repository_path: Path) -> None:
        self._repository_path = Path(repository_path)

    def latest_release_marker_hash(self, release_marker: str) -> Optional[str]:
        """Return the newest commit hash whose subject contains the release marker."""
        output = self._run_git(["log", "--format=%H%x1f%s"])
        for line in output.splitlines():
            commit_hash, subject = _split_git_fields(line, 2)
            if release_marker in subject:
                return commit_hash
        return None

    def commits_after_latest_release_marker(self, release_marker: str) -> tuple[GitCommit, ...]:
        """Return commits after the latest release marker, oldest first."""
        release_marker_hash = self.latest_release_marker_hash(release_marker)
        if release_marker_hash is None:
            raise GitHistoryError(f"No release marker found in Git history: {release_marker}")

        output = self._run_git(
            [
                "log",
                "--reverse",
                "--format=%H%x1f%ae%x1f%s",
                f"{release_marker_hash}..HEAD",
            ]
        )
        return tuple(_parse_commit_line(line) for line in output.splitlines() if line)

    def _run_git(self, args: list[str]) -> str:
        command = ["git", "-C", str(self._repository_path), *args]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "Git command failed."
            raise GitHistoryError(message)
        return result.stdout


def filter_commits(
    commits: Iterable[GitCommit],
    approved_author_emails: Iterable[str],
    module_tags: Mapping[str, Iterable[str]],
) -> tuple[ClassifiedCommit, ...]:
    """Keep only commits from approved authors with configured module prefixes."""
    approved_authors = set(approved_author_emails)
    accepted: list[ClassifiedCommit] = []

    for commit in commits:
        if commit.author_email not in approved_authors:
            continue

        module_name = _classify_module(commit.subject, module_tags)
        if module_name is None:
            continue

        accepted.append(
            ClassifiedCommit(
                commit_hash=commit.commit_hash,
                author_email=commit.author_email,
                subject=commit.subject,
                module_name=module_name,
            )
        )

    return tuple(accepted)


def _classify_module(
    subject: str,
    module_tags: Mapping[str, Iterable[str]],
) -> Optional[str]:
    for module_name, tags in module_tags.items():
        if any(tag and subject.startswith(tag) for tag in tags):
            return module_name
    return None


def _parse_commit_line(line: str) -> GitCommit:
    commit_hash, author_email, subject = _split_git_fields(line, 3)
    return GitCommit(commit_hash, author_email, subject)


def _split_git_fields(line: str, expected_fields: int) -> list[str]:
    fields = line.split(_FIELD_SEPARATOR, expected_fields - 1)
    if len(fields) != expected_fields:
        raise GitHistoryError(f"Unexpected Git log output: {line}")
    return fields

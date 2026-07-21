"""Git commit extraction and filtering for release notes generation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Optional


_FIELD_SEPARATOR = "\x1f"


class GitHistoryError(RuntimeError):
    """Raised when Git history cannot be read for release note generation."""


def synchronize_repository(repository_path: Path) -> None:
    """Synchronize the local target repository before release analysis."""
    try:
        _run_git_command(repository_path, ["fetch", "--prune"])
    except GitHistoryError as exc:
        raise GitHistoryError(
            "Repository synchronization failed during fetch.\n\n"
            f"Git reported:\n{exc}"
        ) from exc

    try:
        _run_git_command(repository_path, ["rebase", "@{u}"])
    except GitHistoryError as rebase_error:
        try:
            _run_git_command(repository_path, ["rebase", "--abort"])
        except GitHistoryError as abort_error:
            recovery_message = (
                "The automatic rebase abort also failed:\n"
                f"{abort_error}\n\n"
                "The repository may require manual recovery."
            )
        else:
            recovery_message = "The rebase was aborted."

        raise GitHistoryError(
            "Repository synchronization failed during rebase.\n\n"
            f"Git reported:\n{rebase_error}\n\n{recovery_message}"
        ) from rebase_error


@dataclass(frozen=True)
class GitCommit:
    """A commit extracted from Git history."""

    commit_hash: str
    author_email: str
    subject: str
    authored_at: datetime


@dataclass(frozen=True)
class ClassifiedCommit:
    """A commit accepted by author and module filtering."""

    commit_hash: str
    author_email: str
    subject: str
    module_name: str
    authored_at: datetime


class GitCommitExtractor:
    """Extracts release-range commits from a local Git repository."""

    def __init__(self, repository_path: Path) -> None:
        self._repository_path = Path(repository_path)

    def latest_release_marker_hash(self, release_marker: str) -> Optional[str]:
        """Return the newest commit hash whose subject contains the release marker."""
        output = self._run_git(
            [
                "log",
                "--fixed-strings",
                f"--grep={release_marker}",
                "--format=%H%x1f%s",
            ]
        )
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
                "--format=%H%x1f%ae%x1f%aI%x1f%s",
                f"{release_marker_hash}..HEAD",
            ]
        )
        return tuple(_parse_commit_line(line) for line in output.splitlines() if line)

    def _run_git(self, args: list[str]) -> str:
        return _run_git_command(self._repository_path, args)


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
                authored_at=commit.authored_at,
            )
        )

    return tuple(accepted)


def group_commit_hashes_by_module(
    commits: Iterable[ClassifiedCommit],
) -> dict[str, tuple[str, ...]]:
    """Group accepted commit hashes by their classified module."""
    grouped_hashes: dict[str, list[str]] = {}
    for commit in commits:
        grouped_hashes.setdefault(commit.module_name, []).append(commit.commit_hash)

    return {
        module_name: tuple(commit_hashes)
        for module_name, commit_hashes in grouped_hashes.items()
        if commit_hashes
    }


def _classify_module(
    subject: str,
    module_tags: Mapping[str, Iterable[str]],
) -> Optional[str]:
    for module_name, tags in module_tags.items():
        if any(tag and subject.startswith(tag) for tag in tags):
            return module_name
    return None


def _parse_commit_line(line: str) -> GitCommit:
    commit_hash, author_email, author_timestamp, subject = _split_git_fields(line, 4)
    normalized_timestamp = (
        f"{author_timestamp[:-1]}+00:00"
        if author_timestamp.endswith("Z")
        else author_timestamp
    )
    try:
        authored_at = datetime.fromisoformat(normalized_timestamp)
    except ValueError as exc:
        raise GitHistoryError(
            f"Unexpected Git author timestamp: {author_timestamp}"
        ) from exc
    if authored_at.tzinfo is None or authored_at.utcoffset() is None:
        raise GitHistoryError(f"Unexpected Git author timestamp: {author_timestamp}")
    return GitCommit(commit_hash, author_email, subject, authored_at)


def _split_git_fields(line: str, expected_fields: int) -> list[str]:
    fields = line.split(_FIELD_SEPARATOR, expected_fields - 1)
    if len(fields) != expected_fields:
        raise GitHistoryError(f"Unexpected Git log output: {line}")
    return fields


def _run_git_command(repository_path: Path, args: list[str]) -> str:
    command = ["git", "-C", str(Path(repository_path)), *args]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Git command failed."
        raise GitHistoryError(message)
    return result.stdout

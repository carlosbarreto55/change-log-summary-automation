"""Git commit extraction and filtering for release notes generation."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal, Mapping, Optional, Sequence


_FIELD_SEPARATOR = "\x1f"
_UNKNOWN_FRESHNESS_WARNING = (
    "Remote freshness is unknown because no explicit remote-ref refresh was performed."
)
_FRESHNESS_WARNING_PREFIX = "Remote freshness"

RepositoryRelation = Literal["equal", "ahead", "behind", "diverged", "unknown"]
RepositoryUpdateMode = Literal[
    "read_only", "refresh_remote_refs", "legacy_in_place_sync"
]


class GitHistoryError(RuntimeError):
    """Raised when Git history cannot be read for release note generation."""


@dataclass(frozen=True)
class RepositoryStatus:
    """Immutable checkout diagnostics and scoped remote-freshness information."""

    staged_count: int
    unstaged_count: int
    untracked_count: int
    branch: Optional[str]
    upstream: Optional[str]
    upstream_resolved: bool
    relation: RepositoryRelation
    ahead_count: Optional[int]
    behind_count: Optional[int]
    checkout_head_sha: Optional[str]
    refreshed_refs: tuple[str, ...] = ()
    freshness_checked_at: Optional[datetime] = None
    warnings: tuple[str, ...] = ()

    @property
    def is_dirty(self) -> bool:
        """Return whether the index or worktree has any reported change."""
        return bool(self.staged_count or self.unstaged_count or self.untracked_count)

    def freshness_for(self, ref: str) -> Literal["fresh_as_of_fetch", "unknown"]:
        """Return freshness only for a destination named by a successful fetch."""
        if ref in self.refreshed_refs:
            return "fresh_as_of_fetch"
        return "unknown"


@dataclass(frozen=True)
class ReleaseRange:
    """Exact immutable commit boundaries for one analysis run."""

    base_sha: str
    head_sha: str


def inspect_repository(
    repository_path: Path, analysis_head_ref: Optional[str] = None
) -> RepositoryStatus:
    """Inspect checkout state without taking optional Git locks."""
    status_output = _run_read_only_git_command(
        repository_path,
        ["status", "--porcelain=v2", "--branch", "--untracked-files=normal"],
    )
    staged_count, unstaged_count, untracked_count, headers = _parse_status_output(
        status_output
    )
    warnings: list[str] = []

    branch_result = _run_read_only_git_process(
        repository_path, ["symbolic-ref", "--quiet", "--short", "HEAD"]
    )
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    branch = branch or None
    checkout_head_sha = headers.get("branch.oid")
    if checkout_head_sha == "(initial)":
        checkout_head_sha = None

    upstream: Optional[str] = None
    upstream_resolved = False
    relation: RepositoryRelation = "unknown"
    ahead_count: Optional[int] = None
    behind_count: Optional[int] = None

    if branch is None:
        if analysis_head_ref:
            warnings.append(
                f"Checkout HEAD is detached; analysis head '{analysis_head_ref}' is resolved independently."
            )
        else:
            warnings.append("Checkout HEAD is detached.")
    else:
        if analysis_head_ref and not _ref_names_checkout(analysis_head_ref, branch):
            warnings.append(
                f"Checkout branch '{branch}' differs from analysis head '{analysis_head_ref}'."
            )

        configured_upstream = headers.get("branch.upstream")
        upstream_result = _run_read_only_git_process(
            repository_path,
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        )
        if upstream_result.returncode == 0 and upstream_result.stdout.strip():
            upstream = upstream_result.stdout.strip()
            upstream_resolved = True
        else:
            upstream = configured_upstream
            if configured_upstream:
                warnings.append(
                    f"Configured upstream '{configured_upstream}' cannot be resolved; "
                    "checkout relationship is unknown."
                )
            else:
                warnings.append(
                    f"Checkout branch '{branch}' has no configured upstream; "
                    "checkout relationship is unknown."
                )

        if upstream_resolved:
            comparison_result = _run_read_only_git_process(
                repository_path,
                ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
            )
            comparison = _parse_upstream_counts(comparison_result)
            if comparison is None:
                warnings.append(
                    f"Checkout branch '{branch}' could not be compared with upstream "
                    f"'{upstream}'; checkout relationship is unknown."
                )
            else:
                ahead_count, behind_count = comparison
                relation = _classify_relation(ahead_count, behind_count)
                if relation != "equal":
                    warnings.append(
                        f"Checkout branch '{branch}' is {relation} relative to upstream "
                        f"'{upstream}' ({ahead_count} ahead, {behind_count} behind)."
                    )

    if staged_count or unstaged_count or untracked_count:
        warnings.append(
            "Checkout is dirty "
            f"({staged_count} staged, {unstaged_count} unstaged, "
            f"{untracked_count} untracked); SHA-based analysis does not consume these changes."
        )
    warnings.append(_UNKNOWN_FRESHNESS_WARNING)

    return RepositoryStatus(
        staged_count=staged_count,
        unstaged_count=unstaged_count,
        untracked_count=untracked_count,
        branch=branch,
        upstream=upstream,
        upstream_resolved=upstream_resolved,
        relation=relation,
        ahead_count=ahead_count,
        behind_count=behind_count,
        checkout_head_sha=checkout_head_sha,
        warnings=tuple(warnings),
    )


def update_repository(
    repository_path: Path,
    mode: RepositoryUpdateMode = "read_only",
    *,
    status: Optional[RepositoryStatus] = None,
    remote: Optional[str] = None,
    refspecs: Sequence[str] = (),
) -> RepositoryStatus:
    """Apply the selected repository update mode after read-only preflight."""
    inspected_status = status or inspect_repository(repository_path)
    if mode == "read_only":
        return _with_unknown_freshness(inspected_status)
    if mode == "refresh_remote_refs":
        destinations = _validate_refresh_scope(remote, refspecs)
        try:
            _run_git_command(
                repository_path,
                [
                    "fetch",
                    "--no-tags",
                    "--no-write-fetch-head",
                    remote,
                    *refspecs,
                ],
            )
        except GitHistoryError as exc:
            raise GitHistoryError(
                "Repository refresh failed.\n\n" f"Git reported:\n{exc}"
            ) from exc

        warnings = _without_freshness_warnings(inspected_status.warnings)
        warnings += (
            "Remote freshness is known only for refs refreshed by this fetch: "
            + ", ".join(destinations)
            + ".",
        )
        return replace(
            inspected_status,
            refreshed_refs=destinations,
            freshness_checked_at=datetime.now(timezone.utc),
            warnings=warnings,
        )
    if mode == "legacy_in_place_sync":
        _guard_legacy_sync(inspected_status)
        _synchronize_after_guards(repository_path)
        return _with_unknown_freshness(inspected_status)
    raise ValueError(f"Unknown repository update mode: {mode}")


def synchronize_repository(
    repository_path: Path, status: Optional[RepositoryStatus] = None
) -> None:
    """Run guarded legacy in-place synchronization."""
    update_repository(repository_path, "legacy_in_place_sync", status=status)


def _synchronize_after_guards(repository_path: Path) -> None:
    try:
        _run_git_command(repository_path, ["fetch", "--prune"])
    except GitHistoryError as exc:
        raise GitHistoryError(
            "Repository synchronization failed during fetch.\n\n"
            f"Git reported:\n{exc}"
        ) from exc

    try:
        _run_git_command(repository_path, ["rebase", "@{upstream}"])
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
    """Resolves and extracts one frozen release range from a Git repository."""

    def __init__(self, repository_path: Path) -> None:
        self._repository_path = Path(repository_path)

    def resolve_release_range(
        self,
        head_ref: str,
        *,
        base_ref: Optional[str] = None,
        release_marker: Optional[str] = None,
    ) -> ReleaseRange:
        """Resolve explicit selectors once and freeze their full commit object IDs."""
        if not head_ref:
            raise GitHistoryError("An explicit non-empty head ref is required.")
        if bool(base_ref) == bool(release_marker):
            raise GitHistoryError(
                "Exactly one non-empty base ref or release marker is required."
            )

        head_sha = self._resolve_commit(head_ref, "head")
        if base_ref:
            base_sha = self._resolve_commit(base_ref, "base")
        else:
            assert release_marker is not None
            marker_hash = self.latest_release_marker_hash(release_marker, head_sha)
            if marker_hash is None:
                raise GitHistoryError(
                    f"No release marker found in history reachable from {head_sha}: "
                    f"{release_marker}"
                )
            base_sha = marker_hash
        return ReleaseRange(base_sha=base_sha, head_sha=head_sha)

    def latest_release_marker_hash(
        self, release_marker: str, head_sha: str
    ) -> Optional[str]:
        """Return the newest subject match reachable from the frozen head SHA."""
        output = self._run_git(
            [
                "log",
                head_sha,
                "--fixed-strings",
                f"--grep={release_marker}",
                "--format=%H%x1f%s",
                "--",
            ]
        )
        for line in output.splitlines():
            commit_hash, subject = _split_git_fields(line, 2)
            if release_marker in subject:
                return commit_hash
        return None

    def commits_in_range(self, release_range: ReleaseRange) -> tuple[GitCommit, ...]:
        """Return commits in the frozen base-exclusive range, oldest first."""
        output = self._run_git(
            [
                "log",
                "--reverse",
                "--format=%H%x1f%ae%x1f%aI%x1f%s",
                f"{release_range.base_sha}..{release_range.head_sha}",
                "--",
            ]
        )
        return tuple(_parse_commit_line(line) for line in output.splitlines() if line)

    def commits_after_latest_release_marker(
        self, release_marker: str, head_ref: Optional[str] = None
    ) -> tuple[GitCommit, ...]:
        """Resolve an explicit head and extract commits after its newest marker."""
        if not head_ref:
            raise GitHistoryError(
                "An explicit head ref is required; ambient HEAD is not an analysis boundary."
            )
        release_range = self.resolve_release_range(
            head_ref, release_marker=release_marker
        )
        return self.commits_in_range(release_range)

    def _resolve_commit(self, ref: str, boundary_name: str) -> str:
        try:
            commit_sha = self._run_git(
                ["rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"]
            ).strip()
        except GitHistoryError as exc:
            raise GitHistoryError(
                f"Unable to resolve {boundary_name} ref '{ref}' to a commit.\n\n"
                f"Git reported:\n{exc}"
            ) from exc
        if not commit_sha:
            raise GitHistoryError(
                f"Unable to resolve {boundary_name} ref '{ref}' to a commit: "
                "Git returned an empty object ID."
            )
        return commit_sha

    def _run_git(self, args: list[str]) -> str:
        return _run_read_only_git_command(self._repository_path, args)


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


def _parse_status_output(
    output: str,
) -> tuple[int, int, int, dict[str, str]]:
    staged_count = 0
    unstaged_count = 0
    untracked_count = 0
    headers: dict[str, str] = {}

    for line in output.splitlines():
        if line.startswith("# "):
            key, separator, value = line[2:].partition(" ")
            if separator:
                headers[key] = value
            continue
        if line.startswith("? "):
            untracked_count += 1
            continue
        if not line or line[0] not in {"1", "2", "u"}:
            continue

        fields = line.split(" ", 2)
        if len(fields) < 2 or len(fields[1]) != 2:
            raise GitHistoryError(f"Unexpected Git status output: {line}")
        index_state, worktree_state = fields[1]
        if index_state != ".":
            staged_count += 1
        if worktree_state != ".":
            unstaged_count += 1

    return staged_count, unstaged_count, untracked_count, headers


def _parse_upstream_counts(
    result: subprocess.CompletedProcess[str],
) -> Optional[tuple[int, int]]:
    if result.returncode != 0:
        return None
    fields = result.stdout.split()
    if len(fields) != 2:
        return None
    try:
        ahead_count, behind_count = (int(field) for field in fields)
    except ValueError:
        return None
    if ahead_count < 0 or behind_count < 0:
        return None
    return ahead_count, behind_count


def _classify_relation(ahead_count: int, behind_count: int) -> RepositoryRelation:
    if ahead_count and behind_count:
        return "diverged"
    if ahead_count:
        return "ahead"
    if behind_count:
        return "behind"
    return "equal"


def _ref_names_checkout(analysis_head_ref: str, branch: str) -> bool:
    return analysis_head_ref in {"HEAD", branch, f"refs/heads/{branch}"}


def _without_freshness_warnings(warnings: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        warning
        for warning in warnings
        if not warning.startswith(_FRESHNESS_WARNING_PREFIX)
    )


def _with_unknown_freshness(status: RepositoryStatus) -> RepositoryStatus:
    warnings = _without_freshness_warnings(status.warnings)
    warnings += (_UNKNOWN_FRESHNESS_WARNING,)
    return replace(
        status,
        refreshed_refs=(),
        freshness_checked_at=None,
        warnings=warnings,
    )


def _validate_refresh_scope(
    remote: Optional[str], refspecs: Sequence[str]
) -> tuple[str, ...]:
    if not remote:
        raise GitHistoryError("Remote-ref refresh requires a non-empty remote name.")
    if not refspecs:
        raise GitHistoryError("Remote-ref refresh requires at least one refspec.")

    namespace = f"refs/remotes/{remote}/"
    destinations: list[str] = []
    for refspec in refspecs:
        normalized_refspec = refspec[1:] if refspec.startswith("+") else refspec
        source, separator, destination = normalized_refspec.partition(":")
        if not separator or not source or not destination.startswith(namespace):
            raise GitHistoryError(
                f"Refresh refspec destination must be in remote-tracking namespace "
                f"'{namespace}': {refspec}"
            )
        if destination == namespace:
            raise GitHistoryError(
                f"Refresh refspec destination must name a ref below '{namespace}': "
                f"{refspec}"
            )
        destinations.append(destination)
    return tuple(destinations)


def _guard_legacy_sync(status: RepositoryStatus) -> None:
    failed_guards: list[str] = []
    if status.is_dirty:
        failed_guards.append("the checkout is dirty")
    if status.branch is None:
        failed_guards.append("HEAD is detached")
    if not status.upstream or not status.upstream_resolved:
        failed_guards.append("the checked-out branch has no resolvable upstream")
    if failed_guards:
        raise GitHistoryError(
            "Legacy in-place synchronization guard failed: "
            + "; ".join(failed_guards)
            + "."
        )


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


def _run_read_only_git_command(repository_path: Path, args: list[str]) -> str:
    result = _run_read_only_git_process(repository_path, args)
    if result.returncode != 0:
        raise GitHistoryError(_git_error_message(result))
    return result.stdout


def _run_read_only_git_process(
    repository_path: Path, args: list[str]
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(Path(repository_path)), *args]
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        env=environment,
    )


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
        raise GitHistoryError(_git_error_message(result))
    return result.stdout


def _git_error_message(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip() or "Git command failed."

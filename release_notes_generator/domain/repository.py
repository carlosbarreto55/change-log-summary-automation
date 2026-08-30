"""Immutable repository and commit facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Optional


class RepositoryRelation(str, Enum):
    """Relationship between the checkout and its configured upstream."""

    EQUAL = "equal"
    AHEAD = "ahead"
    BEHIND = "behind"
    DIVERGED = "diverged"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RepositoryStatus:
    """Checkout diagnostics and scoped remote-freshness information."""

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
        return bool(self.staged_count or self.unstaged_count or self.untracked_count)

    def freshness_for(self, ref: str) -> Literal["fresh_as_of_fetch", "unknown"]:
        if ref in self.refreshed_refs:
            return "fresh_as_of_fetch"
        return "unknown"


@dataclass(frozen=True)
class ReleaseRange:
    """Exact immutable commit boundaries for one analysis run."""

    base_sha: str
    head_sha: str


@dataclass(frozen=True)
class Commit:
    """A commit extracted from Git history."""

    commit_hash: str
    author_email: str
    subject: str
    authored_at: datetime


@dataclass(frozen=True)
class ClassifiedCommit:
    """A commit accepted by contributor and module policies."""

    commit_hash: str
    author_email: str
    subject: str
    module_name: str
    authored_at: datetime

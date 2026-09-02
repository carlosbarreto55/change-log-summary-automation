"""Database change detection service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from release_notes_generator.domain.configuration import DatabasePathPolicy
from release_notes_generator.domain.repository import ClassifiedCommit
from release_notes_generator.services.contracts import GitGateway


@dataclass(frozen=True)
class DatabaseChangeMatch:
    """A commit that matched one or more configured database paths."""

    commit: ClassifiedCommit
    matched_paths: tuple[str, ...]


class DatabaseChangeDetectionService:
    """Detect commits that touched configured database paths."""

    def __init__(self, git_gateway: GitGateway) -> None:
        self._git_gateway = git_gateway

    def detect(
        self,
        repository_path: Path,
        commits: tuple[ClassifiedCommit, ...],
        policy: Optional[DatabasePathPolicy],
    ) -> tuple[DatabaseChangeMatch, ...]:
        """Detect database changes in the given commits.

        Args:
            repository_path: Path to the repository.
            commits: Classified commits to scan (oldest first).
            policy: Optional database path policy. If None or empty, returns empty result.

        Returns:
            Tuple of DatabaseChangeMatch in configured commit order.
        """
        if policy is None or not policy.paths:
            return ()

        matches: list[DatabaseChangeMatch] = []
        for commit in commits:
            changed = self._git_gateway.changed_files(repository_path, commit.commit_hash)
            changed_paths = frozenset(changed)
            matched = [path for path in policy.paths if path in changed_paths]
            if matched:
                matches.append(DatabaseChangeMatch(commit, tuple(matched)))

        return tuple(matches)

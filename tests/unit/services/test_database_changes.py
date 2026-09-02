"""Unit tests for DatabaseChangeDetectionService (tasks 4.1, 4.2, 4.3)."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Optional

from release_notes_generator.domain.configuration import DatabasePathPolicy
from release_notes_generator.domain.repository import ClassifiedCommit
from release_notes_generator.services.database_changes import (
    DatabaseChangeMatch,
    DatabaseChangeDetectionService,
)
from release_notes_generator.services.errors import GitHistoryError


class FakeGitGateway:
    """Fake GitGateway for testing that records changed_files calls."""

    def __init__(self, changed_files_map: dict[str, tuple[str, ...]]) -> None:
        self._changed_files_map = changed_files_map
        self.call_count = 0
        self.calls: list[tuple[Path, str]] = []

    def changed_files(self, repository_path: Path, commit_hash: str) -> tuple[str, ...]:
        self.call_count += 1
        self.calls.append((repository_path, commit_hash))
        if commit_hash not in self._changed_files_map:
            raise GitHistoryError(f"Unknown commit: {commit_hash}")
        return self._changed_files_map[commit_hash]


TEST_TIMESTAMP = "2026-01-03T12:30:00+00:00"


def make_commit(
    commit_hash: str,
    author_email: str = "dev@example.com",
    subject: str = "Test commit",
    module_name: str = "TestModule",
) -> ClassifiedCommit:
    """Helper to create a ClassifiedCommit for testing."""
    return ClassifiedCommit(
        commit_hash=commit_hash,
        author_email=author_email,
        subject=subject,
        module_name=module_name,
        authored_at=TEST_TIMESTAMP,
    )


class DatabaseChangeMatchTests(unittest.TestCase):
    """Tests for DatabaseChangeMatch dataclass."""

    def test_is_frozen(self) -> None:
        """Verify DatabaseChangeMatch is frozen (immutable)."""
        commit = make_commit("abc123")
        match = DatabaseChangeMatch(commit, ("path/to/db.kt",))

        with self.assertRaises(FrozenInstanceError):
            match.commit = make_commit("def456")  # type: ignore[misc]


class DatabaseChangeDetectionServiceTests(unittest.TestCase):
    """Tests for DatabaseChangeDetectionService."""

    def test_exact_match_returns_matched_paths_in_configured_order(self) -> None:
        """Test 4.1: exact match returns matched paths in configured order."""
        policy = DatabasePathPolicy(
            ("path/to/db.kt", "another/path.kt")
        )
        fake_gateway = FakeGitGateway({
            "abc123": ("path/to/db.kt", "unrelated.txt"),
        })
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (make_commit("abc123"),)

        result = service.detect(Path("/repo"), commits, policy)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].commit.commit_hash, "abc123")
        self.assertEqual(result[0].matched_paths, ("path/to/db.kt",))

    def test_directory_prefix_non_match(self) -> None:
        """Test 4.1: directory prefix does not match (exact match only)."""
        policy = DatabasePathPolicy(("path/to/db.kt",))
        fake_gateway = FakeGitGateway({
            "abc123": ("path/to/db.kt/file.txt",),  # subdirectory, not exact match
        })
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (make_commit("abc123"),)

        result = service.detect(Path("/repo"), commits, policy)

        self.assertEqual(result, ())

    def test_filename_suffix_non_match(self) -> None:
        """Test 4.1: filename suffix does not match (exact match only)."""
        policy = DatabasePathPolicy(("db.kt",))
        fake_gateway = FakeGitGateway({
            "abc123": ("path/to/db.kt.bak",),  # different file, not exact match
        })
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (make_commit("abc123"),)

        result = service.detect(Path("/repo"), commits, policy)

        self.assertEqual(result, ())

    def test_case_difference_non_match(self) -> None:
        """Test 4.1: case difference does not match (case-sensitive)."""
        policy = DatabasePathPolicy(("path/to/db.kt",))
        fake_gateway = FakeGitGateway({
            "abc123": ("path/to/DB.KT",),  # different case
        })
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (make_commit("abc123"),)

        result = service.detect(Path("/repo"), commits, policy)

        self.assertEqual(result, ())

    def test_commit_matching_several_configured_paths(self) -> None:
        """Test 4.1: commit matching several configured paths returns all."""
        policy = DatabasePathPolicy(
            ("path/to/db.kt", "another/path.kt", "third.kt")
        )
        fake_gateway = FakeGitGateway({
            "abc123": ("path/to/db.kt", "another/path.kt", "third.kt", "other.txt"),
        })
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (make_commit("abc123"),)

        result = service.detect(Path("/repo"), commits, policy)

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0].matched_paths,
            ("path/to/db.kt", "another/path.kt", "third.kt")
        )

    def test_commit_matching_none_returns_empty(self) -> None:
        """Test 4.1: commit matching none returns empty result."""
        policy = DatabasePathPolicy(("path/to/db.kt",))
        fake_gateway = FakeGitGateway({
            "abc123": ("unrelated.txt", "other.kt"),
        })
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (make_commit("abc123"),)

        result = service.detect(Path("/repo"), commits, policy)

        self.assertEqual(result, ())

    def test_none_policy_returns_empty_without_gateway_call(self) -> None:
        """Test 4.2: None policy returns empty without gateway call."""
        fake_gateway = FakeGitGateway({})
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (make_commit("abc123"),)

        result = service.detect(Path("/repo"), commits, None)

        self.assertEqual(result, ())
        self.assertEqual(fake_gateway.call_count, 0)

    def test_empty_policy_returns_empty_without_gateway_call(self) -> None:
        """Test 4.2: empty policy returns empty without gateway call."""
        policy = DatabasePathPolicy(())
        fake_gateway = FakeGitGateway({})
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (make_commit("abc123"),)

        result = service.detect(Path("/repo"), commits, policy)

        self.assertEqual(result, ())
        self.assertEqual(fake_gateway.call_count, 0)

    def test_detect_scans_only_accepted_commits(self) -> None:
        """Test 4.3: detection scans only accepted commits."""
        policy = DatabasePathPolicy(("path/to/db.kt",))
        fake_gateway = FakeGitGateway({
            "abc123": ("path/to/db.kt",),
            "def456": ("other.txt",),
            "ghi789": ("path/to/db.kt",),
        })
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (
            make_commit("abc123", subject="Commit 1"),
            make_commit("def456", subject="Commit 2"),
            make_commit("ghi789", subject="Commit 3"),
        )

        result = service.detect(Path("/repo"), commits, policy)

        # Should have matches for abc123 and ghi789
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].commit.commit_hash, "abc123")
        self.assertEqual(result[1].commit.commit_hash, "ghi789")
        # Gateway should be called exactly once per commit
        self.assertEqual(fake_gateway.call_count, 3)
        called_hashes = [call[1] for call in fake_gateway.calls]
        self.assertEqual(called_hashes, ["abc123", "def456", "ghi789"])

    def test_gateway_not_called_for_hash_outside_commits(self) -> None:
        """Test 4.3: gateway never queried for hash outside supplied commits."""
        policy = DatabasePathPolicy(("path/to/db.kt",))
        fake_gateway = FakeGitGateway({
            "abc123": ("path/to/db.kt",),
            "other123": ("path/to/db.kt",),  # This hash is NOT in commits
        })
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (make_commit("abc123"),)

        result = service.detect(Path("/repo"), commits, policy)

        self.assertEqual(len(result), 1)
        called_hashes = [call[1] for call in fake_gateway.calls]
        self.assertNotIn("other123", called_hashes)

    def test_multiple_commits_preserve_order(self) -> None:
        """Test that commits are returned in supplied (oldest-first) order."""
        policy = DatabasePathPolicy(("db.kt",))
        fake_gateway = FakeGitGateway({
            "oldest": ("db.kt",),
            "middle": ("db.kt",),
            "newest": ("db.kt",),
        })
        service = DatabaseChangeDetectionService(fake_gateway)
        commits = (
            make_commit("oldest", subject="Oldest"),
            make_commit("middle", subject="Middle"),
            make_commit("newest", subject="Newest"),
        )

        result = service.detect(Path("/repo"), commits, policy)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].commit.subject, "Oldest")
        self.assertEqual(result[1].commit.subject, "Middle")
        self.assertEqual(result[2].commit.subject, "Newest")


if __name__ == "__main__":
    unittest.main()

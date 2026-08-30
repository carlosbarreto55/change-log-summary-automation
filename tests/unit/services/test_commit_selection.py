import unittest
from datetime import datetime, timezone

from release_notes_generator.domain.repository import ClassifiedCommit
from release_notes_generator.services.commit_selection import CommitSelectionService


class CommitGroupingTests(unittest.TestCase):
    def test_groups_accepted_commit_hashes_by_module_category(self) -> None:
        commits = (
            _commit("pix1", "Pix: add payment", "Pix"),
            _commit("gl1", "GlobalLoyalty: add reward", "GlobalLoyalty"),
            _commit("pix2", "Pix: add refund", "Pix"),
            _commit("tol1", "TransitOpenLoop: add fare", "TransitOpenLoop"),
        )

        groups = CommitSelectionService().group(commits)

        self.assertEqual(
            groups,
            {
                "Pix": ("pix1", "pix2"),
                "GlobalLoyalty": ("gl1",),
                "TransitOpenLoop": ("tol1",),
            },
        )

    def test_skips_empty_groups(self) -> None:
        groups = CommitSelectionService().group(())

        self.assertEqual(groups, {})


def _commit(commit_hash: str, subject: str, module_name: str) -> ClassifiedCommit:
    return ClassifiedCommit(
        commit_hash,
        "dev@example.com",
        subject,
        module_name,
        datetime(2026, 1, 3, 12, tzinfo=timezone.utc),
    )


if __name__ == "__main__":
    unittest.main()

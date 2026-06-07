import unittest

from release_notes_generator.commits import ClassifiedCommit, group_commit_hashes_by_module


class CommitGroupingTests(unittest.TestCase):
    def test_groups_accepted_commit_hashes_by_module_category(self) -> None:
        commits = (
            ClassifiedCommit("pix1", "dev@example.com", "Pix: add payment", "Pix"),
            ClassifiedCommit("gl1", "dev@example.com", "GlobalLoyalty: add reward", "GlobalLoyalty"),
            ClassifiedCommit("pix2", "dev@example.com", "Pix: add refund", "Pix"),
            ClassifiedCommit("tol1", "dev@example.com", "TransitOpenLoop: add fare", "TransitOpenLoop"),
        )

        groups = group_commit_hashes_by_module(commits)

        self.assertEqual(
            groups,
            {
                "Pix": ("pix1", "pix2"),
                "GlobalLoyalty": ("gl1",),
                "TransitOpenLoop": ("tol1",),
            },
        )

    def test_skips_empty_groups(self) -> None:
        groups = group_commit_hashes_by_module(())

        self.assertEqual(groups, {})


if __name__ == "__main__":
    unittest.main()

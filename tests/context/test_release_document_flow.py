import unittest
from datetime import date, datetime

from release_notes_generator.domain.configuration import (
    ContributorPolicy,
    ModuleDefinition,
    ModulePolicy,
)
from release_notes_generator.domain.repository import Commit
from release_notes_generator.services.commit_selection import CommitSelectionService
from release_notes_generator.services.release_document import ReleaseDocumentService


class ReleaseDocumentFlowTests(unittest.TestCase):
    def test_filtered_dated_commits_flow_into_configured_module_context(self) -> None:
        module_config = ModulePolicy(
            modules=(
                ModuleDefinition("Payments", ("PAY:",), "Customer Features"),
                ModuleDefinition("Rewards", ("REWARD:",), "Customer Features"),
            )
        )
        commits = (
            _commit("pay-1", "approved@example.com", "PAY: add transfer", "2026-01-03"),
            _commit("pay-2", "approved@example.com", "PAY: add refund", "2026-01-18"),
            _commit("reward", "approved@example.com", "REWARD: add points", "2026-01-12"),
            _commit("outsider", "outsider@example.com", "PAY: excluded", "2026-01-20"),
            _commit("unmapped", "approved@example.com", "OTHER: excluded", "2026-01-21"),
        )

        accepted = CommitSelectionService().select(
            commits, ContributorPolicy(("approved@example.com",)), module_config
        )
        summaries = {
            "Payments": "- Added transfers and refunds.",
            "Rewards": "- Added loyalty points.",
        }
        document = ReleaseDocumentService().compose(
            summaries,
            module_config,
            repository_name="customer-platform",
            accepted_commits=accepted,
        )

        self.assertEqual(document.repository_name, "customer-platform")
        self.assertEqual(document.qualifying_change_count, 3)
        self.assertEqual(document.change_start_date, date(2026, 1, 3))
        self.assertEqual(document.change_end_date, date(2026, 1, 18))
        self.assertEqual([section.title for section in document.sections], ["Customer Features"])
        self.assertEqual(
            [module.name for module in document.sections[0].modules],
            ["Payments", "Rewards"],
        )

        payments, rewards = document.sections[0].modules
        self.assertEqual(payments.qualifying_change_count, 2)
        self.assertEqual(payments.change_start_date, date(2026, 1, 3))
        self.assertEqual(payments.change_end_date, date(2026, 1, 18))
        self.assertEqual(rewards.qualifying_change_count, 1)
        self.assertEqual(rewards.change_start_date, date(2026, 1, 12))
        self.assertEqual(rewards.change_end_date, date(2026, 1, 12))
        self.assertEqual(payments.summary, "- Added transfers and refunds.")
        self.assertNotIn("2026-", payments.summary)


def _commit(
    commit_hash: str,
    author_email: str,
    subject: str,
    authored_date: str,
) -> Commit:
    return Commit(
        commit_hash,
        author_email,
        subject,
        datetime.fromisoformat(f"{authored_date}T12:00:00+00:00"),
    )


if __name__ == "__main__":
    unittest.main()

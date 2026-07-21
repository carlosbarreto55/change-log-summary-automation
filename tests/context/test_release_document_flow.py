import unittest

from release_notes_generator.commits import GitCommit, filter_commits
from release_notes_generator.composition import compose_release_document
from release_notes_generator.configuration import ModuleConfig, ModuleDefinition


class ReleaseDocumentFlowTests(unittest.TestCase):
    def test_filtered_summaries_keep_configured_shared_section_order(self) -> None:
        module_config = ModuleConfig(
            modules=(
                ModuleDefinition("Payments", ("PAY:",), "Customer Features"),
                ModuleDefinition("Rewards", ("REWARD:",), "Customer Features"),
            )
        )
        commits = (
            GitCommit("pay", "approved@example.com", "PAY: add transfer"),
            GitCommit("reward", "approved@example.com", "REWARD: add points"),
            GitCommit("outsider", "outsider@example.com", "PAY: excluded"),
            GitCommit("unmapped", "approved@example.com", "OTHER: excluded"),
        )

        accepted = filter_commits(
            commits,
            approved_author_emails=("approved@example.com",),
            module_tags=module_config.module_tags,
        )
        summaries = {commit.module_name: f"- {commit.subject}" for commit in accepted}
        document = compose_release_document(summaries, module_config)

        self.assertEqual([section.title for section in document.sections], ["Customer Features"])
        self.assertEqual(
            [module.name for module in document.sections[0].modules],
            ["Payments", "Rewards"],
        )
        rendered_input = "\n".join(
            module.summary for section in document.sections for module in section.modules
        )
        self.assertNotIn("excluded", rendered_input)


if __name__ == "__main__":
    unittest.main()

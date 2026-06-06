import unittest

from release_notes_generator.workflow import ReleaseNotesWorkflow


class RuntimeFlowTests(unittest.TestCase):
    def test_expected_runtime_flow_is_declared_in_order(self) -> None:
        workflow = ReleaseNotesWorkflow()

        self.assertEqual(
            workflow.step_names(),
            [
                "locate release marker",
                "load approved users",
                "load supported modules",
                "capture commits after release marker",
                "filter commits by approved users",
                "classify commits by module tag",
                "discard unauthorized or unmapped commits",
                "group accepted commits by category",
                "generate category diff files",
                "send category diffs to AI API",
                "receive category summaries",
                "merge global feature summaries",
                "insert pix summary",
                "export final release notes",
                "delete temporary diff files",
            ],
        )


if __name__ == "__main__":
    unittest.main()

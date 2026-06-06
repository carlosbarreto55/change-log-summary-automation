import unittest
from unittest.mock import patch

from release_notes_generator.cli import main


class MainEntrypointTests(unittest.TestCase):
    def test_main_runs_release_notes_workflow(self) -> None:
        with patch("release_notes_generator.cli.ReleaseNotesWorkflow") as workflow_cls:
            workflow = workflow_cls.return_value
            workflow.run.return_value = 0

            result = main()

        self.assertEqual(result, 0)
        workflow_cls.assert_called_once_with()
        workflow.run.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

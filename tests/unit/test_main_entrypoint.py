from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

from release_notes_generator.cli import main
from release_notes_generator.commits import GitHistoryError
from release_notes_generator.pdf_export import PDFGenerationError


class MainEntrypointTests(unittest.TestCase):
    def test_main_runs_release_notes_workflow_with_config_path(self) -> None:
        with patch("release_notes_generator.cli.ReleaseNotesWorkflow") as workflow_cls:
            workflow = workflow_cls.return_value
            workflow.run.return_value = 0

            result = main(["--config", "workflow.json"])

        self.assertEqual(result, 0)
        workflow_cls.assert_called_once_with()
        workflow.run.assert_called_once_with(Path("workflow.json"))

    def test_main_requires_config_path(self) -> None:
        with patch("sys.stderr", new_callable=StringIO), self.assertRaises(SystemExit) as error:
            main([])

        self.assertEqual(error.exception.code, 2)

    def test_main_reports_expected_workflow_error_without_traceback(self) -> None:
        standard_error = StringIO()
        with patch("release_notes_generator.cli.ReleaseNotesWorkflow") as workflow_cls, patch(
            "sys.stderr", standard_error
        ):
            workflow_cls.return_value.run.side_effect = GitHistoryError(
                "Repository synchronization failed during rebase.\n\n"
                "Git reported:\nrebase conflict\n\nThe rebase was aborted."
            )

            result = main(["--config", "workflow.json"])

        self.assertEqual(result, 1)
        self.assertIn("Error: Repository synchronization failed during rebase.", standard_error.getvalue())
        self.assertIn("rebase conflict", standard_error.getvalue())
        self.assertNotIn("Traceback", standard_error.getvalue())

    def test_main_reports_pdf_error_with_nonzero_status(self) -> None:
        standard_error = StringIO()
        with patch("release_notes_generator.cli.ReleaseNotesWorkflow") as workflow_cls, patch(
            "sys.stderr", standard_error
        ):
            workflow_cls.return_value.run.side_effect = PDFGenerationError(
                "Unable to generate PDF: release.pdf"
            )

            result = main(["--config", "workflow.json"])

        self.assertEqual(result, 1)
        self.assertIn("Error: Unable to generate PDF", standard_error.getvalue())


if __name__ == "__main__":
    unittest.main()

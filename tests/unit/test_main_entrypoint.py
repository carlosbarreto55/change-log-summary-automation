from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

from release_notes_generator.cli import main


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


if __name__ == "__main__":
    unittest.main()

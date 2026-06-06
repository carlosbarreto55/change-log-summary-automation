import unittest

from release_notes_generator import paths


class ProjectStructureTests(unittest.TestCase):
    def test_expected_directories_exist(self) -> None:
        self.assertTrue(paths.CONFIG_DIR.is_dir())
        self.assertTrue(paths.TEMP_DIFF_DIR.is_dir())
        self.assertTrue(paths.OUTPUT_DIR.is_dir())

    def test_main_entrypoint_file_exists(self) -> None:
        entrypoint = paths.PROJECT_ROOT / "release_notes_generator" / "__main__.py"

        self.assertTrue(entrypoint.is_file())


if __name__ == "__main__":
    unittest.main()

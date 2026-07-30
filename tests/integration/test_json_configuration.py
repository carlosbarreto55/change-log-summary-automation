from __future__ import annotations

import unittest

from release_notes_generator.configuration import (
    RepositoryUpdateMode,
    load_release_marker_config,
    load_runtime_config,
)
from release_notes_generator.paths import CONFIG_DIR


class CommittedRuntimeConfigurationTests(unittest.TestCase):
    def test_every_committed_runtime_json_declares_safe_explicit_selectors(
        self,
    ) -> None:
        runtime_paths = tuple(sorted(CONFIG_DIR.glob("workflow*.json")))
        self.assertTrue(runtime_paths)

        for runtime_path in runtime_paths:
            with self.subTest(runtime_path=runtime_path):
                config = load_runtime_config(runtime_path)
                self.assertTrue(config.head_ref.strip())
                self.assertNotEqual(
                    config.base_ref is None,
                    config.release_marker_config_path is None,
                )
                self.assertNotEqual(
                    config.temp_diff_dir,
                    config.repository_path,
                )
                self.assertNotIn(
                    config.repository_path,
                    config.temp_diff_dir.parents,
                )
                if (
                    config.repository_update_mode
                    is not RepositoryUpdateMode.LEGACY_IN_PLACE_SYNC
                ):
                    self.assertNotEqual(
                        config.output_path,
                        config.repository_path,
                    )
                    self.assertNotIn(
                        config.repository_path,
                        config.output_path.parents,
                    )
                if config.release_marker_config_path is not None:
                    self.assertTrue(
                        load_release_marker_config(
                            config.release_marker_config_path
                        ).marker.strip()
                    )

    def test_linux_runtime_intentionally_uses_omitted_read_only_default(
        self,
    ) -> None:
        runtime_path = CONFIG_DIR / "workflowLinuxIT.json"
        raw = runtime_path.read_text(encoding="utf-8")
        config = load_runtime_config(runtime_path)

        self.assertNotIn('"repository_update_mode"', raw)
        self.assertIs(
            config.repository_update_mode,
            RepositoryUpdateMode.READ_ONLY,
        )


if __name__ == "__main__":
    unittest.main()

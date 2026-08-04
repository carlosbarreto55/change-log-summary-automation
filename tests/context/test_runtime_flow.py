import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.configuration import ConfigurationError
from release_notes_generator.workflow import ReleaseNotesWorkflow
from tests.context.workflow_fixture import (
    create_repository,
    write_runtime_configuration,
)


class RecordingSummaryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def summarize(self, module_name: str, diff_content: str) -> str:
        self.calls.append((module_name, diff_content))
        return f"- {module_name} summary"

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        return partial_summaries


class RuntimeFlowTests(unittest.TestCase):
    def test_expected_runtime_flow_is_declared_in_order(self) -> None:
        self.assertEqual(
            ReleaseNotesWorkflow().step_names(),
            [
                "load runtime configuration",
                "load selected lower-boundary configuration",
                "load approved users",
                "load supported modules",
                "load AI settings",
                "validate external analysis paths",
                "inspect target repository",
                "apply selected repository update mode",
                "freeze release-range boundaries",
                "capture commits from frozen range",
                "filter commits by approved users",
                "classify commits by module tag",
                "discard unauthorized or unmapped commits",
                "group accepted commits by category",
                "prepare validated external destinations",
                "generate category diff files",
                "send category diffs to AI API",
                "receive category summaries",
                "compose configured release document",
                "export final PDF release notes",
                "delete temporary diff files",
            ],
        )

    def test_explicit_base_mode_does_not_load_marker_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, base_sha, _ = create_repository(root)
            runtime_path = write_runtime_configuration(
                root,
                repository,
                marker_mode=False,
                base_ref=base_sha,
            )
            (root / "config" / "releaseMarker.json").write_text(
                "not json",
                encoding="utf-8",
            )

            result = ReleaseNotesWorkflow(
                summary_client=RecordingSummaryClient()
            ).run(runtime_path)

            self.assertEqual(result, 0)
            self.assertEqual((root / "analysis" / "release.pdf").read_bytes()[:5], b"%PDF-")

    def test_marker_mode_rejects_every_unusable_marker_before_git(self) -> None:
        cases = (
            ("missing", None),
            ("malformed", "not json"),
            ("non-object", "[]"),
            ("absent-marker", "{}"),
            ("empty-marker", '{"marker": ""}'),
        )
        for name, content in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                repository, _, _ = create_repository(root)
                runtime_path = write_runtime_configuration(root, repository)
                marker_path = root / "config" / "releaseMarker.json"
                if content is None:
                    marker_path.unlink()
                else:
                    marker_path.write_text(content, encoding="utf-8")

                with (
                    patch("release_notes_generator.workflow.validate_analysis_paths") as validate_paths,
                    patch("release_notes_generator.workflow.inspect_repository") as inspect,
                    self.assertRaises(ConfigurationError),
                ):
                    ReleaseNotesWorkflow(
                        summary_client=RecordingSummaryClient()
                    ).run(runtime_path)

                validate_paths.assert_not_called()
                inspect.assert_not_called()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            runtime_path = write_runtime_configuration(root, repository)
            marker_path = root / "config" / "releaseMarker.json"
            marker_path.unlink()
            marker_path.mkdir()

            with (
                patch("release_notes_generator.workflow.validate_analysis_paths") as validate_paths,
                self.assertRaises(ConfigurationError),
            ):
                ReleaseNotesWorkflow(
                    summary_client=RecordingSummaryClient()
                ).run(runtime_path)
            validate_paths.assert_not_called()

    def test_all_referenced_configuration_is_validated_before_git(self) -> None:
        for config_name in ("user.json", "module.json", "ai.json"):
            with self.subTest(config_name=config_name), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                repository, _, _ = create_repository(root)
                runtime_path = write_runtime_configuration(root, repository)
                (root / "config" / config_name).write_text("not json", encoding="utf-8")

                with (
                    patch("release_notes_generator.workflow.validate_analysis_paths") as validate_paths,
                    patch("release_notes_generator.workflow.inspect_repository") as inspect,
                    self.assertRaises(ConfigurationError),
                ):
                    ReleaseNotesWorkflow(
                        summary_client=RecordingSummaryClient()
                    ).run(runtime_path)

                validate_paths.assert_not_called()
                inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()

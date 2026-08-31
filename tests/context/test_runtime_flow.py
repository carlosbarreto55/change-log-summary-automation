"""Context tests for configuration-first workflow ordering."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.infrastructure.git import GitAdapter
from release_notes_generator.infrastructure.json_reader import FileJSONReader
from release_notes_generator.infrastructure.openai import SummaryClientFactoryAdapter
from release_notes_generator.infrastructure.reportlab_pdf import ReportLabPDFExporter
from release_notes_generator.presentation.composition import compose_release_notes_service
from release_notes_generator.services.commit_selection import CommitSelectionService
from release_notes_generator.services.configuration import ConfigurationService
from release_notes_generator.services.diff_generation import DiffGenerationService
from release_notes_generator.services.errors import ConfigurationError
from release_notes_generator.services.release_notes import WORKFLOW_STEPS, ReleaseNotesService
from release_notes_generator.services.summarization import SummarizationService
from tests.context.workflow_fixture import create_repository, write_runtime_configuration


class RecordingSummaryClient:
    def summarize(self, module_name: str, diff_content: str) -> str:
        return f"- {module_name} summary"

    def reduce(self, module_name: str, partial_summaries: str) -> str:
        return partial_summaries


class RecordingPathValidator:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def validate(self, configuration):
        self.calls.append(configuration)
        raise AssertionError("path validation must not run after configuration failure")


def _configuration_gated_service(paths: RecordingPathValidator) -> ReleaseNotesService:
    """Build only the dependencies reachable by configuration-failure tests."""
    return ReleaseNotesService(
        configuration=ConfigurationService(FileJSONReader()),
        paths=paths,
        repositories=None,  # type: ignore[arg-type]
        commits=None,  # type: ignore[arg-type]
        diffs=None,  # type: ignore[arg-type]
        summarization=None,  # type: ignore[arg-type]
        documents=None,  # type: ignore[arg-type]
        pdf=None,  # type: ignore[arg-type]
    )


class RuntimeFlowTests(unittest.TestCase):
    def test_commit_list_fixture_omits_ai_environment_and_diff_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)

            runtime_path = write_runtime_configuration(
                root, repository, report_mode="commit_list"
            )
            runtime = json.loads(runtime_path.read_text(encoding="utf-8"))

            self.assertEqual(runtime["report_mode"], "commit_list")
            self.assertNotIn("ai_config_path", runtime)
            self.assertNotIn("env_file_path", runtime)
            self.assertNotIn("temp_diff_dir", runtime)
            self.assertFalse((root / "config" / "ai.json").exists())

    def test_commit_list_real_git_flow_exports_exact_commit_without_temp_analysis(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, base_sha, head_sha = create_repository(root)
            output_path = root / "output" / "commit-report.pdf"
            runtime_path = write_runtime_configuration(
                root,
                repository,
                marker_mode=False,
                base_ref=base_sha,
                output_path=output_path,
                report_mode="commit_list",
            )
            documents = []
            original_export = ReportLabPDFExporter.export

            def recording_export(exporter, document, destination):
                documents.append(document)
                return original_export(exporter, document, destination)

            forbidden = AssertionError("commit_list must not perform diff or AI work")
            with (
                patch.object(CommitSelectionService, "group", side_effect=forbidden),
                patch.object(GitAdapter, "show", side_effect=forbidden),
                patch.object(DiffGenerationService, "generate", side_effect=forbidden),
                patch.object(DiffGenerationService, "cleanup", side_effect=forbidden),
                patch.object(SummaryClientFactoryAdapter, "create", side_effect=forbidden),
                patch.object(SummarizationService, "summarize", side_effect=forbidden),
                patch.object(ReportLabPDFExporter, "export", new=recording_export),
            ):
                output = compose_release_notes_service().generate(runtime_path)

            self.assertEqual(output, output_path.resolve())
            self.assertEqual(output.read_bytes()[:5], b"%PDF-")
            self.assertEqual(len(documents), 1)
            document = documents[0]
            self.assertEqual(document.title, "Release Commit Report")
            self.assertEqual(document.qualifying_change_count, 1)
            self.assertEqual(len(document.sections), 1)
            module = document.sections[0].modules[0]
            self.assertEqual(module.name, "Pix")
            self.assertEqual(
                tuple((entry.subject, entry.commit_hash) for entry in module.commits),
                (("Pix: committed feature", head_sha),),
            )
            self.assertFalse((root / "analysis").exists())

    def test_expected_runtime_flow_is_declared_in_order(self) -> None:
        self.assertEqual(
            list(WORKFLOW_STEPS),
            [
                "load and validate all configuration",
                "validate external analysis paths",
                "inspect target repository",
                "apply selected repository update mode",
                "freeze release-range boundaries",
                "capture commits from frozen range",
                "filter and classify commits",
                "prepare validated report destinations",
                "produce configured report content",
                "compose configured release document",
                "revalidate and export final PDF report",
                "clean up report-specific temporary artifacts",
            ],
        )

    def test_explicit_base_mode_does_not_load_marker_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, base_sha, _ = create_repository(root)
            runtime_path = write_runtime_configuration(
                root, repository, marker_mode=False, base_ref=base_sha
            )
            (root / "config" / "releaseMarker.json").write_text(
                "not json", encoding="utf-8"
            )

            output = compose_release_notes_service(
                summary_client=RecordingSummaryClient()
            ).generate(runtime_path)

            self.assertEqual(output.read_bytes()[:5], b"%PDF-")

    def test_marker_mode_rejects_every_unusable_marker_before_path_or_git(self) -> None:
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
                paths = RecordingPathValidator()

                with self.assertRaises(ConfigurationError):
                    _configuration_gated_service(paths).generate(runtime_path)

                self.assertEqual(paths.calls, [])

    def test_invalid_backend_configuration_fails_before_every_downstream_stage(self) -> None:
        invalid_ai = {
            "backend": "claude_code",
            "api_url": "https://api.example.test",
            "model": "m",
            "prompt": "p",
            "max_diff_characters_per_request": 100,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            runtime_path = write_runtime_configuration(root, repository)
            (root / "config" / "ai.json").write_text(
                json.dumps(invalid_ai), encoding="utf-8"
            )
            paths = RecordingPathValidator()

            with self.assertRaises(ConfigurationError):
                _configuration_gated_service(paths).generate(runtime_path)

            self.assertEqual(paths.calls, [])

    def test_all_referenced_configuration_is_validated_before_path_or_git(self) -> None:
        for config_name in ("user.json", "module.json", "ai.json"):
            with self.subTest(config_name=config_name), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                repository, _, _ = create_repository(root)
                runtime_path = write_runtime_configuration(root, repository)
                (root / "config" / config_name).write_text(
                    "not json", encoding="utf-8"
                )
                paths = RecordingPathValidator()

                with self.assertRaises(ConfigurationError):
                    _configuration_gated_service(paths).generate(runtime_path)

                self.assertEqual(paths.calls, [])


if __name__ == "__main__":
    unittest.main()

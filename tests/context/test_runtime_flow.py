import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.commits import GitCommit, GitHistoryError
from release_notes_generator.configuration import ConfigurationError
from release_notes_generator.pdf_export import export_release_pdf
from release_notes_generator.workflow import ReleaseNotesWorkflow


class RecordingSummaryClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def summarize(self, module_name: str, diff_content: str) -> str:
        self.calls.append((module_name, diff_content))
        return f"- {module_name} summary"


class RuntimeFlowTests(unittest.TestCase):
    def test_expected_runtime_flow_is_declared_in_order(self) -> None:
        workflow = ReleaseNotesWorkflow()

        self.assertEqual(
            workflow.step_names(),
            [
                "load runtime configuration",
                "load release marker",
                "load approved users",
                "load supported modules",
                "load AI settings",
                "synchronize target repository",
                "locate release marker",
                "capture commits after release marker",
                "filter commits by approved users",
                "classify commits by module tag",
                "discard unauthorized or unmapped commits",
                "group accepted commits by category",
                "generate category diff files",
                "send category diffs to AI API",
                "receive category summaries",
                "compose configured release document",
                "export final PDF release notes",
                "delete temporary diff files",
            ],
        )

    def test_run_executes_full_workflow_and_cleans_up_generated_diffs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            runtime_config_path = _write_runtime_configuration(base_dir)
            diff_file_path = base_dir / "tmp" / "diffs" / "diff_pix.md"
            events: list[str] = []
            documents = []
            client = RecordingSummaryClient()
            test_case = self

            class Extractor:
                def __init__(self, repository_path: Path) -> None:
                    events.append("create extractor")
                    self.repository_path = repository_path

                def commits_after_latest_release_marker(self, release_marker: str):
                    events.append("extract commits")
                    test_case.assertEqual(release_marker, "[Release]")
                    return (
                        GitCommit(
                            "pix1",
                            "dev@example.com",
                            "Pix: add payment",
                            datetime(2026, 1, 3, 12, tzinfo=timezone.utc),
                        ),
                        GitCommit(
                            "ignored",
                            "outsider@example.com",
                            "Pix: ignore",
                            datetime(2026, 1, 4, 12, tzinfo=timezone.utc),
                        ),
                    )

            def synchronize(repository_path: Path) -> None:
                events.append("synchronize")
                self.assertEqual(repository_path, (base_dir / "repo").resolve())

            def generate_diffs(repository_path, grouped_commit_hashes, output_dir):
                events.append("generate diffs")
                self.assertEqual(repository_path, (base_dir / "repo").resolve())
                self.assertEqual(grouped_commit_hashes, {"Pix": ("pix1",)})
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                diff_file_path.write_text("pix-only diff", encoding="utf-8")
                return {"Pix": diff_file_path}

            def recording_export(document, output_path):
                documents.append(document)
                return export_release_pdf(document, output_path)

            with patch(
                "release_notes_generator.workflow.synchronize_repository",
                side_effect=synchronize,
            ), patch(
                "release_notes_generator.workflow.GitCommitExtractor",
                side_effect=Extractor,
            ), patch(
                "release_notes_generator.workflow.generate_diff_files",
                side_effect=generate_diffs,
            ), patch(
                "release_notes_generator.workflow.export_release_pdf",
                side_effect=recording_export,
            ):
                result = ReleaseNotesWorkflow(summary_client=client).run(runtime_config_path)

            output_path = base_dir / "output" / "release_notes.pdf"
            output_header = output_path.read_bytes()[:5]
            diff_file_removed = not diff_file_path.exists()

        self.assertEqual(result, 0)
        self.assertEqual(events, ["synchronize", "create extractor", "extract commits", "generate diffs"])
        self.assertEqual(client.calls, [("Pix", "pix-only diff")])
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].repository_name, "repo")
        self.assertEqual(documents[0].qualifying_change_count, 1)
        self.assertEqual(documents[0].sections[0].modules[0].qualifying_change_count, 1)
        self.assertEqual(output_header, b"%PDF-")
        self.assertTrue(diff_file_removed)

    def test_run_stops_before_commit_processing_when_sync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_config_path = _write_runtime_configuration(Path(temp_dir))

            with patch(
                "release_notes_generator.workflow.synchronize_repository",
                side_effect=GitHistoryError("sync failed"),
            ), patch(
                "release_notes_generator.workflow.GitCommitExtractor"
            ) as extractor, patch(
                "release_notes_generator.workflow.generate_diff_files"
            ) as generate_diffs, patch(
                "release_notes_generator.workflow.summarize_diff_files"
            ) as summarize, patch(
                "release_notes_generator.workflow.export_release_pdf"
            ) as export:
                with self.assertRaises(GitHistoryError):
                    ReleaseNotesWorkflow(summary_client=RecordingSummaryClient()).run(
                        runtime_config_path
                    )

        extractor.assert_not_called()
        generate_diffs.assert_not_called()
        summarize.assert_not_called()
        export.assert_not_called()

    def test_run_validates_referenced_configuration_before_synchronizing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            runtime_config_path = _write_runtime_configuration(base_dir)
            (base_dir / "config" / "releaseMarker.json").write_text(
                json.dumps({"marker": ""}),
                encoding="utf-8",
            )

            with patch("release_notes_generator.workflow.synchronize_repository") as synchronize:
                with self.assertRaises(ConfigurationError):
                    ReleaseNotesWorkflow(summary_client=RecordingSummaryClient()).run(
                        runtime_config_path
                    )

        synchronize.assert_not_called()


def _write_runtime_configuration(base_dir: Path) -> Path:
    config_dir = base_dir / "config"
    config_dir.mkdir()
    (base_dir / "repo").mkdir()
    (config_dir / "user.json").write_text(
        json.dumps({"approved_author_emails": ["dev@example.com"]}),
        encoding="utf-8",
    )
    (config_dir / "module.json").write_text(
        json.dumps(
            {"modules": [{"name": "Pix", "tags": ["Pix:"], "section": "Pix"}]}
        ),
        encoding="utf-8",
    )
    (config_dir / "releaseMarker.json").write_text(
        json.dumps({"marker": "[Release]"}),
        encoding="utf-8",
    )
    (config_dir / "ai.json").write_text(
        json.dumps(
            {
                "api_url": "https://api.example.test/v1/chat/completions",
                "model": "summary-model",
                "api_key_env_var": "CHANGE_LOG_SUMMARY_AI_API_KEY",
                "prompt": "Summarize release-note diffs.",
                "max_diff_characters_per_request": 12000,
            }
        ),
        encoding="utf-8",
    )
    runtime_config_path = config_dir / "workflow.json"
    runtime_config_path.write_text(
        json.dumps(
            {
                "repository_path": "../repo",
                "user_config_path": "user.json",
                "module_config_path": "module.json",
                "release_marker_config_path": "releaseMarker.json",
                "ai_config_path": "ai.json",
                "temp_diff_dir": "../tmp/diffs",
                "output_path": "../output/release_notes.pdf",
            }
        ),
        encoding="utf-8",
    )
    return runtime_config_path


if __name__ == "__main__":
    unittest.main()

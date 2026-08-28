"""Context tests for Claude Code backend selection, isolation, and failure gating."""

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.claude_code import ClaudeCodeClient, ProcessResult
from release_notes_generator.cli import main
from release_notes_generator.configuration import ClaudeCodeAIConfig
from release_notes_generator.summarization import (
    AISummarizationError,
    SummarizationProvenance,
    summarize_diff_files_with_provenance,
)
from release_notes_generator.workflow import ReleaseNotesWorkflow
from tests.context.workflow_fixture import (
    create_repository,
    run_git,
    write_runtime_configuration,
)


VERSION_RESULT = ProcessResult(returncode=0, stdout="2.1.251 (Claude Code)\n", stderr="")


def _envelope(summary: str) -> ProcessResult:
    return ProcessResult(
        returncode=0,
        stdout=json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "structured_output": {"summary": summary},
            }
        ),
        stderr="",
    )


class FakeClaudeProcessRunner:
    """Fake process boundary answering version probes and summary requests."""

    def __init__(self, request_outcome=None) -> None:
        self.invocations: list[dict] = []
        self._request_outcome = request_outcome

    def __call__(self, args, *, stdin_text, cwd, timeout_seconds) -> ProcessResult:
        working_dir = Path(cwd)
        arguments = tuple(args)
        is_version = arguments[1:] == ("--version",)
        module_name = None
        request_kind = None
        if not is_version:
            first_line = stdin_text.splitlines()[0] if stdin_text else ""
            if first_line.startswith("Module: "):
                module_name = first_line.removeprefix("Module: ")
            request_kind = (
                "reduce" if "\nPartial summaries:\n" in stdin_text else "summarize"
            )
        self.invocations.append(
            {
                "args": arguments,
                "stdin_text": stdin_text,
                "cwd": working_dir,
                "cwd_was_empty": (
                    working_dir.is_dir() and not any(working_dir.iterdir())
                ),
                "is_version": is_version,
                "module": module_name,
                "kind": request_kind,
            }
        )
        if is_version:
            return VERSION_RESULT
        if self._request_outcome is not None:
            outcome = self._request_outcome
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        request_number = len(self.invocations)
        return _envelope(f"- {module_name} {request_kind} {request_number}")

    @property
    def request_invocations(self) -> list[dict]:
        return [entry for entry in self.invocations if not entry["is_version"]]

    @property
    def version_invocations(self) -> list[dict]:
        return [entry for entry in self.invocations if entry["is_version"]]


def _write_claude_ai_configuration(root: Path, max_characters: int = 12000) -> None:
    (root / "config" / "ai.json").write_text(
        json.dumps(
            {
                "backend": "claude_code",
                "model": "claude-model",
                "prompt": "Summarize release-note diffs.",
                "max_diff_characters_per_request": max_characters,
            }
        ),
        encoding="utf-8",
    )


class ClaudeCodeBackendSelectionTests(unittest.TestCase):
    def test_claude_code_summarizes_qualifying_diffs_without_openai_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            runtime_path = write_runtime_configuration(root, repository)
            _write_claude_ai_configuration(root)
            fake_runner = FakeClaudeProcessRunner()

            with (
                patch(
                    "release_notes_generator.claude_code.run_claude_process",
                    fake_runner,
                ),
                patch("urllib.request.urlopen") as urlopen,
                patch(
                    "release_notes_generator.summarization.OpenAIChatClient.from_config"
                ) as from_config,
            ):
                result = ReleaseNotesWorkflow().run(runtime_path)

            self.assertEqual(result, 0)
            self.assertEqual(
                (root / "analysis" / "release.pdf").read_bytes()[:5], b"%PDF-"
            )
            urlopen.assert_not_called()
            from_config.assert_not_called()
            self.assertEqual(len(fake_runner.version_invocations), 1)
            self.assertGreaterEqual(len(fake_runner.request_invocations), 1)
            self.assertIn(
                "committed feature",
                fake_runner.request_invocations[0]["stdin_text"],
            )

    def test_openai_compatible_path_remains_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            runtime_path = write_runtime_configuration(root, repository)
            fake_runner = FakeClaudeProcessRunner()

            with (
                patch(
                    "release_notes_generator.claude_code.run_claude_process",
                    fake_runner,
                ),
                patch.dict(
                    "os.environ",
                    {"CHANGE_LOG_SUMMARY_AI_API_KEY": "test-api-key"},
                ),
                patch(
                    "release_notes_generator.summarization.urllib.request.urlopen"
                ) as urlopen,
            ):
                urlopen.return_value.__enter__.return_value.read.return_value = (
                    json.dumps(
                        {"choices": [{"message": {"content": "- Pix summary"}}]}
                    ).encode("utf-8")
                )
                result = ReleaseNotesWorkflow().run(runtime_path)

            self.assertEqual(result, 0)
            self.assertEqual(
                (root / "analysis" / "release.pdf").read_bytes()[:5], b"%PDF-"
            )
            urlopen.assert_called()
            self.assertEqual(fake_runner.invocations, [])

    def test_no_qualifying_path_executes_no_backend_and_no_version_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            runtime_path = write_runtime_configuration(root, repository)
            _write_claude_ai_configuration(root)
            (root / "config" / "user.json").write_text(
                json.dumps({"approved_author_emails": ["nobody@example.com"]}),
                encoding="utf-8",
            )
            fake_runner = FakeClaudeProcessRunner()

            with (
                patch(
                    "release_notes_generator.claude_code.run_claude_process",
                    fake_runner,
                ),
                patch("urllib.request.urlopen") as urlopen,
            ):
                result = ReleaseNotesWorkflow().run(runtime_path)

            self.assertEqual(result, 0)
            self.assertEqual(
                (root / "analysis" / "release.pdf").read_bytes()[:5], b"%PDF-"
            )
            self.assertEqual(fake_runner.invocations, [])
            urlopen.assert_not_called()

    def test_explicit_summary_client_injection_bypasses_the_backend_factory(self) -> None:
        class InjectedClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def summarize(self, module_name: str, diff_content: str) -> str:
                self.calls.append((module_name, diff_content))
                return "- injected summary"

            def reduce(self, module_name: str, partial_summaries: str) -> str:
                return partial_summaries

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            runtime_path = write_runtime_configuration(root, repository)
            _write_claude_ai_configuration(root)
            injected = InjectedClient()

            with patch(
                "release_notes_generator.workflow.create_summary_client"
            ) as factory:
                result = ReleaseNotesWorkflow(summary_client=injected).run(runtime_path)

            self.assertEqual(result, 0)
            factory.assert_not_called()
            self.assertEqual(len(injected.calls), 1)


class ClaudeCodeIsolationFlowTests(unittest.TestCase):
    def test_modules_and_reduction_levels_use_ordered_isolated_fresh_processes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            source = repository / "source.txt"
            source.write_text("released\ncommitted feature\npix more\n", encoding="utf-8")
            run_git(repository, ["add", "source.txt"])
            run_git(repository, ["commit", "--quiet", "-m", "Pix: second feature"])
            source.write_text(
                "released\ncommitted feature\npix more\nloyalty\n", encoding="utf-8"
            )
            run_git(repository, ["add", "source.txt"])
            run_git(repository, ["commit", "--quiet", "-m", "GL: loyalty feature"])

            runtime_path = write_runtime_configuration(root, repository)
            (root / "config" / "module.json").write_text(
                json.dumps(
                    {
                        "modules": [
                            {"name": "Pix", "tags": ["Pix:"], "section": "Payments"},
                            {
                                "name": "GlobalLoyalty",
                                "tags": ["GL:"],
                                "section": "Loyalty",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            _write_claude_ai_configuration(root, max_characters=400)
            fake_runner = FakeClaudeProcessRunner()

            with patch(
                "release_notes_generator.claude_code.run_claude_process",
                fake_runner,
            ):
                result = ReleaseNotesWorkflow().run(runtime_path)

            self.assertEqual(result, 0)

            self.assertEqual(len(fake_runner.version_invocations), 1)
            self.assertTrue(fake_runner.invocations[0]["is_version"])

            requests = fake_runner.request_invocations
            modules_in_order = [entry["module"] for entry in requests]
            self.assertIn("Pix", modules_in_order)
            self.assertIn("GlobalLoyalty", modules_in_order)

            # Modules are processed sequentially without interleaving.
            first_global = modules_in_order.index("GlobalLoyalty")
            self.assertTrue(
                all(module == "Pix" for module in modules_in_order[:first_global])
            )
            self.assertTrue(
                all(
                    module == "GlobalLoyalty"
                    for module in modules_in_order[first_global:]
                )
            )

            pix_requests = [entry for entry in requests if entry["module"] == "Pix"]
            self.assertGreaterEqual(
                len([entry for entry in pix_requests if entry["kind"] == "summarize"]),
                2,
            )
            self.assertGreaterEqual(
                len([entry for entry in pix_requests if entry["kind"] == "reduce"]), 1
            )
            last_summarize = max(
                index
                for index, entry in enumerate(pix_requests)
                if entry["kind"] == "summarize"
            )
            first_reduce = min(
                index
                for index, entry in enumerate(pix_requests)
                if entry["kind"] == "reduce"
            )
            self.assertLess(last_summarize, first_reduce)

            # Every request runs in its own fresh empty working directory.
            working_dirs = [entry["cwd"] for entry in fake_runner.invocations]
            self.assertEqual(len(set(working_dirs)), len(working_dirs))
            self.assertTrue(
                all(entry["cwd_was_empty"] for entry in fake_runner.invocations)
            )
            self.assertTrue(
                all(not working_dir.exists() for working_dir in working_dirs)
            )

            # No request carries another module's payload or summaries.
            for entry in requests:
                other_module = (
                    "GlobalLoyalty" if entry["module"] == "Pix" else "Pix"
                )
                self.assertNotIn(f"Module: {other_module}", entry["stdin_text"])
                if entry["module"] == "Pix":
                    self.assertNotIn("loyalty feature", entry["stdin_text"])
                    self.assertNotIn("GlobalLoyalty", entry["stdin_text"])
                else:
                    self.assertNotIn("Pix:", entry["stdin_text"])

    def test_completed_summaries_carry_claude_execution_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            diff_dir = Path(temp_dir)
            pix_path = diff_dir / "diff_pix.md"
            loyalty_path = diff_dir / "diff_globalloyalty.md"
            pix_path.write_text("pix diff", encoding="utf-8")
            loyalty_path.write_text("loyalty diff", encoding="utf-8")
            fake_runner = FakeClaudeProcessRunner()
            client = ClaudeCodeClient(
                ClaudeCodeAIConfig(
                    model="claude-model",
                    prompt="Summarize release-note diffs.",
                    max_diff_characters_per_request=1000,
                ),
                process_runner=fake_runner,
            )

            outcome = summarize_diff_files_with_provenance(
                {"Pix": pix_path, "GlobalLoyalty": loyalty_path},
                client,
                max_characters_per_request=1000,
            )

        self.assertEqual(
            outcome.provenance,
            SummarizationProvenance(
                backend="claude_code",
                model="claude-model",
                claude_code_version="2.1.251",
            ),
        )
        self.assertEqual(
            [module for module, _ in outcome.module_summaries],
            ["Pix", "GlobalLoyalty"],
        )
        for _, summary in outcome.module_summaries:
            self.assertTrue(summary)


class ClaudeCodeFailureGatingTests(unittest.TestCase):
    def _run_failure_case(self, request_outcome) -> tuple[Path, Path, AISummarizationError]:
        self._temp_dir = tempfile.TemporaryDirectory()
        root = Path(self._temp_dir.name)
        self.addCleanup(self._temp_dir.cleanup)
        repository, _, _ = create_repository(root)
        runtime_path = write_runtime_configuration(root, repository)
        _write_claude_ai_configuration(root)
        output_path = root / "analysis" / "release.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"existing pdf content")
        fake_runner = FakeClaudeProcessRunner(request_outcome=request_outcome)

        with (
            patch(
                "release_notes_generator.claude_code.run_claude_process",
                fake_runner,
            ),
            patch("release_notes_generator.workflow.export_release_pdf") as export_pdf,
            self.assertRaises(AISummarizationError) as context,
        ):
            ReleaseNotesWorkflow().run(runtime_path)

        export_pdf.assert_not_called()
        return output_path, root / "analysis" / "diffs", context.exception

    def test_expected_claude_failures_preserve_existing_pdf_and_clean_diffs(self) -> None:
        failure_cases = (
            ("missing-executable", FileNotFoundError("claude")),
            ("timeout", subprocess.TimeoutExpired(cmd="claude", timeout=1)),
            (
                "login-style-failure",
                ProcessResult(1, "", "Not logged in - SECRET account details"),
            ),
            (
                "usage-limit-style-failure",
                ProcessResult(1, "", "Usage limit reached - SECRET quota"),
            ),
            ("unusable-output", ProcessResult(0, "SECRET diagnostic text", "")),
        )
        for name, request_outcome in failure_cases:
            with self.subTest(name=name):
                output_path, diff_dir, error = self._run_failure_case(request_outcome)

                self.assertEqual(output_path.read_bytes(), b"existing pdf content")
                self.assertEqual(
                    [path for path in diff_dir.glob("diff_*.md")],
                    [],
                )
                message = str(error)
                self.assertNotIn("SECRET", message)
                self.assertNotIn("committed feature", message)

    def test_cli_reports_claude_failures_concisely_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository, _, _ = create_repository(root)
            runtime_path = write_runtime_configuration(root, repository)
            _write_claude_ai_configuration(root)
            fake_runner = FakeClaudeProcessRunner(
                request_outcome=FileNotFoundError("claude")
            )
            stderr = io.StringIO()

            with (
                patch(
                    "release_notes_generator.claude_code.run_claude_process",
                    fake_runner,
                ),
                redirect_stderr(stderr),
            ):
                exit_code = main(["--config", str(runtime_path)])

            self.assertEqual(exit_code, 1)
            output = stderr.getvalue()
            error_lines = [
                line for line in output.splitlines() if line.startswith("Error: ")
            ]
            self.assertEqual(len(error_lines), 1)
            self.assertNotIn("Traceback", output)
            self.assertNotIn("committed feature", output)


if __name__ == "__main__":
    unittest.main()

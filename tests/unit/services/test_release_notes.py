import unittest
from datetime import datetime, timezone
from pathlib import Path

from release_notes_generator.domain.analysis import AnalysisPaths, DiffArtifact
from release_notes_generator.domain.configuration import (
    ClaudeCodeAISettings,
    ContributorPolicy,
    ModuleDefinition,
    ModulePolicy,
    WorkflowConfiguration,
)
from release_notes_generator.domain.release_document import ReleaseDocument
from release_notes_generator.domain.repository import (
    ClassifiedCommit,
    Commit,
    ReleaseRange,
    RepositoryRelation,
    RepositoryStatus,
)
from release_notes_generator.domain.summarization import SummarizationOutcome
from release_notes_generator.services.release_notes import ReleaseNotesService


class Collaborators:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.config = WorkflowConfiguration(
            repository_path=Path("/configured"),
            contributors=ContributorPolicy(("dev@example.com",)),
            modules=ModulePolicy((ModuleDefinition("Pay", ("PAY:",), "Payments"),)),
            ai=ClaudeCodeAISettings("sonnet", "Summarize.", 1000),
            temp_diff_dir=Path("/analysis/diffs"),
            output_path=Path("/analysis/release.pdf"),
            head_ref="main",
            base_ref="v1",
            release_marker=None,
        )
        self.paths_value = AnalysisPaths(
            Path("/repository"),
            Path("/analysis/diffs"),
            Path("/analysis/release.pdf"),
            Path("/analysis/diffs"),
            Path("/analysis/release.pdf"),
            True,
        )
        self.status = RepositoryStatus(
            0, 0, 0, "main", "origin/main", True, RepositoryRelation.EQUAL,
            0, 0, "head", warnings=("diagnostic",)
        )
        authored_at = datetime(2026, 1, 3, tzinfo=timezone.utc)
        self.commit = Commit("commit", "dev@example.com", "PAY: change", authored_at)
        self.classified = ClassifiedCommit(
            "commit", "dev@example.com", "PAY: change", "Pay", authored_at
        )
        self.artifact = DiffArtifact("Pay", Path("/analysis/diffs/diff_pay.md"))
        self.document = ReleaseDocument(
            "Release Notes", "repository", 1, authored_at.date(), authored_at.date(), ()
        )

    def load(self, path):
        self.events.append("configuration")
        return self.config

    def validate(self, configuration):
        self.events.append("validate")
        return self.paths_value

    def prepare(self, paths):
        self.events.append("prepare")
        return paths

    def revalidate(self, paths):
        self.events.append("revalidate")
        return paths

    def inspect(self, repository, head):
        self.events.append("inspect")
        return self.status

    def update(self, repository, configuration, status):
        self.events.append("update")
        return status

    def freeze_range(self, repository, configuration):
        self.events.append("freeze")
        return ReleaseRange("base", "head")

    def extract(self, repository, release_range):
        self.events.append("extract")
        return (self.commit,)

    def select(self, commits, contributors, modules):
        self.events.append("select")
        return (self.classified,)

    def group(self, commits):
        self.events.append("group")
        return {"Pay": ("commit",)}

    def generate(self, repository, groups, directory):
        self.events.append("diff")
        return (self.artifact,)

    def cleanup(self, artifacts):
        self.events.append("cleanup")
        self.cleaned = tuple(artifacts)

    def summarize(self, artifacts, settings, env_file):
        self.events.append("summarize")
        return SummarizationOutcome((("Pay", "- summary"),), None)

    def compose(self, summaries, modules, repository_name, accepted):
        self.events.append("compose")
        return self.document

    def export(self, document, output_path):
        self.events.append("export")
        return output_path


class ReleaseNotesServiceTests(unittest.TestCase):
    def test_generate_uses_the_required_order_and_cleans_up_in_finally(self) -> None:
        collaborators = Collaborators()
        warnings: list[str] = []
        service = ReleaseNotesService(
            collaborators,
            collaborators,
            collaborators,
            collaborators,
            collaborators,
            collaborators,
            collaborators,
            collaborators,
            warning_handler=warnings.append,
        )

        output = service.generate(Path("workflow.json"))

        self.assertEqual(output, Path("/analysis/release.pdf"))
        self.assertEqual(warnings, ["diagnostic"])
        self.assertEqual(
            collaborators.events,
            [
                "configuration", "validate", "inspect", "update", "freeze",
                "extract", "select", "group", "prepare", "diff", "summarize",
                "compose", "revalidate", "export", "cleanup",
            ],
        )
        self.assertEqual(collaborators.cleaned, (collaborators.artifact,))

    def test_cleanup_runs_when_downstream_summarization_fails(self) -> None:
        collaborators = Collaborators()

        def fail(*args):
            collaborators.events.append("summarize")
            raise RuntimeError("failed")

        collaborators.summarize = fail
        service = ReleaseNotesService(
            collaborators, collaborators, collaborators, collaborators,
            collaborators, collaborators, collaborators, collaborators,
        )

        with self.assertRaisesRegex(RuntimeError, "failed"):
            service.generate(Path("workflow.json"))

        self.assertEqual(collaborators.events[-1], "cleanup")
        self.assertEqual(collaborators.cleaned, (collaborators.artifact,))


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from release_notes_generator.domain.configuration import (
    ContributorPolicy,
    ModuleDefinition,
    ModulePolicy,
)
from release_notes_generator.domain.repository import Commit
from release_notes_generator.infrastructure.artifacts import LocalArtifactStore
from release_notes_generator.services.commit_selection import CommitSelectionService
from release_notes_generator.services.diff_generation import DiffGenerationService


class RecordingGit:
    def __init__(self) -> None:
        self.shown: list[str] = []

    def show(self, repository_path: Path, commit_hash: str) -> str:
        self.shown.append(commit_hash)
        return {
            "pix1": "pix diff",
            "gl1": "global loyalty diff",
            "tol1": "transit diff",
        }[commit_hash]


class DiffGenerationFlowTests(unittest.TestCase):
    def test_accepted_commits_are_rendered_into_expected_temporary_markdown_files(self) -> None:
        commits = (
            _commit("pix1", "approved@example.com", "Pix: add payment"),
            _commit("gl1", "approved@example.com", "GlobalLoyalty: add rewards"),
            _commit("tol1", "approved@example.com", "TransitOpenLoop: add fare"),
            _commit("bad-author", "unknown@example.com", "Pix: should be ignored"),
            _commit("bad-module", "approved@example.com", "Unknown: should be ignored"),
        )
        modules = ModulePolicy(
            (
                ModuleDefinition("Pix", ("Pix",), "Pix"),
                ModuleDefinition("GlobalLoyalty", ("GlobalLoyalty",), "Global Features"),
                ModuleDefinition("TransitOpenLoop", ("TransitOpenLoop",), "Global Features"),
            )
        )
        selection = CommitSelectionService()
        accepted_commits = selection.select(
            commits, ContributorPolicy(("approved@example.com",)), modules
        )
        grouped_hashes = selection.group(accepted_commits)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            git = RecordingGit()
            artifacts = DiffGenerationService(git, LocalArtifactStore()).generate(
                Path("/repo"), grouped_hashes, output_dir
            )
            generated_files = {
                artifact.module_name: artifact.path for artifact in artifacts
            }

            self.assertEqual(
                generated_files,
                {
                    "Pix": output_dir / "diff_pix.md",
                    "GlobalLoyalty": output_dir / "diff_globalloyalty.md",
                    "TransitOpenLoop": output_dir / "diff_transitopenloop.md",
                },
            )
            self.assertEqual((output_dir / "diff_pix.md").read_text(encoding="utf-8"), "pix diff\n")
            self.assertEqual(
                (output_dir / "diff_globalloyalty.md").read_text(encoding="utf-8"),
                "global loyalty diff\n",
            )
            self.assertEqual(
                (output_dir / "diff_transitopenloop.md").read_text(encoding="utf-8"),
                "transit diff\n",
            )
            self.assertEqual(
                git.shown,
                ["pix1", "gl1", "tol1"],
            )


def _commit(commit_hash: str, author_email: str, subject: str) -> Commit:
    return Commit(
        commit_hash,
        author_email,
        subject,
        datetime(2026, 1, 3, 12, tzinfo=timezone.utc),
    )


if __name__ == "__main__":
    unittest.main()

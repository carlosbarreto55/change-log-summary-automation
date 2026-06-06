"""Command-line entry point for release notes generation."""

from release_notes_generator.workflow import ReleaseNotesWorkflow


def main() -> int:
    """Run the release notes workflow."""
    workflow = ReleaseNotesWorkflow()
    return workflow.run()

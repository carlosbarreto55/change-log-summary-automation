"""Command-line entry point for release notes generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from release_notes_generator.commits import GitHistoryError
from release_notes_generator.configuration import ConfigurationError
from release_notes_generator.diffs import DiffGenerationError
from release_notes_generator.pdf_export import PDFGenerationError
from release_notes_generator.repository_safety import RepositorySafetyError
from release_notes_generator.summarization import AISummarizationError
from release_notes_generator.workflow import ReleaseNotesWorkflow


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the release notes workflow."""
    parser = argparse.ArgumentParser(
        prog="change-log-summary",
        description="Generate PDF release notes from a configured Git repository.",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to the runtime workflow JSON configuration file.",
    )
    args = parser.parse_args(argv)

    workflow = ReleaseNotesWorkflow(
        warning_handler=lambda warning: print(f"Warning: {warning}", file=sys.stderr)
    )
    try:
        return workflow.run(args.config)
    except (
        ConfigurationError,
        GitHistoryError,
        DiffGenerationError,
        AISummarizationError,
        PDFGenerationError,
        RepositorySafetyError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

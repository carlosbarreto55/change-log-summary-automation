"""Command-line entry point for release notes generation."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from release_notes_generator.workflow import ReleaseNotesWorkflow


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the release notes workflow."""
    parser = argparse.ArgumentParser(
        prog="change-log-summary",
        description="Generate Markdown release notes from a configured Git repository.",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to the runtime workflow JSON configuration file.",
    )
    args = parser.parse_args(argv)

    workflow = ReleaseNotesWorkflow()
    return workflow.run(args.config)

"""Command-line entry point for release notes generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from release_notes_generator.presentation.composition import compose_release_notes_service
from release_notes_generator.services.errors import (
    AISummarizationError,
    ConfigurationError,
    DiffGenerationError,
    GitHistoryError,
    PDFGenerationError,
    RepositorySafetyError,
)


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

    service = compose_release_notes_service(
        warning_handler=lambda warning: print(f"Warning: {warning}", file=sys.stderr)
    )
    try:
        service.generate(args.config)
        return 0
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

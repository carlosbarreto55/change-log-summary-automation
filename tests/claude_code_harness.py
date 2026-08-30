"""Install and inspect the deterministic fake Claude Code executable."""

from __future__ import annotations

import json
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch


FAKE_CLAUDE_SOURCE = (
    Path(__file__).parent / "fixtures" / "claude_code" / "fake_claude.py"
)


@contextmanager
def installed_fake_claude(
    root: Path,
    *,
    mode: str = "success",
) -> Iterator[Path]:
    """Place the fake executable first on PATH and yield its JSONL record path."""
    binary_directory = root / "fake-claude-bin"
    binary_directory.mkdir(parents=True)
    executable_path = binary_directory / "claude"
    shutil.copy2(FAKE_CLAUDE_SOURCE, executable_path)
    executable_path.chmod(0o755)
    record_path = root / "fake-claude-records.jsonl"
    environment = {
        "PATH": f"{binary_directory}{os.pathsep}{os.environ.get('PATH', '')}",
        "FAKE_CLAUDE_RECORD_PATH": str(record_path),
        "FAKE_CLAUDE_MODE": mode,
    }
    with patch.dict(os.environ, environment):
        yield record_path


def load_fake_claude_records(record_path: Path) -> tuple[dict, ...]:
    """Load the sanitized records written by the fake executable."""
    if not record_path.exists():
        return ()
    return tuple(
        json.loads(line)
        for line in record_path.read_text(encoding="utf-8").splitlines()
        if line
    )

"""Project filesystem locations used by the release notes workflow."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
TEMP_DIFF_DIR = PROJECT_ROOT / "tmp" / "diffs"
OUTPUT_DIR = PROJECT_ROOT / "output"

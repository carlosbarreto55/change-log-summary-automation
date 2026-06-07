"""Project filesystem locations used by the release notes workflow."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_USER_CONFIG_PATH = CONFIG_DIR / "user.json"
DEFAULT_MODULE_CONFIG_PATH = CONFIG_DIR / "module.json"
DEFAULT_RELEASE_MARKER_CONFIG_PATH = CONFIG_DIR / "releaseMarker.json"
DEFAULT_AI_CONFIG_PATH = CONFIG_DIR / "ai.json"
LOCAL_ENV_FILE_PATH = PROJECT_ROOT / ".env.local"
TEMP_DIFF_DIR = PROJECT_ROOT / "tmp" / "diffs"
OUTPUT_DIR = PROJECT_ROOT / "output"

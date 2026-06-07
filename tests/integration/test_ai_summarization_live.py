import json
import os
import shutil
import subprocess
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.commits import (
    GitCommitExtractor,
    filter_commits,
    group_commit_hashes_by_module,
)
from release_notes_generator.configuration import (
    load_ai_config,
    load_module_config,
    load_release_marker_config,
    load_user_config,
)
from release_notes_generator.diffs import generate_diff_files
from release_notes_generator.paths import CONFIG_DIR, LOCAL_ENV_FILE_PATH, PROJECT_ROOT
from release_notes_generator.summarization import (
    OpenAIChatClient,
    load_env_file,
    summarize_diff_files,
)


REDIS_REPOSITORY_PATH = PROJECT_ROOT.parent / "redis"
USER_IT_CONFIG_PATH = CONFIG_DIR / "userIT.json"
MODULE_IT_CONFIG_PATH = CONFIG_DIR / "moduleIT.json"
RELEASE_MARKER_IT_CONFIG_PATH = CONFIG_DIR / "releaseMarkerIT.json"
AI_IT_CONFIG_PATH = CONFIG_DIR / "aiIT.json"
ASSETS_DIR = PROJECT_ROOT / "tests" / "assets"


class LiveAISummarizationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.environment = load_env_file(LOCAL_ENV_FILE_PATH)
        cls.environment.update(os.environ)
        if cls.environment.get("RUN_LIVE_AI_IT", "").lower() not in {"1", "true", "yes"}:
            raise unittest.SkipTest("Set RUN_LIVE_AI_IT=1 to run live AI integration tests.")

        if not REDIS_REPOSITORY_PATH.exists():
            raise unittest.SkipTest(
                f"Redis integration fixture not found at {REDIS_REPOSITORY_PATH}. "
                "Clone it once outside the test run."
            )

        result = subprocess.run(
            ["git", "-C", str(REDIS_REPOSITORY_PATH), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise unittest.SkipTest(
                f"Redis integration fixture is not a Git repository: {REDIS_REPOSITORY_PATH}"
            )

        cls.ai_config = load_ai_config(AI_IT_CONFIG_PATH)
        if not cls.environment.get(cls.ai_config.api_key_env_var):
            raise unittest.SkipTest(
                f"Missing AI API key environment variable: {cls.ai_config.api_key_env_var}"
            )

    def test_live_ai_summarizes_separated_redis_diff_payloads(self) -> None:
        _reset_assets_dir()
        release_marker_config = load_release_marker_config(RELEASE_MARKER_IT_CONFIG_PATH)
        user_config = load_user_config(USER_IT_CONFIG_PATH)
        module_config = load_module_config(MODULE_IT_CONFIG_PATH)
        commits = GitCommitExtractor(REDIS_REPOSITORY_PATH).commits_after_latest_release_marker(
            release_marker_config.marker
        )
        accepted_commits = filter_commits(
            commits,
            user_config.approved_author_emails,
            module_config.module_tags,
        )
        selected_commits = _first_commit_per_module(accepted_commits, tuple(module_config.module_tags))

        grouped_hashes = group_commit_hashes_by_module(selected_commits)
        diff_files = generate_diff_files(REDIS_REPOSITORY_PATH, grouped_hashes, ASSETS_DIR)
        client = OpenAIChatClient.from_config(self.ai_config, environ=self.environment)
        original_urlopen = urllib.request.urlopen
        request_count = 0
        request_assets_dir = ASSETS_DIR / "ai_requests"

        def recording_urlopen(request, *args, **kwargs):
            nonlocal request_count
            request_count += 1
            _write_ai_request_asset(request_assets_dir, request_count, request)
            return original_urlopen(request, *args, **kwargs)

        with patch(
            "release_notes_generator.summarization.urllib.request.urlopen",
            side_effect=recording_urlopen,
        ):
            summaries = summarize_diff_files(diff_files, client)

        self.assertEqual(set(summaries), set(grouped_hashes))
        self.assertEqual(request_count, len(grouped_hashes))
        request_asset_paths = sorted(request_assets_dir.glob("request_*.json"))
        self.assertEqual(len(request_asset_paths), len(grouped_hashes))
        request_modules = {
            json.loads(path.read_text(encoding="utf-8"))["module_name"]
            for path in request_asset_paths
        }
        self.assertEqual(request_modules, set(grouped_hashes))
        for module_name, summary in summaries.items():
            self.assertTrue(summary.strip())
            summary_path = ASSETS_DIR / f"summary_{module_name.lower()}.md"
            summary_path.write_text(summary, encoding="utf-8")
            self.assertTrue(summary_path.is_file())


class AIRequestAssetTests(unittest.TestCase):
    def test_ai_request_asset_redacts_authorization_and_preserves_payload(self) -> None:
        payload = {
            "model": "kimi-k2.6",
            "messages": [
                {"role": "system", "content": "Summarize release-note diffs."},
                {"role": "user", "content": "Module: Pix\n\nDiff:\npix diff"},
            ],
        }
        request = urllib.request.Request(
            "https://opencode.ai/zen/go/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer secret-api-key",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            asset_path = _write_ai_request_asset(Path(temp_dir), 1, request)
            asset_text = asset_path.read_text(encoding="utf-8")
            asset = json.loads(asset_text)

        headers = {key.lower(): value for key, value in asset["headers"].items()}
        self.assertEqual(asset_path.name, "request_01_pix.json")
        self.assertEqual(asset["request_number"], 1)
        self.assertEqual(asset["module_name"], "Pix")
        self.assertEqual(asset["url"], "https://opencode.ai/zen/go/v1/chat/completions")
        self.assertEqual(asset["method"], "POST")
        self.assertEqual(headers["authorization"], "<redacted>")
        self.assertEqual(asset["body"], payload)
        self.assertNotIn("secret-api-key", asset_text)


def _first_commit_per_module(accepted_commits, module_names: tuple[str, ...]):
    selected = {}
    for commit in accepted_commits:
        selected.setdefault(commit.module_name, commit)
        if all(module_name in selected for module_name in module_names):
            break

    missing_modules = set(module_names) - set(selected)
    if missing_modules:
        raise AssertionError(f"No accepted Redis commits found for modules: {missing_modules}")
    return tuple(selected[module_name] for module_name in module_names)


def _reset_assets_dir() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for path in ASSETS_DIR.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _write_ai_request_asset(assets_dir: Path, request_number: int, request) -> Path:
    assets_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(request.data.decode("utf-8"))
    module_name = _module_name_from_payload(payload)
    asset_path = assets_dir / f"request_{request_number:02d}_{_asset_safe_name(module_name)}.json"
    asset = {
        "request_number": request_number,
        "module_name": module_name,
        "url": request.full_url,
        "method": request.get_method(),
        "headers": _redacted_headers(request),
        "body": payload,
    }
    asset_path.write_text(json.dumps(asset, indent=2, sort_keys=True), encoding="utf-8")
    return asset_path


def _redacted_headers(request) -> dict[str, str]:
    redacted_headers = {}
    sensitive_headers = {"authorization", "api-key", "x-api-key"}
    for key, value in request.header_items():
        redacted_headers[key] = "<redacted>" if key.lower() in sensitive_headers else value
    return redacted_headers


def _module_name_from_payload(payload) -> str:
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list):
        return "unknown"

    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        first_line = content.splitlines()[0] if content.splitlines() else ""
        if first_line.startswith("Module: "):
            return first_line.removeprefix("Module: ").strip() or "unknown"
    return "unknown"


def _asset_safe_name(value: str) -> str:
    safe_name = "".join(character.lower() if character.isalnum() else "_" for character in value)
    return safe_name.strip("_") or "unknown"


if __name__ == "__main__":
    unittest.main()

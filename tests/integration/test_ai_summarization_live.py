import json
import os
import shutil
import subprocess
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from release_notes_generator.infrastructure.artifacts import LocalArtifactStore
from release_notes_generator.infrastructure.environment import EnvironmentFileAdapter
from release_notes_generator.infrastructure.git import GitAdapter
from release_notes_generator.infrastructure.json_reader import FileJSONReader
from release_notes_generator.infrastructure.openai import SummaryClientFactoryAdapter
from release_notes_generator.services.commit_selection import CommitSelectionService
from release_notes_generator.services.configuration import ConfigurationService
from release_notes_generator.services.diff_generation import DiffGenerationService
from release_notes_generator.services.summarization import SummarizationService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
LOCAL_ENV_FILE_PATH = PROJECT_ROOT / ".env.local"
LINUX_REPOSITORY_PATH = PROJECT_ROOT.parent / "linux"
WORKFLOW_IT_CONFIG_PATH = CONFIG_DIR / "workflowLinuxIT.json"
USER_IT_CONFIG_PATH = CONFIG_DIR / "userIT.json"
MODULE_IT_CONFIG_PATH = CONFIG_DIR / "moduleIT.json"
RELEASE_MARKER_IT_CONFIG_PATH = CONFIG_DIR / "releaseMarkerIT.json"
AI_IT_CONFIG_PATH = CONFIG_DIR / "aiIT.json"
ASSETS_DIR = PROJECT_ROOT / "tests" / "assets"


class LiveAISummarizationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.environment = EnvironmentFileAdapter().load(LOCAL_ENV_FILE_PATH)
        cls.environment.update(os.environ)
        if cls.environment.get("RUN_LIVE_AI_IT", "").lower() not in {"1", "true", "yes"}:
            raise unittest.SkipTest("Set RUN_LIVE_AI_IT=1 to run live AI integration tests.")

        if not LINUX_REPOSITORY_PATH.exists():
            raise unittest.SkipTest(
                f"Linux integration fixture not found at {LINUX_REPOSITORY_PATH}. "
                "Clone git@github.com:torvalds/linux.git once outside the test run."
            )

        result = subprocess.run(
            ["git", "-C", str(LINUX_REPOSITORY_PATH), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise unittest.SkipTest(
                f"Linux integration fixture is not a Git repository: {LINUX_REPOSITORY_PATH}"
            )

        cls.workflow_config = ConfigurationService(FileJSONReader()).load(
            WORKFLOW_IT_CONFIG_PATH
        )
        cls.ai_config = cls.workflow_config.ai
        if not cls.environment.get(cls.ai_config.api_key_env_var):
            raise unittest.SkipTest(
                f"Missing AI API key environment variable: {cls.ai_config.api_key_env_var}"
            )

    def test_live_ai_summarizes_bounded_separated_linux_diff_payloads(self) -> None:
        _reset_assets_dir()
        configuration = self.workflow_config
        git = GitAdapter()
        release_range = git.resolve_release_range(
            LINUX_REPOSITORY_PATH,
            configuration.head_ref,
            base_ref=configuration.base_ref,
            release_marker=configuration.release_marker,
        )
        selection = CommitSelectionService()
        accepted_commits = selection.select(
            git.commits_in_range(LINUX_REPOSITORY_PATH, release_range),
            configuration.contributors,
            configuration.modules,
        )
        selected_commits = _first_commit_per_module(
            accepted_commits, tuple(configuration.modules.module_tags)
        )

        grouped_hashes = selection.group(selected_commits)
        store = LocalArtifactStore()
        artifacts = DiffGenerationService(git, store).generate(
            LINUX_REPOSITORY_PATH, grouped_hashes, ASSETS_DIR
        )
        client = SummaryClientFactoryAdapter(environ=self.environment).create(
            self.ai_config, None
        )
        original_urlopen = urllib.request.urlopen
        request_count = 0
        request_assets_dir = ASSETS_DIR / "ai_requests"

        def recording_urlopen(request, *args, **kwargs):
            nonlocal request_count
            request_count += 1
            _write_ai_request_asset(request_assets_dir, request_count, request)
            return original_urlopen(request, *args, **kwargs)

        with patch(
            "release_notes_generator.infrastructure.openai.urllib.request.urlopen",
            side_effect=recording_urlopen,
        ):
            summaries = SummarizationService(store, SummaryClientFactoryAdapter(), client).summarize(
                artifacts, self.ai_config, None
            ).summaries

        self.assertEqual(set(summaries), set(grouped_hashes))
        self.assertGreaterEqual(request_count, len(grouped_hashes))
        request_asset_paths = sorted(request_assets_dir.glob("request_*.json"))
        self.assertEqual(len(request_asset_paths), len(grouped_hashes))
        request_modules = {
            json.loads(path.read_text(encoding="utf-8"))["module_name"]
            for path in request_asset_paths
        }
        self.assertEqual(request_modules, set(grouped_hashes))
        self.assertTrue(
            all(
                len(_bounded_input_from_payload(json.loads(path.read_text(encoding="utf-8"))["body"]))
                <= self.ai_config.max_diff_characters_per_request
                for path in request_asset_paths
            )
        )
        for module_name, summary in summaries.items():
            self.assertTrue(summary.strip())
            summary_path = ASSETS_DIR / f"summary_{_asset_safe_name(module_name)}.md"
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
        raise AssertionError(f"No accepted Linux commits found for modules: {missing_modules}")
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


def _bounded_input_from_payload(payload) -> str:
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list):
        return ""

    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        for boundary in ("\n\nDiff:\n", "\n\nPartial summaries:\n"):
            if boundary in content:
                return content.split(boundary, 1)[1]
    return ""


def _asset_safe_name(value: str) -> str:
    safe_name = "".join(character.lower() if character.isalnum() else "_" for character in value)
    return safe_name.strip("_") or "unknown"


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

import dataclasses

from release_notes_generator.domain.configuration import (
    AIBackend,
    ClaudeCodeAISettings,
    ModuleDefinition,
    OpenAICompatibleAISettings,
    ReportMode,
    RepositoryUpdateMode,
)
from release_notes_generator.infrastructure.json_reader import FileJSONReader
from release_notes_generator.services.configuration import ConfigurationService
from release_notes_generator.services.errors import ConfigurationError


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _valid_user_data():
    return {"approved_author_emails": []}


def _valid_module_data():
    return {
        "modules": [{"name": "Pix", "tags": ["Pix:"], "section": "Pix"}]
    }


def _write_json_if_missing(path: Path, data) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _resolved_reference(runtime_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve(strict=False)
    return (runtime_path.resolve(strict=False).parent / path).resolve(strict=False)


def load_runtime_config(config_path: Path):
    runtime_path = Path(config_path)
    data = json.loads(runtime_path.read_text(encoding="utf-8"))
    references = (
        ("user_config_path", _valid_user_data()),
        ("module_config_path", _valid_module_data()),
        ("ai_config_path", _openai_ai_config_data()),
    )
    for field_name, content in references:
        value = data.get(field_name)
        if isinstance(value, str) and value.strip():
            _write_json_if_missing(_resolved_reference(runtime_path, value), content)
    marker_value = data.get("release_marker_config_path")
    if isinstance(marker_value, str) and marker_value.strip():
        _write_json_if_missing(
            _resolved_reference(runtime_path, marker_value), {"marker": "[Release]"}
        )
    return ConfigurationService(FileJSONReader()).load(runtime_path)


def _load_component(config_path: Path, component: str):
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        runtime = {
            **_runtime_config_data(),
            "user_config_path": str(PROJECT_ROOT / "config" / "user.json"),
            "module_config_path": str(PROJECT_ROOT / "config" / "module.json"),
            "ai_config_path": str(root / "valid-ai.json"),
        }
        (root / "valid-ai.json").write_text(
            json.dumps(_openai_ai_config_data()), encoding="utf-8"
        )
        if component == "user":
            runtime["user_config_path"] = str(config_path)
        elif component == "module":
            runtime["module_config_path"] = str(config_path)
        elif component == "ai":
            runtime["ai_config_path"] = str(config_path)
        elif component == "marker":
            runtime.pop("base_ref")
            runtime["release_marker_config_path"] = str(config_path)
        runtime_path = root / "workflow.json"
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
        loaded = ConfigurationService(FileJSONReader()).load(runtime_path)
    if component == "user":
        return loaded.contributors
    if component == "module":
        return loaded.modules
    if component == "ai":
        return loaded.ai
    return type("ReleaseMarker", (), {"marker": loaded.release_marker})()


def load_user_config(config_path: Path = PROJECT_ROOT / "config" / "user.json"):
    return _load_component(config_path, "user")


def load_module_config(config_path: Path = PROJECT_ROOT / "config" / "module.json"):
    return _load_component(config_path, "module")


def load_release_marker_config(
    config_path: Path = PROJECT_ROOT / "config" / "releaseMarker.json",
):
    return _load_component(config_path, "marker")


def load_ai_config(config_path: Path):
    return _load_component(config_path, "ai")


def _openai_ai_config_data() -> dict[str, object]:
    return {
        "api_url": "https://api.example.test/v1/chat/completions",
        "model": "summary-model",
        "api_key_env_var": "CHANGE_LOG_SUMMARY_AI_API_KEY",
        "prompt": "Summarize this diff.",
        "max_diff_characters_per_request": 12000,
    }


def _claude_code_ai_config_data() -> dict[str, object]:
    return {
        "backend": "claude_code",
        "model": "claude-sonnet-5",
        "prompt": "Summarize this diff.",
        "max_diff_characters_per_request": 12000,
    }


def _load_ai_config_from_data(temp_dir: str, data: dict[str, object]):
    config_path = Path(temp_dir) / "ai.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")
    return load_ai_config(config_path)


def _runtime_config_data() -> dict[str, object]:
    return {
        "repository_path": "repo",
        "user_config_path": "user.json",
        "module_config_path": "module.json",
        "ai_config_path": "ai.json",
        "temp_diff_dir": "tmp/diffs",
        "output_path": "output/release_notes.pdf",
        "head_ref": "refs/remotes/origin/main",
        "base_ref": "refs/tags/v1.0.0",
    }


class ConfigurationTests(unittest.TestCase):
    def test_report_mode_values_are_explicit(self) -> None:
        self.assertEqual(
            tuple(mode.value for mode in ReportMode),
            ("ai_summary", "commit_list"),
        )

    def test_load_runtime_config_defaults_missing_report_mode_to_ai_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_config_path = Path(temp_dir) / "workflow.json"
            runtime_config_path.write_text(
                json.dumps(_runtime_config_data()), encoding="utf-8"
            )

            configuration = load_runtime_config(runtime_config_path)

        self.assertIs(configuration.report_mode, ReportMode.AI_SUMMARY)
        self.assertIsNotNone(configuration.ai)
        self.assertIsNotNone(configuration.temp_diff_dir)

    def test_load_runtime_config_accepts_explicit_ai_summary_mode_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _runtime_config_data()
            data["report_mode"] = "ai_summary"
            runtime_config_path = Path(temp_dir) / "workflow.json"
            runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

            configuration = load_runtime_config(runtime_config_path)

        self.assertIs(configuration.report_mode, ReportMode.AI_SUMMARY)
        self.assertIsInstance(configuration.ai, OpenAICompatibleAISettings)
        self.assertEqual(
            configuration.temp_diff_dir,
            (Path(temp_dir) / "tmp" / "diffs").resolve(),
        )

    def test_load_runtime_config_accepts_commit_list_without_ai_or_diff_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _runtime_config_data()
            data["report_mode"] = "commit_list"
            data.pop("ai_config_path")
            data.pop("temp_diff_dir")
            runtime_config_path = Path(temp_dir) / "workflow.json"
            runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

            configuration = load_runtime_config(runtime_config_path)

        self.assertIs(configuration.report_mode, ReportMode.COMMIT_LIST)
        self.assertIsNone(configuration.ai)
        self.assertIsNone(configuration.temp_diff_dir)
        self.assertIsNone(configuration.env_file_path)

    def test_commit_list_ignores_unusable_ai_environment_and_diff_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data = _runtime_config_data()
            data.update(
                {
                    "report_mode": "commit_list",
                    "ai_config_path": "missing-ai.json",
                    "env_file_path": {"not": "a path"},
                    "temp_diff_dir": ["not", "a", "path"],
                }
            )
            runtime_config_path = root / "workflow.json"
            runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

            configuration = load_runtime_config(runtime_config_path)

        self.assertFalse((root / "missing-ai.json").exists())
        self.assertIs(configuration.report_mode, ReportMode.COMMIT_LIST)
        self.assertIsNone(configuration.ai)
        self.assertIsNone(configuration.temp_diff_dir)
        self.assertIsNone(configuration.env_file_path)

    def test_load_runtime_config_rejects_invalid_report_modes(self) -> None:
        for mode in ("unknown", "", "   ", None, 7, True, []):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp_dir:
                data = _runtime_config_data()
                data["report_mode"] = mode
                runtime_config_path = Path(temp_dir) / "workflow.json"
                runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

                with self.assertRaises(ConfigurationError):
                    load_runtime_config(runtime_config_path)

    def test_explicit_ai_summary_still_requires_usable_ai_and_diff_fields(self) -> None:
        invalid_fields = (
            ("ai_config_path", None),
            ("ai_config_path", ""),
            ("temp_diff_dir", None),
            ("temp_diff_dir", ""),
        )
        for field_name, value in invalid_fields:
            with (
                self.subTest(field=field_name, value=value),
                tempfile.TemporaryDirectory() as temp_dir,
            ):
                data = _runtime_config_data()
                data["report_mode"] = "ai_summary"
                if value is None:
                    data.pop(field_name)
                else:
                    data[field_name] = value
                runtime_config_path = Path(temp_dir) / "workflow.json"
                runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

                with self.assertRaises(ConfigurationError):
                    load_runtime_config(runtime_config_path)

    def test_load_user_config_reads_default_approved_author_emails(self) -> None:
        config = load_user_config()

        self.assertEqual(config.approved_author_emails, ())

    def test_load_module_config_reads_default_supported_modules(self) -> None:
        config = load_module_config()

        self.assertEqual(
            config.modules,
            (
                ModuleDefinition("Pix", ("Pix",), "Pix"),
                ModuleDefinition("GlobalLoyalty", ("GlobalLoyalty",), "Global Features"),
                ModuleDefinition("TransitOpenLoop", ("TransitOpenLoop",), "Global Features"),
            ),
        )

    def test_load_module_config_preserves_json_order_and_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "module.json"
            config_path.write_text(
                json.dumps(
                    {
                        "modules": [
                            {"name": "Second", "tags": ["S:"], "section": "Later"},
                            {"name": "First", "tags": ["F:"], "section": "Earlier"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            config = load_module_config(config_path)

        self.assertEqual(
            config.modules,
            (
                ModuleDefinition("Second", ("S:",), "Later"),
                ModuleDefinition("First", ("F:",), "Earlier"),
            ),
        )
        self.assertEqual(config.module_tags, {"Second": ("S:",), "First": ("F:",)})

    def test_load_module_config_rejects_missing_empty_or_unusable_sections(self) -> None:
        invalid_sections = (None, "", 42)
        for section in invalid_sections:
            with self.subTest(section=section), tempfile.TemporaryDirectory() as temp_dir:
                config_path = Path(temp_dir) / "module.json"
                module = {"name": "Pix", "tags": ["Pix:"]}
                if section is not None:
                    module["section"] = section
                config_path.write_text(
                    json.dumps({"modules": [module]}),
                    encoding="utf-8",
                )

                with self.assertRaises(ConfigurationError):
                    load_module_config(config_path)

    def test_load_release_marker_config_reads_default_marker(self) -> None:
        config = load_release_marker_config()

        self.assertEqual(config.marker, "[Release]")

    def test_load_release_marker_config_rejects_unusable_marker_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            unreadable_path = config_dir / "directory.json"
            unreadable_path.mkdir()
            unusable_files = (
                ("missing", config_dir / "missing.json", None),
                ("unreadable", unreadable_path, None),
                ("malformed", config_dir / "malformed.json", "not json"),
                ("non-object", config_dir / "non-object.json", "[]"),
                ("absent-marker", config_dir / "absent-marker.json", "{}"),
                ("empty-marker", config_dir / "empty-marker.json", '{"marker": ""}'),
                (
                    "blank-marker",
                    config_dir / "blank-marker.json",
                    '{"marker": "   "}',
                ),
            )

            for name, config_path, content in unusable_files:
                with self.subTest(name=name):
                    if content is not None:
                        config_path.write_text(content, encoding="utf-8")

                    with self.assertRaises(ConfigurationError):
                        load_release_marker_config(config_path)

    def test_load_ai_config_reads_api_settings_without_secret_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.json"
            config_path.write_text(
                json.dumps(
                    {
                        "api_url": "https://api.example.test/v1/chat/completions",
                        "model": "summary-model",
                        "api_key_env_var": "CHANGE_LOG_SUMMARY_AI_API_KEY",
                        "prompt": "Summarize this diff.",
                        "max_diff_characters_per_request": 12000,
                    }
                ),
                encoding="utf-8",
            )

            config = load_ai_config(config_path)

        self.assertEqual(config.api_url, "https://api.example.test/v1/chat/completions")
        self.assertEqual(config.model, "summary-model")
        self.assertEqual(config.api_key_env_var, "CHANGE_LOG_SUMMARY_AI_API_KEY")
        self.assertEqual(config.prompt, "Summarize this diff.")
        self.assertEqual(config.max_diff_characters_per_request, 12000)
        self.assertFalse(hasattr(config, "api_key"))

    def test_load_ai_config_rejects_invalid_request_limits(self) -> None:
        invalid_limits = (None, True, 0, -1, 1.5, "1000")
        for limit in invalid_limits:
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as temp_dir:
                config_path = Path(temp_dir) / "ai.json"
                data = {
                    "api_url": "https://api.example.test/v1/chat/completions",
                    "model": "summary-model",
                    "api_key_env_var": "CHANGE_LOG_SUMMARY_AI_API_KEY",
                    "prompt": "Summarize this diff.",
                }
                if limit is not None:
                    data["max_diff_characters_per_request"] = limit
                config_path.write_text(json.dumps(data), encoding="utf-8")

                with self.assertRaises(ConfigurationError):
                    load_ai_config(config_path)

    def test_load_runtime_config_resolves_paths_relative_to_runtime_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            runtime_config_path = config_dir / "workflow.json"
            runtime_config_path.write_text(
                json.dumps(
                    {
                        "repository_path": "../target-repo",
                        "user_config_path": "user.json",
                        "module_config_path": "module.json",
                        "release_marker_config_path": "releaseMarker.json",
                        "ai_config_path": "ai.json",
                        "temp_diff_dir": "../tmp/diffs",
                        "output_path": "../output/release_notes.pdf",
                        "env_file_path": "../.env.local",
                        "head_ref": "refs/remotes/origin/main",
                    }
                ),
                encoding="utf-8",
            )

            config = load_runtime_config(runtime_config_path)

        self.assertEqual(config.repository_path, (config_dir / "../target-repo").resolve())
        self.assertEqual(config.contributors.approved_author_emails, ())
        self.assertEqual(config.modules.modules[0].name, "Pix")
        self.assertEqual(config.release_marker, "[Release]")
        self.assertEqual(config.ai.model, "summary-model")
        self.assertEqual(config.temp_diff_dir, (config_dir / "../tmp/diffs").resolve())
        self.assertEqual(config.output_path, (config_dir / "../output/release_notes.pdf").resolve())
        self.assertEqual(config.env_file_path, (config_dir / "../.env.local").resolve())

    def test_load_runtime_config_accepts_explicit_base_selector(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_config_path = Path(temp_dir) / "workflow.json"
            runtime_config_path.write_text(
                json.dumps(_runtime_config_data()),
                encoding="utf-8",
            )

            config = load_runtime_config(runtime_config_path)

        self.assertEqual(config.head_ref, "refs/remotes/origin/main")
        self.assertEqual(config.base_ref, "refs/tags/v1.0.0")
        self.assertIsNone(config.release_marker)

    def test_load_runtime_config_accepts_marker_path_selector(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            marker_path = config_dir / "releaseMarker.json"
            marker_path.write_text(json.dumps({"marker": "[Release]"}), encoding="utf-8")
            data = _runtime_config_data()
            data.pop("base_ref")
            data["release_marker_config_path"] = marker_path.name
            runtime_config_path = config_dir / "workflow.json"
            runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

            config = load_runtime_config(runtime_config_path)

        self.assertEqual(config.head_ref, "refs/remotes/origin/main")
        self.assertIsNone(config.base_ref)
        self.assertEqual(config.release_marker, "[Release]")

    def test_load_runtime_config_validates_marker_file_content_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            marker_path = config_dir / "releaseMarker.json"
            marker_path.write_text("not json", encoding="utf-8")
            data = _runtime_config_data()
            data.pop("base_ref")
            data["release_marker_config_path"] = marker_path.name
            runtime_config_path = config_dir / "workflow.json"
            runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaises(ConfigurationError):
                load_runtime_config(runtime_config_path)

    def test_load_runtime_config_rejects_missing_or_blank_head_ref(self) -> None:
        invalid_head_refs = (
            ("missing", None, False),
            ("null", None, True),
            ("empty", "", True),
            ("blank", "   ", True),
        )
        for name, head_ref, include_field in invalid_head_refs:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                data = _runtime_config_data()
                if not include_field:
                    data.pop("head_ref")
                else:
                    data["head_ref"] = head_ref
                runtime_config_path = Path(temp_dir) / "workflow.json"
                runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

                with self.assertRaises(ConfigurationError):
                    load_runtime_config(runtime_config_path)

    def test_load_runtime_config_requires_exactly_one_usable_lower_selector(self) -> None:
        invalid_selectors = (
            ("neither", {}),
            (
                "both",
                {
                    "base_ref": "refs/tags/v1.0.0",
                    "release_marker_config_path": "releaseMarker.json",
                },
            ),
            ("null-base", {"base_ref": None}),
            ("empty-base", {"base_ref": ""}),
            ("blank-base", {"base_ref": "   "}),
            ("null-marker-path", {"release_marker_config_path": None}),
            ("empty-marker-path", {"release_marker_config_path": ""}),
            ("blank-marker-path", {"release_marker_config_path": "   "}),
        )
        for name, selectors in invalid_selectors:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                data = _runtime_config_data()
                data.pop("base_ref")
                data.update(selectors)
                runtime_config_path = Path(temp_dir) / "workflow.json"
                runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

                with self.assertRaises(ConfigurationError):
                    load_runtime_config(runtime_config_path)

    def test_load_runtime_config_defaults_repository_update_mode_to_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_config_path = Path(temp_dir) / "workflow.json"
            runtime_config_path.write_text(
                json.dumps(_runtime_config_data()),
                encoding="utf-8",
            )

            config = load_runtime_config(runtime_config_path)

        self.assertEqual(config.repository_update_mode, RepositoryUpdateMode.READ_ONLY)
        self.assertIsNone(config.refresh_remote)
        self.assertEqual(config.refresh_refspecs, ())

    def test_load_runtime_config_accepts_each_repository_update_mode(self) -> None:
        for mode in RepositoryUpdateMode:
            with self.subTest(mode=mode.value), tempfile.TemporaryDirectory() as temp_dir:
                data = _runtime_config_data()
                data["repository_update_mode"] = mode.value
                if mode is RepositoryUpdateMode.REFRESH_REMOTE_REFS:
                    data["refresh_remote"] = "origin"
                    data["refresh_refspecs"] = [
                        "refs/heads/main:refs/remotes/origin/main"
                    ]
                runtime_config_path = Path(temp_dir) / "workflow.json"
                runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

                config = load_runtime_config(runtime_config_path)

            self.assertEqual(config.repository_update_mode, mode)

    def test_load_runtime_config_rejects_invalid_repository_update_mode(self) -> None:
        for mode in ("unknown", "", "   ", None):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp_dir:
                data = _runtime_config_data()
                data["repository_update_mode"] = mode
                runtime_config_path = Path(temp_dir) / "workflow.json"
                runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

                with self.assertRaises(ConfigurationError):
                    load_runtime_config(runtime_config_path)

    def test_load_runtime_config_rejects_refresh_fields_outside_refresh_mode(self) -> None:
        for mode in (
            RepositoryUpdateMode.READ_ONLY,
            RepositoryUpdateMode.LEGACY_IN_PLACE_SYNC,
        ):
            for refresh_field, value in (
                ("refresh_remote", "origin"),
                (
                    "refresh_refspecs",
                    ["refs/heads/main:refs/remotes/origin/main"],
                ),
            ):
                with (
                    self.subTest(mode=mode.value, refresh_field=refresh_field),
                    tempfile.TemporaryDirectory() as temp_dir,
                ):
                    data = _runtime_config_data()
                    data["repository_update_mode"] = mode.value
                    data[refresh_field] = value
                    runtime_config_path = Path(temp_dir) / "workflow.json"
                    runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

                    with self.assertRaises(ConfigurationError):
                        load_runtime_config(runtime_config_path)

    def test_load_runtime_config_accepts_explicit_remote_tracking_refspecs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _runtime_config_data()
            data.update(
                {
                    "repository_update_mode": "refresh_remote_refs",
                    "refresh_remote": "origin",
                    "refresh_refspecs": [
                        "refs/heads/main:refs/remotes/origin/main",
                        "+refs/heads/release:refs/remotes/origin/release",
                    ],
                }
            )
            runtime_config_path = Path(temp_dir) / "workflow.json"
            runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

            config = load_runtime_config(runtime_config_path)

        self.assertEqual(config.refresh_remote, "origin")
        self.assertEqual(
            config.refresh_refspecs,
            (
                "refs/heads/main:refs/remotes/origin/main",
                "+refs/heads/release:refs/remotes/origin/release",
            ),
        )

    def test_load_runtime_config_rejects_invalid_refresh_configuration(self) -> None:
        invalid_refresh_values = (
            ("missing-remote", None, ["refs/heads/main:refs/remotes/origin/main"]),
            ("empty-remote", "", ["refs/heads/main:refs/remotes/origin/main"]),
            ("blank-remote", "   ", ["refs/heads/main:refs/remotes/origin/main"]),
            ("missing-refspecs", "origin", None),
            ("empty-refspecs", "origin", []),
            ("non-list-refspecs", "origin", "refs/heads/main"),
            ("non-string-refspec", "origin", [42]),
            ("blank-refspec", "origin", ["   "]),
            ("implicit-destination", "origin", ["refs/heads/main"]),
            ("empty-source", "origin", [":refs/remotes/origin/main"]),
            ("empty-destination", "origin", ["refs/heads/main:"]),
            ("local-destination", "origin", ["refs/heads/main:refs/heads/main"]),
            (
                "other-remote-destination",
                "origin",
                ["refs/heads/main:refs/remotes/upstream/main"],
            ),
        )
        for name, remote, refspecs in invalid_refresh_values:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                data = _runtime_config_data()
                data["repository_update_mode"] = "refresh_remote_refs"
                if remote is not None:
                    data["refresh_remote"] = remote
                if refspecs is not None:
                    data["refresh_refspecs"] = refspecs
                runtime_config_path = Path(temp_dir) / "workflow.json"
                runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

                with self.assertRaises(ConfigurationError):
                    load_runtime_config(runtime_config_path)

    def test_load_runtime_config_requires_pdf_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_config_path = Path(temp_dir) / "workflow.json"
            runtime_config_path.write_text(
                json.dumps(
                    {
                        "repository_path": "repo",
                        "user_config_path": "user.json",
                        "module_config_path": "module.json",
                        "release_marker_config_path": "releaseMarker.json",
                        "ai_config_path": "ai.json",
                        "temp_diff_dir": "tmp/diffs",
                        "output_path": "output/release_notes.txt",
                        "head_ref": "refs/remotes/origin/main",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigurationError):
                load_runtime_config(runtime_config_path)

    def test_load_runtime_config_accepts_absolute_and_home_relative_pdf_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            absolute_output = Path(temp_dir) / "absolute" / "release.pdf"
            common = {
                "repository_path": "repo",
                "user_config_path": "user.json",
                "module_config_path": "module.json",
                "release_marker_config_path": "releaseMarker.json",
                "ai_config_path": "ai.json",
                "temp_diff_dir": "tmp/diffs",
                "head_ref": "refs/remotes/origin/main",
            }
            absolute_config_path = config_dir / "absolute.json"
            absolute_config_path.write_text(
                json.dumps({**common, "output_path": str(absolute_output)}),
                encoding="utf-8",
            )
            home_config_path = config_dir / "home.json"
            home_config_path.write_text(
                json.dumps({**common, "output_path": "~/release-notes/release.pdf"}),
                encoding="utf-8",
            )

            absolute_config = load_runtime_config(absolute_config_path)
            home_config = load_runtime_config(home_config_path)

        self.assertEqual(absolute_config.output_path, absolute_output.resolve())
        self.assertEqual(
            home_config.output_path,
            (Path.home() / "release-notes" / "release.pdf").resolve(),
        )

    def test_load_user_config_accepts_explicit_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "user.json"
            config_path.write_text(
                json.dumps({"approved_author_emails": ["dev@example.com"]}),
                encoding="utf-8",
            )

            config = load_user_config(config_path)

        self.assertEqual(config.approved_author_emails, ("dev@example.com",))

    def test_missing_configuration_file_raises_error(self) -> None:
        with self.assertRaises(ConfigurationError):
            load_user_config(Path("missing-user-config.json"))

    def test_invalid_configuration_file_raises_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "user.json"
            config_path.write_text("not json", encoding="utf-8")

            with self.assertRaises(ConfigurationError):
                load_user_config(config_path)

    def test_unusable_users_configuration_raises_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "user.json"
            config_path.write_text(
                json.dumps({"approved_author_emails": [1]}),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigurationError):
                load_user_config(config_path)

    def test_load_ai_config_defaults_missing_backend_to_openai_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _load_ai_config_from_data(temp_dir, _openai_ai_config_data())

        self.assertIsInstance(config, OpenAICompatibleAISettings)
        self.assertEqual(config.backend, AIBackend.OPENAI_COMPATIBLE)
        self.assertEqual(config.api_url, "https://api.example.test/v1/chat/completions")
        self.assertEqual(config.model, "summary-model")
        self.assertEqual(config.api_key_env_var, "CHANGE_LOG_SUMMARY_AI_API_KEY")
        self.assertEqual(config.prompt, "Summarize this diff.")
        self.assertEqual(config.max_diff_characters_per_request, 12000)

    def test_load_ai_config_accepts_explicit_openai_compatible_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _openai_ai_config_data()
            data["backend"] = "openai_compatible"

            config = _load_ai_config_from_data(temp_dir, data)

        self.assertIsInstance(config, OpenAICompatibleAISettings)
        self.assertEqual(config.backend, AIBackend.OPENAI_COMPATIBLE)
        self.assertEqual(config.api_url, "https://api.example.test/v1/chat/completions")
        self.assertEqual(config.model, "summary-model")
        self.assertEqual(config.api_key_env_var, "CHANGE_LOG_SUMMARY_AI_API_KEY")
        self.assertEqual(config.prompt, "Summarize this diff.")
        self.assertEqual(config.max_diff_characters_per_request, 12000)

    def test_openai_compatible_backend_requires_current_fields(self) -> None:
        required_fields = ("api_url", "model", "api_key_env_var", "prompt")
        for backend in (None, "openai_compatible"):
            for field_name in required_fields:
                for invalid_value in (None, "", 42):
                    with (
                        self.subTest(backend=backend, field=field_name, value=invalid_value),
                        tempfile.TemporaryDirectory() as temp_dir,
                    ):
                        data = _openai_ai_config_data()
                        if backend is not None:
                            data["backend"] = backend
                        if invalid_value is None:
                            data.pop(field_name)
                        else:
                            data[field_name] = invalid_value

                        with self.assertRaises(ConfigurationError):
                            _load_ai_config_from_data(temp_dir, data)

    def test_load_ai_config_accepts_keyless_claude_code_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _load_ai_config_from_data(temp_dir, _claude_code_ai_config_data())

        self.assertIsInstance(config, ClaudeCodeAISettings)
        self.assertEqual(config.backend, AIBackend.CLAUDE_CODE)
        self.assertEqual(config.model, "claude-sonnet-5")
        self.assertEqual(config.prompt, "Summarize this diff.")
        self.assertEqual(config.max_diff_characters_per_request, 12000)
        self.assertFalse(hasattr(config, "api_url"))
        self.assertFalse(hasattr(config, "api_key_env_var"))
        self.assertFalse(hasattr(config, "api_key"))

    def test_claude_code_backend_rejects_missing_or_invalid_required_fields(self) -> None:
        invalid_cases = (
            ("missing-model", "model", None),
            ("empty-model", "model", ""),
            ("non-string-model", "model", 42),
            ("missing-prompt", "prompt", None),
            ("empty-prompt", "prompt", ""),
            ("non-string-prompt", "prompt", ["Summarize."]),
            ("missing-limit", "max_diff_characters_per_request", None),
            ("boolean-limit", "max_diff_characters_per_request", True),
            ("zero-limit", "max_diff_characters_per_request", 0),
            ("negative-limit", "max_diff_characters_per_request", -1),
            ("float-limit", "max_diff_characters_per_request", 1.5),
            ("string-limit", "max_diff_characters_per_request", "1000"),
        )
        for name, field_name, invalid_value in invalid_cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                data = _claude_code_ai_config_data()
                if invalid_value is None:
                    data.pop(field_name)
                else:
                    data[field_name] = invalid_value

                with self.assertRaises(ConfigurationError):
                    _load_ai_config_from_data(temp_dir, data)

    def test_load_ai_config_rejects_unsupported_backends(self) -> None:
        for backend in ("anthropic", "openai", "claude", "", "   ", 7, True, None, []):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as temp_dir:
                data = _openai_ai_config_data()
                data["backend"] = backend

                with self.assertRaises(ConfigurationError):
                    _load_ai_config_from_data(temp_dir, data)

    def test_load_ai_config_rejects_inline_secret_for_every_backend(self) -> None:
        backend_data = (
            ("legacy-no-backend", _openai_ai_config_data()),
            (
                "openai_compatible",
                {**_openai_ai_config_data(), "backend": "openai_compatible"},
            ),
            ("claude_code", _claude_code_ai_config_data()),
        )
        for name, data in backend_data:
            with self.subTest(backend=name), tempfile.TemporaryDirectory() as temp_dir:
                data["api_key"] = "inline-secret"

                with self.assertRaises(ConfigurationError):
                    _load_ai_config_from_data(temp_dir, data)

    def test_claude_code_backend_rejects_openai_api_fields(self) -> None:
        api_fields = (
            ("api_url", "https://api.example.test/v1/chat/completions"),
            ("api_key_env_var", "CHANGE_LOG_SUMMARY_AI_API_KEY"),
        )
        for field_name, value in api_fields:
            with self.subTest(field=field_name), tempfile.TemporaryDirectory() as temp_dir:
                data = _claude_code_ai_config_data()
                data[field_name] = value

                with self.assertRaises(ConfigurationError):
                    _load_ai_config_from_data(temp_dir, data)

    def test_backend_configurations_are_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            openai_config = _load_ai_config_from_data(temp_dir, _openai_ai_config_data())
        with tempfile.TemporaryDirectory() as temp_dir:
            claude_config = _load_ai_config_from_data(
                temp_dir, _claude_code_ai_config_data()
            )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            openai_config.model = "other-model"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            claude_config.model = "other-model"

    def test_unusable_ai_configuration_raises_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.json"
            config_path.write_text(
                json.dumps({"api_url": "https://api.example.test", "model": ""}),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigurationError):
                load_ai_config(config_path)


if __name__ == "__main__":
    unittest.main()

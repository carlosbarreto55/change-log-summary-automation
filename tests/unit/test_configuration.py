import json
import tempfile
import unittest
from pathlib import Path

from release_notes_generator.configuration import (
    ConfigurationError,
    ModuleDefinition,
    RepositoryUpdateMode,
    load_ai_config,
    load_module_config,
    load_release_marker_config,
    load_runtime_config,
    load_user_config,
)


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
        self.assertEqual(config.user_config_path, (config_dir / "user.json").resolve())
        self.assertEqual(config.module_config_path, (config_dir / "module.json").resolve())
        self.assertEqual(
            config.release_marker_config_path,
            (config_dir / "releaseMarker.json").resolve(),
        )
        self.assertEqual(config.ai_config_path, (config_dir / "ai.json").resolve())
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
        self.assertIsNone(config.release_marker_config_path)

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
        self.assertEqual(config.release_marker_config_path, marker_path.resolve())

    def test_load_runtime_config_defers_marker_file_content_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            marker_path = config_dir / "releaseMarker.json"
            marker_path.write_text("not json", encoding="utf-8")
            data = _runtime_config_data()
            data.pop("base_ref")
            data["release_marker_config_path"] = marker_path.name
            runtime_config_path = config_dir / "workflow.json"
            runtime_config_path.write_text(json.dumps(data), encoding="utf-8")

            config = load_runtime_config(runtime_config_path)

            with self.assertRaises(ConfigurationError):
                load_release_marker_config(config.release_marker_config_path)

        self.assertEqual(config.release_marker_config_path, marker_path.resolve())

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

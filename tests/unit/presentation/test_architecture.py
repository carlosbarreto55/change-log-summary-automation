import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = PROJECT_ROOT / "release_notes_generator"


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    return tuple(imports)


class ProjectStructureTests(unittest.TestCase):
    def test_expected_layer_directories_and_entrypoint_exist(self) -> None:
        for directory in ("domain", "services", "infrastructure", "presentation"):
            self.assertTrue((PACKAGE_ROOT / directory).is_dir())
        self.assertTrue((PACKAGE_ROOT / "__main__.py").is_file())

    def test_replaced_flat_modules_are_removed(self) -> None:
        replaced = (
            "claude_code.py",
            "cli.py",
            "commits.py",
            "composition.py",
            "configuration.py",
            "diffs.py",
            "paths.py",
            "pdf_export.py",
            "repository_safety.py",
            "summarization.py",
            "workflow.py",
        )
        self.assertFalse(any((PACKAGE_ROOT / name).exists() for name in replaced))

    def test_domain_has_no_project_or_third_party_imports(self) -> None:
        allowed = {"dataclasses", "datetime", "enum", "pathlib", "typing", "__future__"}
        for path in (PACKAGE_ROOT / "domain").glob("*.py"):
            with self.subTest(path=path.name):
                imports = _imports(path)
                self.assertTrue(
                    all(name.split(".", 1)[0] in allowed for name in imports), imports
                )

    def test_services_never_import_infrastructure_or_presentation(self) -> None:
        forbidden = (
            "release_notes_generator.infrastructure",
            "release_notes_generator.presentation",
        )
        for path in (PACKAGE_ROOT / "services").glob("*.py"):
            with self.subTest(path=path.name):
                imports = _imports(path)
                self.assertFalse(
                    any(name.startswith(forbidden) for name in imports), imports
                )

    def test_infrastructure_never_imports_presentation(self) -> None:
        for path in (PACKAGE_ROOT / "infrastructure").glob("*.py"):
            with self.subTest(path=path.name):
                imports = _imports(path)
                self.assertFalse(
                    any(
                        name.startswith("release_notes_generator.presentation")
                        for name in imports
                    ),
                    imports,
                )

    def test_package_initializers_are_side_effect_free(self) -> None:
        for path in (PACKAGE_ROOT / "__init__.py", *PACKAGE_ROOT.glob("*/__init__.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            executable = [
                node
                for node in tree.body
                if not (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                )
            ]
            with self.subTest(path=path.relative_to(PACKAGE_ROOT)):
                self.assertEqual(executable, [])


if __name__ == "__main__":
    unittest.main()

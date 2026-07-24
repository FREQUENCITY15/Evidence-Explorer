from pathlib import Path
import tempfile
import unittest

from project_mentor.scanner import scan_project


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class ScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_scan_extracts_facts_and_orders_dependencies(self) -> None:
        write(
            self.root / "utils.py",
        '''"""Small helpers."""

def greet(name: str) -> str:
    """Create a greeting."""
    return f"Hello {name}"
''',
        )
        write(
            self.root / "main.py",
        '''import json
import fastapi
from utils import greet

class Greeter:
    def run(self) -> str:
        return greet("Thomas")

def main() -> None:
    print(Greeter().run())

if __name__ == "__main__":
    main()
''',
        )
        write(self.root / "plugin.py", "def activate():\n    return True\n")
        write(
            self.root / "tests" / "test_manual.py",
            '''if __name__ == "__main__":
    print("manual test runner")
''',
        )

        result = scan_project(self.root)

        self.assertEqual(result.summary["python_files"], 4)
        self.assertEqual(result.summary["functions"], 4)
        self.assertEqual(result.summary["classes"], 1)
        self.assertGreater(result.summary["calls"], 0)
        self.assertEqual(result.summary["possibly_unused"], 1)
        self.assertEqual(result.entry_points[0].path, "main.py")
        self.assertEqual(result.entry_points[0].confidence, "high")
        self.assertGreaterEqual(result.entry_points[0].score, 100)
        learning_paths = [step.path for step in result.learning_order]
        self.assertLess(learning_paths.index("utils.py"), learning_paths.index("main.py"))

        main_file = next(item for item in result.files if item.path == "main.py")
        self.assertTrue(main_file.has_main_guard)
        self.assertEqual([item.name for item in main_file.classes], ["Greeter"])
        self.assertEqual(
            [item.name for item in main_file.functions], ["Greeter.run", "main"]
        )
        classifications = {
            item.names[0]: item.classification for item in main_file.imports
        }
        self.assertEqual(classifications["json"], "standard_library")
        self.assertEqual(classifications["fastapi"], "external")
        self.assertEqual(classifications["greet"], "internal")
        self.assertIn("fastapi", result.external_dependencies)
        self.assertEqual(
            [(edge.source_path, edge.target_path) for edge in result.import_edges],
            [("main.py", "utils.py")],
        )
        self.assertTrue(
            any(call.caller == "Greeter.run" and call.target == "greet" for call in main_file.calls)
        )
        self.assertEqual([item.path for item in result.unused_files], ["plugin.py"])

    def test_scan_reports_syntax_errors_without_stopping(self) -> None:
        write(self.root / "good.py", "value = 1\n")
        write(self.root / "broken.py", "def broken(:\n")

        result = scan_project(self.root)

        self.assertEqual(result.summary["python_files"], 2)
        self.assertEqual(result.summary["parse_errors"], 1)
        broken = next(item for item in result.files if item.path == "broken.py")
        self.assertIsNotNone(broken.parse_error)
        self.assertIn("Syntax error", broken.parse_error or "")

    def test_scan_ignores_virtual_environments(self) -> None:
        write(self.root / "app.py", "print('hello')\n")
        write(self.root / ".venv" / "library.py", "print('ignore me')\n")
        write(self.root / "__pycache__" / "cached.py", "print('ignore me')\n")

        result = scan_project(self.root)

        self.assertEqual([item.path for item in result.files], ["app.py"])

    def test_scan_resolves_relative_package_imports(self) -> None:
        write(self.root / "package" / "__init__.py", "")
        write(self.root / "package" / "helpers.py", "def help_me():\n    return 1\n")
        write(
            self.root / "package" / "service.py",
            "from .helpers import help_me\n\ndef serve():\n    return help_me()\n",
        )

        result = scan_project(self.root)

        service = next(
            item for item in result.files if item.path == "package/service.py"
        )
        self.assertEqual(service.imports[0].classification, "internal")
        self.assertEqual(service.imports[0].resolved_modules, ["package.helpers"])
        self.assertIn(
            ("package/service.py", "package/helpers.py"),
            [(edge.source_path, edge.target_path) for edge in result.import_edges],
        )

    def test_scan_rejects_missing_folder(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not exist"):
            scan_project(self.root / "missing")


if __name__ == "__main__":
    unittest.main()

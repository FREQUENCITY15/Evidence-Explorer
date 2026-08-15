import json
from pathlib import Path
import tempfile
import unittest

from project_mentor.scanner import scan_project


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class SemanticEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def relationship(self, result, expression: str):
        matches = [
            item
            for item in result.call_relationships
            if item.target_expression == expression
        ]
        self.assertEqual(len(matches), 1, expression)
        return matches[0]

    def test_stable_symbol_ids_kinds_signatures_and_docstrings(self) -> None:
        write(
            self.root / "service.py",
            '''class Service:
    """Provide work."""

    async def fetch(self, item: str) -> str:
        """Fetch one item.

        More details follow.
        """
        return item

def helper(value: int = 1) -> int:
    """Return the value."""
    return value
''',
        )

        first = scan_project(self.root)
        second = scan_project(self.root)
        symbols = {item.symbol_id: item for item in first.symbols}

        self.assertEqual(
            sorted(symbols),
            ["service:Service", "service:Service.fetch", "service:helper"],
        )
        self.assertEqual(symbols["service:Service"].kind, "class")
        self.assertEqual(symbols["service:Service.fetch"].kind, "async_method")
        self.assertEqual(
            symbols["service:Service.fetch"].parent_symbol_id,
            "service:Service",
        )
        self.assertEqual(
            symbols["service:Service.fetch"].signature,
            "(self, item: str) -> str",
        )
        self.assertEqual(
            symbols["service:Service.fetch"].docstring_first_line,
            "Fetch one item.",
        )
        self.assertEqual(
            [item.symbol_id for item in first.symbols],
            [item.symbol_id for item in second.symbols],
        )

    def test_resolves_same_file_direct_call(self) -> None:
        write(
            self.root / "app.py",
            "def helper():\n    return 1\n\ndef run():\n    return helper()\n",
        )

        result = scan_project(self.root)
        call = self.relationship(result, "helper")

        self.assertEqual(call.caller_symbol_id, "app:run")
        self.assertEqual(call.resolved_target_symbol_id, "app:helper")
        self.assertEqual(call.confidence, "high")
        self.assertIn("uniquely matches", call.reason)

    def test_resolves_imported_function_alias(self) -> None:
        write(self.root / "helpers.py", "def greet():\n    return 'hello'\n")
        write(
            self.root / "main.py",
            "from helpers import greet as welcome\n\ndef run():\n    return welcome()\n",
        )

        result = scan_project(self.root)
        call = self.relationship(result, "welcome")

        self.assertEqual(call.resolved_target_symbol_id, "helpers:greet")
        self.assertEqual(call.confidence, "high")
        self.assertIn("Import binding", call.reason)

    def test_resolves_module_qualified_call(self) -> None:
        write(self.root / "scanner.py", "def scan_project():\n    return {}\n")
        write(
            self.root / "main.py",
            "import scanner as tools\n\ndef run():\n    return tools.scan_project()\n",
        )

        result = scan_project(self.root)
        call = self.relationship(result, "tools.scan_project")

        self.assertEqual(call.resolved_target_symbol_id, "scanner:scan_project")
        self.assertEqual(call.confidence, "high")
        self.assertIn("module import", call.reason)

    def test_constructors_and_inferred_methods_are_cautious(self) -> None:
        write(
            self.root / "worker.py",
            '''class Worker:
    def start(self):
        return True

def run():
    worker = Worker()
    return worker.start()
''',
        )

        result = scan_project(self.root)
        constructor = self.relationship(result, "Worker")
        method = self.relationship(result, "worker.start")

        self.assertEqual(constructor.resolved_target_symbol_id, "worker:Worker")
        self.assertEqual(constructor.confidence, "high")
        self.assertEqual(method.resolved_target_symbol_id, "worker:Worker.start")
        self.assertEqual(method.confidence, "medium")
        self.assertIn("runtime", method.reason.lower())

    def test_dynamic_call_stays_unresolved_with_reason(self) -> None:
        write(
            self.root / "dynamic.py",
            '''def invoke(obj, name):
    return getattr(obj, name)()

def conditional(flag):
    if flag:
        def maybe():
            return 1
    return maybe()
''',
        )

        result = scan_project(self.root)
        call = self.relationship(result, "getattr(obj, name)")

        self.assertIsNone(call.resolved_target_symbol_id)
        self.assertEqual(call.confidence, "unresolved")
        self.assertTrue(call.reason)
        self.assertIn("dynamically", call.reason)
        conditional = self.relationship(result, "maybe")
        self.assertIsNone(conditional.resolved_target_symbol_id)
        self.assertEqual(conditional.confidence, "unresolved")
        self.assertIn("conditional", conditional.reason)

    def test_relationships_support_caller_and_callee_traces(self) -> None:
        write(
            self.root / "chain.py",
            '''def leaf():
    return 1

def middle():
    return leaf()

def top():
    return middle()
''',
        )

        result = scan_project(self.root)
        outgoing = [
            item
            for item in result.call_relationships
            if item.caller_symbol_id == "chain:middle"
        ]
        incoming = [
            item
            for item in result.call_relationships
            if item.resolved_target_symbol_id == "chain:leaf"
        ]

        self.assertEqual([item.resolved_target_symbol_id for item in outgoing], ["chain:leaf"])
        self.assertEqual([item.caller_symbol_id for item in incoming], ["chain:middle"])
        self.assertTrue(all(item.reason for item in result.call_relationships))

    def test_report_output_is_deterministic_and_grouped(self) -> None:
        write(self.root / "b.py", "def second():\n    return 2\n")
        write(self.root / "a.py", "from b import second\n\ndef first():\n    return second()\n")

        first = scan_project(self.root).to_dict()
        second = scan_project(self.root).to_dict()

        self.assertEqual(
            json.dumps(first, indent=2),
            json.dumps(second, indent=2),
        )
        self.assertEqual(first["schema_version"], "1.3.0")
        self.assertEqual(first["generator"]["version"], "0.8.0")
        self.assertIn("files", first["observed_facts"])
        self.assertIn("symbols", first["observed_facts"])
        self.assertIn("function_evidence", first["observed_facts"])
        self.assertIn("call_relationships", first["inferred_relationships"])
        self.assertIn("data_flows", first["inferred_relationships"])
        self.assertIn("error_propagation", first["inferred_relationships"])
        self.assertGreaterEqual(len(first["warnings"]), 3)

    def test_learning_order_deprioritises_markers_and_tests(self) -> None:
        write(self.root / "package" / "__init__.py", "")
        write(self.root / "core.py", "def value():\n    return 1\n")
        write(
            self.root / "app.py",
            "from core import value\n\ndef main():\n    return value()\n",
        )
        write(
            self.root / "tests" / "test_app.py",
            "from app import main\n\ndef test_main():\n    assert main() == 1\n",
        )

        result = scan_project(self.root)
        paths = [item.path for item in result.learning_order]

        self.assertLess(paths.index("core.py"), paths.index("app.py"))
        self.assertLess(paths.index("app.py"), paths.index("tests/test_app.py"))
        self.assertLess(paths.index("tests/test_app.py"), paths.index("package/__init__.py"))
        marker = next(
            item for item in result.files if item.path == "package/__init__.py"
        )
        self.assertTrue(marker.is_empty_package_marker)
        marker_step = next(
            item for item in result.learning_order if item.path == marker.path
        )
        self.assertIn("little code", marker_step.reason)


if __name__ == "__main__":
    unittest.main()

"""Contract tests for the read-only canonical evidence record viewer."""

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIEWER_PATH = PROJECT_ROOT / "project_mentor" / "static" / "record_view.html"


class RecordViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = VIEWER_PATH.read_text(encoding="utf-8")

    def test_canonical_tool_and_execution_fields_are_mapped(self) -> None:
        self.assertIn(
            '["parsedToolName", "selectedTool", "selectedToolName", "toolName", "firstToolCall.name"]',
            self.source,
        )
        self.assertIn(
            '["boundedToolResult", "result", "status", "details"]',
            self.source,
        )
        self.assertIn(
            'card("Execution successful", valueAt(execution, ["successful"], null))',
            self.source,
        )

    def test_invalid_test_cannot_match_the_valid_pass_token(self) -> None:
        self.assertIn('"invalid_test"', self.source)
        self.assertIn("passVerdicts.indexOf(normalized)", self.source)
        self.assertIn("failVerdicts.indexOf(normalized)", self.source)
        self.assertNotIn("/pass|valid|success|compliant|accepted/", self.source)

    def test_null_false_and_zero_are_not_treated_as_missing(self) -> None:
        self.assertIn(
            'if (current !== undefined && current !== "") return current;',
            self.source,
        )
        self.assertIn('if (value === null) return "null";', self.source)
        self.assertIn(
            'typeof value === "number" || typeof value === "boolean"',
            self.source,
        )
        self.assertNotIn(
            'value === null || value === undefined || value === ""',
            self.source,
        )

    def test_malicious_record_content_uses_text_only_dom_sinks(self) -> None:
        malicious = '<img src=x onerror="window.__viewerXss = true">'
        self.assertTrue(malicious.startswith("<img"))
        self.assertIn("node.textContent = String(text);", self.source)
        self.assertNotIn("innerHTML", self.source)
        self.assertNotIn("outerHTML", self.source)
        self.assertNotIn("insertAdjacentHTML", self.source)
        self.assertNotIn("document.write", self.source)
        self.assertIn(
            'element("div", "value", display(value))',
            self.source,
        )
        self.assertIn(
            'element("pre", "", display(value))',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()

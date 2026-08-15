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

    def test_viewer_requests_validation_without_changing_the_default_api(self) -> None:
        self.assertIn("?include_validation=true", self.source)
        self.assertIn("payload.record", self.source)
        self.assertIn("payload.validation", self.source)
        self.assertIn('section("Evidence quality")', self.source)
        self.assertIn("validation.completenessGaps", self.source)
        self.assertIn("validation.warnings", self.source)

    def test_raw_evidence_has_line_and_pointer_targets(self) -> None:
        self.assertIn('var list = element("ol", "raw-evidence")', self.source)
        self.assertIn("item.id = pointerId(line.pointer)", self.source)
        self.assertIn("item.dataset.pointer = line.pointer", self.source)
        self.assertIn('buildRawLines(record, "#", 0, "", false, lines)', self.source)
        self.assertIn('replace(/~/g, "~0").replace(/\\//g, "~1")', self.source)

    def test_verdict_citations_navigate_to_safe_raw_evidence_nodes(self) -> None:
        self.assertIn("normalized.evidenceRefs", self.source)
        self.assertIn('link.href = "#" + pointerId(reference)', self.source)
        self.assertIn("document.getElementById(pointerId(reference))", self.source)
        self.assertIn("target.scrollIntoView", self.source)
        self.assertIn('element("span", "", normalized.notes)', self.source)

    def test_governance_result_renders_with_finding_citations(self) -> None:
        self.assertIn('section("Govern")', self.source)
        self.assertIn('"govern-banner govern-" + governance.status', self.source)
        self.assertIn("governance.scoreable", self.source)
        self.assertIn("governance.findings", self.source)
        self.assertIn("finding.message", self.source)
        self.assertIn("appendCitations(findingCard, finding.evidenceRefs)", self.source)

    def test_audit_exports_are_explicitly_user_triggered(self) -> None:
        self.assertIn('id="export-json-button"', self.source)
        self.assertIn('id="export-markdown-button"', self.source)
        self.assertIn("function downloadAudit(exportFormat)", self.source)
        self.assertIn(
            'exportJsonButton.addEventListener("click", function () { downloadAudit("json"); })',
            self.source,
        )
        self.assertIn(
            'exportMarkdownButton.addEventListener("click", function () { downloadAudit("markdown"); })',
            self.source,
        )
        self.assertIn("/audit?export_format=", self.source)
        self.assertIn("link.download = filename +", self.source)


if __name__ == "__main__":
    unittest.main()

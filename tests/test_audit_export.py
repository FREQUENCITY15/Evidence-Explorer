import copy
import json
from pathlib import Path
import unittest

from project_mentor.audit_export import (
    AUDIT_EXPORT_VERSION,
    build_audit_payload,
    render_audit_json,
    render_audit_markdown,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "evidence_loader"
    / "structured-record.json"
)


def structured_record():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class AuditExportTests(unittest.TestCase):
    def test_json_export_is_deterministic_lossless_and_versioned(self) -> None:
        record = structured_record()

        first = render_audit_json(record)
        second = render_audit_json(record)
        payload = json.loads(first)

        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertEqual(payload["auditExportVersion"], AUDIT_EXPORT_VERSION)
        self.assertEqual(payload["record"], record)
        self.assertEqual(payload["validation"]["governance"]["status"], "green")
        self.assertEqual(
            payload["source"]["checksumVerification"],
            "not_performed",
        )
        self.assertNotIn("generatedAt", first)
        self.assertNotIn("exportedAt", first)

    def test_building_an_export_does_not_mutate_the_record(self) -> None:
        record = structured_record()
        before = copy.deepcopy(record)

        build_audit_payload(record)

        self.assertEqual(record, before)

    def test_markdown_export_uses_safe_literal_values_and_adaptive_fence(self) -> None:
        record = structured_record()
        record["verdicts"]["selection"]["notes"] = (
            "```\n# injected heading\n<img src=x onerror=alert(1)>"
        )

        markdown = render_audit_markdown(record)

        self.assertIn("# Evidence Explorer audit", markdown)
        self.assertIn("## Govern", markdown)
        self.assertIn("## Canonical record", markdown)
        self.assertIn("\n````json\n", markdown)
        self.assertIn("\n````\n", markdown)
        self.assertIn('"notes": "```\\n# injected heading', markdown)
        self.assertIn("Checksum verification is", markdown)
        self.assertIn("not performed", markdown)

    def test_markdown_and_json_share_the_same_deterministic_governance(self) -> None:
        record = structured_record()
        json_payload = json.loads(render_audit_json(record))
        markdown = render_audit_markdown(record)

        governance = json_payload["validation"]["governance"]
        self.assertIn(f"` {governance['status']} `", markdown)
        self.assertIn(f"` {governance['findings'][0]['code']} `", markdown)


if __name__ == "__main__":
    unittest.main()

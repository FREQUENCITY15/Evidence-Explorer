import json
from pathlib import Path
import tempfile
import unittest

from project_mentor.debug_service import (
    DEBUG_SCHEMA_VERSION,
    DebugInvestigationError,
    DebugInvestigationService,
)
from project_mentor.scanner import scan_project


class DebugInvestigationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "helpers.py").write_text(
            "def normalize(value: str) -> str:\n    return value.strip()\n",
            encoding="utf-8",
        )
        (self.root / "app.py").write_text(
            "from helpers import normalize\n\n"
            "def process(value: str, store: dict) -> str:\n"
            "    cleaned = normalize(value)\n"
            "    store['last'] = cleaned\n"
            "    if not cleaned:\n"
            "        raise ValueError('empty')\n"
            "    return cleaned\n",
            encoding="utf-8",
        )
        self.analysis = scan_project(self.root)
        self.service = DebugInvestigationService()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_unchanged_inputs_produce_byte_stable_investigation(self) -> None:
        first = self.service.build(
            self.analysis, "app:process", "Blank input crashes"
        ).investigation.to_dict()
        second = self.service.build(
            self.analysis, "app:process", "Blank input crashes"
        ).investigation.to_dict()

        first_bytes = json.dumps(
            first, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        second_bytes = json.dumps(
            second, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

        self.assertEqual(first_bytes, second_bytes)
        self.assertTrue(first["investigation_id"].startswith("DEBUG-"))
        self.assertEqual(first["debug_schema_version"], DEBUG_SCHEMA_VERSION)
        self.assertNotIn("generated_at", first)

    def test_investigation_ranks_competing_unverified_hypotheses(self) -> None:
        investigation = self.service.build(
            self.analysis, "app:process", "Blank input crashes"
        ).investigation

        self.assertGreaterEqual(len(investigation.hypotheses), 2)
        self.assertLessEqual(len(investigation.hypotheses), 4)
        self.assertEqual(
            [item.rank for item in investigation.hypotheses],
            list(range(1, len(investigation.hypotheses) + 1)),
        )
        self.assertTrue(all(item.status == "unverified" for item in investigation.hypotheses))
        self.assertEqual(investigation.conclusion_status, "root_cause_not_established")
        self.assertEqual(len(investigation.diagnostic_steps), len(investigation.hypotheses))
        self.assertTrue(
            all("no command" in item.safety for item in investigation.diagnostic_steps)
        )

    def test_evidence_is_bounded_and_all_citations_are_allow_listed(self) -> None:
        bundle = self.service.build(
            self.analysis, "app:process", "Blank input crashes"
        )
        investigation = bundle.investigation
        allowed = {item.evidence_id for item in bundle.evidence_items}
        cited = {
            reference.evidence_id
            for item in (*investigation.hypotheses, *investigation.diagnostic_steps)
            for reference in item.references
        }

        self.assertLessEqual(investigation.evidence_included_count, 12)
        self.assertEqual(
            investigation.evidence_included_count, len(investigation.evidence_references)
        )
        self.assertTrue(cited)
        self.assertTrue(cited.issubset(allowed))
        self.assertTrue(investigation.evidence_groups)

    def test_building_does_not_execute_or_modify_scanned_source(self) -> None:
        marker = self.root / "executed.txt"
        (self.root / "danger.py").write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed')\n"
            "def inspect_only(value):\n    return value\n",
            encoding="utf-8",
        )
        analysis = scan_project(self.root)
        before = (self.root / "danger.py").read_bytes()
        investigation = self.service.build(
            analysis, "danger:inspect_only", "Unexpected output"
        ).investigation

        self.assertFalse(marker.exists())
        self.assertEqual((self.root / "danger.py").read_bytes(), before)
        self.assertIn("did not run code", investigation.boundary_notice)
        self.assertIn("contact Ollama", investigation.boundary_notice)

    def test_missing_failure_and_unsupported_symbols_fail_clearly(self) -> None:
        with self.assertRaises(DebugInvestigationError) as missing_failure:
            self.service.build(self.analysis, "app:process", "   ")
        with self.assertRaises(DebugInvestigationError) as missing_symbol:
            self.service.build(self.analysis, "app:missing", "Failure")

        self.assertEqual(missing_failure.exception.code, "missing_failure_statement")
        self.assertEqual(missing_symbol.exception.code, "symbol_not_found")


if __name__ == "__main__":
    unittest.main()

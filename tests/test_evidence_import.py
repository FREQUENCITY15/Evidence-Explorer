"""Tests for validation-first evidence record imports."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from project_mentor import evidence_import
from project_mentor.evidence_import import (
    EvidenceImportConflict,
    import_evidence_record,
)
from project_mentor.evidence_loader import load_evidence_record
from project_mentor.main import app


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "evidence_loader"


def structured_record() -> dict:
    return json.loads(
        (FIXTURES_DIR / "structured-record.json").read_text(encoding="utf-8")
    )


class EvidenceImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.records_dir = Path(self.temporary_directory.name) / "records"
        self.records_dir.mkdir()
        self.environment = patch.dict(
            os.environ,
            {"EVIDENCE_RECORDS_DIR": str(self.records_dir)},
        )
        self.environment.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_service_validates_and_preserves_the_submitted_record(self) -> None:
        record = structured_record()
        before = copy.deepcopy(record)

        result = import_evidence_record(record)

        self.assertEqual(result.record_id, "TEST-STRUCTURED-001")
        self.assertEqual(result.validation["governance"]["status"], "green")
        self.assertEqual(record, before)
        self.assertEqual(load_evidence_record(result.record_id), before)

    def test_api_imports_then_exposes_the_record_and_validation(self) -> None:
        record = structured_record()

        response = self.client.post("/api/evidence/import", json={"record": record})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["recordId"], record["attemptId"])
        self.assertTrue(response.json()["validation"]["isComplete"])
        loaded = self.client.get(
            f"/api/evidence/{record['attemptId']}?include_validation=true"
        )
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.json()["record"], record)

    def test_existing_record_is_never_overwritten(self) -> None:
        record = structured_record()
        import_evidence_record(record)
        changed = copy.deepcopy(record)
        changed["overallOutcome"] = "fail"

        response = self.client.post("/api/evidence/import", json={"record": changed})

        self.assertEqual(response.status_code, 409)
        self.assertIn("never overwrite", response.json()["detail"])
        self.assertEqual(load_evidence_record(record["attemptId"]), record)
        with self.assertRaises(EvidenceImportConflict):
            import_evidence_record(changed)

    def test_invalid_schema_or_identifier_is_rejected_before_persistence(self) -> None:
        wrong_version = structured_record()
        wrong_version["schemaVersion"] = "2.0.0"
        unsafe_identifier = structured_record()
        unsafe_identifier["attemptId"] = "../outside"

        version_response = self.client.post(
            "/api/evidence/import", json={"record": wrong_version}
        )
        identifier_response = self.client.post(
            "/api/evidence/import", json={"record": unsafe_identifier}
        )

        self.assertEqual(version_response.status_code, 400)
        self.assertIn("schemaVersion", version_response.json()["detail"])
        self.assertEqual(identifier_response.status_code, 400)
        self.assertIn("attemptId", identifier_response.json()["detail"])
        self.assertEqual(list(self.records_dir.iterdir()), [])

    def test_incomplete_but_well_formed_evidence_remains_importable(self) -> None:
        record = structured_record()
        del record["task"]["exactPrompt"]

        response = self.client.post("/api/evidence/import", json={"record": record})

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["validation"]["isComplete"])
        self.assertEqual(
            response.json()["validation"]["governance"]["status"],
            "flagged",
        )

    def test_oversized_and_non_object_requests_are_rejected(self) -> None:
        record = structured_record()
        record["modelInteraction"]["finalAnswer"] = "x" * 2_000

        with patch.object(evidence_import, "MAX_RECORD_BYTES", 512):
            oversized_response = self.client.post(
                "/api/evidence/import", json={"record": record}
            )
        non_object_response = self.client.post(
            "/api/evidence/import", json={"record": []}
        )

        self.assertEqual(oversized_response.status_code, 400)
        self.assertIn("byte limit", oversized_response.json()["detail"])
        self.assertEqual(non_object_response.status_code, 422)
        self.assertEqual(list(self.records_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

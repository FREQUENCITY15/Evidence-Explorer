"""Tests for bounded, ephemeral raw-artifact checksum verification."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from project_mentor import checksum_verification
from project_mentor.checksum_verification import (
    ArtifactTooLarge,
    ChecksumVerifier,
    declared_main_jsonl_checksum,
)
from project_mentor.main import app


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "evidence_loader"
    / "structured-record.json"
)


class ChecksumVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.records_dir = Path(self.temporary_directory.name) / "records"
        self.records_dir.mkdir()
        self.raw_artifact = b'{"event":"tool_result","ok":true}\n'
        self.record = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.record["checksums"]["main_jsonl"] = hashlib.sha256(
            self.raw_artifact
        ).hexdigest()
        (self.records_dir / "verified-record.json").write_text(
            json.dumps(self.record),
            encoding="utf-8",
        )
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

    def test_incremental_verifier_reports_match_and_mismatch(self) -> None:
        expected = hashlib.sha256(self.raw_artifact).hexdigest()
        matched = ChecksumVerifier(expected)
        matched.update(self.raw_artifact[:10])
        matched.update(self.raw_artifact[10:])
        mismatched = ChecksumVerifier(expected)
        mismatched.update(b"different")

        matched_result = matched.finish()
        mismatched_result = mismatched.finish()

        self.assertTrue(matched_result.verified)
        self.assertEqual(matched_result.status, "verified")
        self.assertEqual(matched_result.byte_count, len(self.raw_artifact))
        self.assertFalse(mismatched_result.verified)
        self.assertEqual(mismatched_result.status, "mismatch")

    def test_verifier_rejects_content_over_its_bound(self) -> None:
        verifier = ChecksumVerifier("0" * 64, max_bytes=3)
        verifier.update(b"abc")

        with self.assertRaisesRegex(ArtifactTooLarge, "3-byte"):
            verifier.update(b"d")

    def test_declared_checksum_is_read_without_mutating_the_record(self) -> None:
        before = json.loads(json.dumps(self.record))

        declared = declared_main_jsonl_checksum(self.record)

        self.assertEqual(declared, self.record["checksums"]["main_jsonl"])
        self.assertEqual(self.record, before)

    def test_api_verifies_bytes_without_retaining_them(self) -> None:
        response = self.client.post(
            "/api/evidence/verified-record/verify-checksum",
            content=self.raw_artifact,
            headers={"Content-Type": "application/octet-stream"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "verified")
        self.assertTrue(response.json()["verified"])
        self.assertEqual(response.json()["algorithm"], "sha256")
        self.assertEqual(response.json()["byteCount"], len(self.raw_artifact))
        self.assertFalse(response.json()["retained"])
        self.assertEqual(
            [path.name for path in self.records_dir.iterdir()],
            ["verified-record.json"],
        )

        audit = self.client.get("/api/evidence/verified-record/audit")
        self.assertEqual(
            audit.json()["source"]["checksumVerification"],
            "not_performed",
        )

    def test_api_reports_mismatch_as_a_completed_verification(self) -> None:
        response = self.client.post(
            "/api/evidence/verified-record/verify-checksum",
            content=b"tampered",
            headers={"Content-Type": "application/octet-stream"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "mismatch")
        self.assertFalse(response.json()["verified"])
        self.assertNotEqual(response.json()["actual"], response.json()["expected"])

    def test_api_rejects_missing_checksum_wrong_media_and_oversize(self) -> None:
        missing_checksum = json.loads(json.dumps(self.record))
        del missing_checksum["checksums"]["main_jsonl"]
        (self.records_dir / "missing-checksum.json").write_text(
            json.dumps(missing_checksum),
            encoding="utf-8",
        )

        missing_response = self.client.post(
            "/api/evidence/missing-checksum/verify-checksum",
            content=b"raw",
            headers={"Content-Type": "application/octet-stream"},
        )
        media_response = self.client.post(
            "/api/evidence/verified-record/verify-checksum",
            content=b"raw",
            headers={"Content-Type": "text/plain"},
        )
        with patch.object(checksum_verification, "MAX_RAW_ARTIFACT_BYTES", 3):
            oversized_response = self.client.post(
                "/api/evidence/verified-record/verify-checksum",
                content=b"four",
                headers={"Content-Type": "application/octet-stream"},
            )

        self.assertEqual(missing_response.status_code, 400)
        self.assertIn("does not declare", missing_response.json()["detail"])
        self.assertEqual(media_response.status_code, 415)
        self.assertEqual(oversized_response.status_code, 413)
        self.assertIn("3-byte", oversized_response.json()["detail"])


if __name__ == "__main__":
    unittest.main()

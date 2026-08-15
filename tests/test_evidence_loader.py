"""Tests for the evidence record loader and API endpoint."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from project_mentor import evidence_loader
from project_mentor.evidence_loader import (
    list_available_records,
    load_evidence_record,
)
from project_mentor.main import app

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "evidence_loader"


class EvidenceLoaderTests(unittest.TestCase):
    """Test the evidence loader with an isolated records directory."""

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.records_dir = Path(self.temporary_directory.name) / "records"
        self.records_dir.mkdir()
        shutil.copyfile(
            FIXTURES_DIR / "valid-record.json",
            self.records_dir / "valid-record.json",
        )
        self.environment = patch.dict(
            os.environ, {"EVIDENCE_RECORDS_DIR": str(self.records_dir)}
        )
        self.environment.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_evidence_index_returns_list(self):
        """The index endpoint lists only the isolated regular-file records."""
        response = self.client.get("/api/evidence/index")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"records": ["valid-record"]})

    def test_load_existing_record_returns_required_fields(self):
        """Loading the canonical record returns the core fields."""
        response = self.client.get("/api/evidence/valid-record")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("attemptId", data)
        self.assertIn("verdicts", data)
        self.assertIn("toolSurface", data)
        self.assertIn("modelInteraction", data)
        self.assertIn("execution", data)
        self.assertEqual(data["schemaVersion"], "1.0.0")

    def test_loader_accepts_json_filename_suffix(self):
        """The loader preserves support for a single .json suffix."""
        self.assertEqual(
            load_evidence_record("valid-record.json")["attemptId"],
            "TEST-VALID-001",
        )

    def test_load_existing_record_has_six_verdicts(self):
        """The record must contain all six verdict layers."""
        response = self.client.get("/api/evidence/valid-record")
        self.assertEqual(response.status_code, 200)
        verdicts = response.json()["verdicts"]
        expected_keys = {
            "selection", "arguments", "protocol",
            "execution", "interpretation", "completion",
        }
        self.assertEqual(set(verdicts.keys()), expected_keys)

    def test_load_existing_record_has_three_tool_groups(self):
        """The record must contain tool group classifications."""
        response = self.client.get("/api/evidence/valid-record")
        self.assertEqual(response.status_code, 200)
        ts = response.json()["toolSurface"]
        self.assertIn("effectiveExperimentalTools", ts)
        self.assertIn("hostInternalTools", ts)
        self.assertIn("forbiddenExtraTools", ts)

    def test_load_missing_record_returns_404(self):
        """A missing record filename returns 404."""
        response = self.client.get("/api/evidence/NONEXISTENT-RECORD")
        self.assertEqual(response.status_code, 404)

    def test_rejects_path_traversal(self):
        """Record identifiers cannot name paths outside the records directory."""
        outside_record = self.records_dir.parent / "outside.json"
        outside_record.write_text("{}", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "identifier"):
            load_evidence_record("../outside")

    def test_rejects_symlinked_records(self):
        """Symlinked records are neither listed nor loaded."""
        outside_record = self.records_dir.parent / "outside.json"
        outside_record.write_text("{}", encoding="utf-8")
        (self.records_dir / "linked.json").symlink_to(outside_record)

        self.assertNotIn("linked", list_available_records())
        with self.assertRaisesRegex(ValueError, "must not be a symlink"):
            load_evidence_record("linked")

    def test_runtime_directory_configuration_is_not_frozen_at_import(self):
        """Changing EVIDENCE_RECORDS_DIR changes the subsequent loader lookup."""
        alternate_dir = self.records_dir.parent / "alternate"
        alternate_dir.mkdir()
        (alternate_dir / "alternate.json").write_text("{}", encoding="utf-8")

        with patch.dict(
            os.environ, {"EVIDENCE_RECORDS_DIR": str(alternate_dir)}
        ):
            self.assertEqual(list_available_records(), ["alternate"])
            self.assertEqual(load_evidence_record("alternate"), {})

    def test_invalid_json_returns_controlled_api_error(self):
        """Malformed records produce a controlled 400 response."""
        shutil.copyfile(
            FIXTURES_DIR / "invalid-json.json",
            self.records_dir / "invalid-json.json",
        )

        response = self.client.get("/api/evidence/invalid-json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("invalid JSON", response.json()["detail"])

    def test_non_object_json_returns_controlled_api_error(self):
        """Canonical records must be JSON objects."""
        (self.records_dir / "array.json").write_text("[]", encoding="utf-8")

        response = self.client.get("/api/evidence/array")
        self.assertEqual(response.status_code, 400)
        self.assertIn("must be a JSON object", response.json()["detail"])

    def test_oversized_record_returns_controlled_api_error(self):
        """Records larger than the configured byte limit are rejected."""
        (self.records_dir / "large.json").write_text(
            json.dumps({"payload": "x" * 32}), encoding="utf-8"
        )

        with patch.object(evidence_loader, "MAX_RECORD_BYTES", 16):
            response = self.client.get("/api/evidence/large")

        self.assertEqual(response.status_code, 400)
        self.assertIn("exceeds the 16-byte limit", response.json()["detail"])

    def test_missing_records_directory_returns_controlled_error(self):
        """A missing configured directory has an explicit loader error."""
        missing_dir = self.records_dir.parent / "missing"
        with patch.dict(
            os.environ, {"EVIDENCE_RECORDS_DIR": str(missing_dir)}
        ):
            with self.assertRaisesRegex(ValueError, "directory is unavailable"):
                load_evidence_record("valid-record")

    def test_html_page_route_served(self):
        """The /evidence/{filename} route serves an HTML page."""
        response = self.client.get("/evidence/TEST-FILE")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()

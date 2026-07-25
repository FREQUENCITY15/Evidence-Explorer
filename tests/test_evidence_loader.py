"""Tests for the evidence record loader and API endpoint."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from project_mentor.main import app


class EvidenceLoaderTests(unittest.TestCase):
    """Test the evidence loader via the API endpoint."""

    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_evidence_index_returns_list(self):
        """The index endpoint returns a list of available records."""
        response = self.client.get("/api/evidence/index")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("records", data)
        self.assertIsInstance(data["records"], list)

    def test_load_existing_record_returns_required_fields(self):
        """Loading the canonical record returns the core fields."""
        response = self.client.get(
            "/api/evidence/QWEN-VSCODE-MCP-ECHO-001"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("attemptId", data)
        self.assertIn("verdicts", data)
        self.assertIn("toolSurface", data)
        self.assertIn("modelInteraction", data)
        self.assertIn("execution", data)
        self.assertEqual(data["schemaVersion"], "1.0.0")

    def test_load_existing_record_has_six_verdicts(self):
        """The record must contain all six verdict layers."""
        response = self.client.get(
            "/api/evidence/QWEN-VSCODE-MCP-ECHO-001"
        )
        self.assertEqual(response.status_code, 200)
        verdicts = response.json()["verdicts"]
        expected_keys = {
            "selection", "arguments", "protocol",
            "execution", "interpretation", "completion",
        }
        self.assertEqual(set(verdicts.keys()), expected_keys)

    def test_load_existing_record_has_three_tool_groups(self):
        """The record must contain tool group classifications."""
        response = self.client.get(
            "/api/evidence/QWEN-VSCODE-MCP-ECHO-001"
        )
        self.assertEqual(response.status_code, 200)
        ts = response.json()["toolSurface"]
        self.assertIn("effectiveExperimentalTools", ts)
        self.assertIn("hostInternalTools", ts)
        self.assertIn("forbiddenExtraTools", ts)

    def test_load_missing_record_returns_404(self):
        """A missing record filename returns 404."""
        response = self.client.get("/api/evidence/NONEXISTENT-RECORD")
        self.assertEqual(response.status_code, 404)

    def test_html_page_route_served(self):
        """The /evidence/{filename} route serves an HTML page."""
        response = self.client.get("/evidence/TEST-FILE")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()

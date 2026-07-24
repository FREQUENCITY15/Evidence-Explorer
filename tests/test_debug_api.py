from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from project_mentor.main import app


class DebugAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "app.py").write_text(
            "def run(value: str) -> str:\n"
            "    if not value:\n"
            "        raise ValueError('empty')\n"
            "    return value.strip()\n",
            encoding="utf-8",
        )
        self.client = TestClient(app)
        scan = self.client.post("/api/scan", json={"path": str(self.root)})
        self.assertEqual(scan.status_code, 200)
        self.assertEqual(scan.json()["schema_version"], "1.3.0")
        self.scan_id = scan.headers["X-Project-Mentor-Scan-ID"]

    def tearDown(self) -> None:
        self.client.close()
        self.temporary_directory.cleanup()

    def test_route_is_offline_stable_and_keeps_other_schema_versions(self) -> None:
        payload = {
            "scan_id": self.scan_id,
            "symbol_id": "app:run",
            "failure_statement": "Blank input crashes",
        }
        with patch(
            "project_mentor.main.AI_SERVICE.explain", new_callable=AsyncMock
        ) as explain:
            first = self.client.post("/api/debug/investigation", json=payload)
            second = self.client.post("/api/debug/investigation", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.content, second.content)
        self.assertEqual(first.json()["debug_schema_version"], "1.0.0")
        self.assertEqual(first.json()["conclusion_status"], "root_cause_not_established")
        self.assertLessEqual(first.json()["evidence_included_count"], 12)
        explain.assert_not_awaited()

        lesson = self.client.post(
            "/api/teach/lesson",
            json={"scan_id": self.scan_id, "symbol_id": "app:run"},
        )
        self.assertEqual(lesson.status_code, 200)
        self.assertEqual(lesson.json()["lesson_schema_version"], "1.1.0")

    def test_expired_and_missing_symbols_fail_safely(self) -> None:
        expired = self.client.post(
            "/api/debug/investigation",
            json={
                "scan_id": "x" * 24,
                "symbol_id": "app:run",
                "failure_statement": "Failure",
            },
        )
        missing = self.client.post(
            "/api/debug/investigation",
            json={
                "scan_id": self.scan_id,
                "symbol_id": "app:missing",
                "failure_statement": "Failure",
            },
        )

        self.assertEqual(expired.status_code, 409)
        self.assertEqual(expired.json()["detail"]["code"], "scan_expired")
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["detail"]["code"], "symbol_not_found")

    def test_malformed_request_is_rejected(self) -> None:
        response = self.client.post(
            "/api/debug/investigation",
            json={"scan_id": self.scan_id, "symbol_id": "app:run"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

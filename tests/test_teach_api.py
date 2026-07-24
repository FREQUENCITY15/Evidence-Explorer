from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from project_mentor.main import app


class TeachAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "app.py").write_text(
            "def run(value: str) -> str:\n    return value.strip()\n",
            encoding="utf-8",
        )
        self.client = TestClient(app)
        scan = self.client.post("/api/scan", json={"path": str(self.root)})
        self.assertEqual(scan.status_code, 200)
        self.scan_id = scan.headers["X-Project-Mentor-Scan-ID"]

    def tearDown(self) -> None:
        self.client.close()
        self.temporary_directory.cleanup()

    def test_lesson_route_is_offline_and_response_bytes_are_stable(self) -> None:
        payload = {"scan_id": self.scan_id, "symbol_id": "app:run"}
        first = self.client.post("/api/teach/lesson", json=payload)
        second = self.client.post("/api/teach/lesson", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.content, second.content)
        self.assertEqual(first.json()["symbol_id"], "app:run")
        self.assertEqual(first.json()["lesson_schema_version"], "1.1.0")
        self.assertEqual(len(first.json()["quiz"]), 3)
        self.assertTrue(first.json()["stages"])
        self.assertTrue(first.json()["evidence_groups"])
        self.assertLessEqual(first.json()["teaching_evidence_count"], 12)

    def test_expired_and_missing_symbols_fail_safely(self) -> None:
        expired = self.client.post(
            "/api/teach/lesson",
            json={"scan_id": "x" * 24, "symbol_id": "app:run"},
        )
        missing = self.client.post(
            "/api/teach/lesson",
            json={"scan_id": self.scan_id, "symbol_id": "app:missing"},
        )

        self.assertEqual(expired.status_code, 409)
        self.assertEqual(expired.json()["detail"]["code"], "scan_expired")
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["detail"]["code"], "symbol_not_found")

    def test_malformed_lesson_request_is_rejected(self) -> None:
        response = self.client.post(
            "/api/teach/lesson", json={"scan_id": self.scan_id}
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

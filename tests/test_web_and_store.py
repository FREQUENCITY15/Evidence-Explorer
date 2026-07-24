from pathlib import Path
import tempfile
import unittest
import warnings

warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`.*")
from fastapi.testclient import TestClient

from project_mentor.main import app
from project_mentor.scan_store import ScanStore
from project_mentor.scanner import scan_project


class WebAndStoreTests(unittest.TestCase):
    def test_scan_route_works_without_contacting_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "app.py").write_text(
                "def run():\n    return True\n", encoding="utf-8"
            )
            with TestClient(app) as client:
                response = client.post("/api/scan", json={"path": str(root)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["python_files"], 1)
        self.assertEqual(response.json()["schema_version"], "1.3.0")
        self.assertTrue(response.headers.get("X-Project-Mentor-Scan-ID"))

    def test_scan_store_is_bounded_and_opaque(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "app.py").write_text("value = 1\n", encoding="utf-8")
            analysis = scan_project(root)
            store = ScanStore(max_entries=1)
            first = store.put(analysis)
            second = store.put(analysis)

        self.assertNotEqual(first, second)
        self.assertIsNone(store.get(first))
        self.assertIs(store.get(second), analysis)
        self.assertNotIn(str(root), second)

    def test_browser_uses_text_content_for_untrusted_model_output(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        app_js = (project_root / "project_mentor" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        index = (project_root / "project_mentor" / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'document.querySelector("#ai-answer-text").textContent = interpretation.answer',
            app_js,
        )
        self.assertNotIn("innerHTML = interpretation.answer", app_js)
        self.assertIn("Observed deterministic facts", index)
        self.assertIn("Project Mentor inference", index)
        self.assertIn("Local-model interpretation", index)

    def test_teach_ui_keeps_model_output_safe_and_exports_are_user_triggered(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        app_js = (project_root / "project_mentor" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        index = (project_root / "project_mentor" / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        styles = (project_root / "project_mentor" / "static" / "styles.css").read_text(
            encoding="utf-8"
        )

        self.assertIn('document.querySelector("#teach-ai-answer-text").textContent = interpretation.answer', app_js)
        self.assertNotIn('document.querySelector("#teach-ai-answer-text").innerHTML', app_js)
        self.assertIn("window.showSaveFilePicker", app_js)
        self.assertIn("Export interpretation (.md)", index)
        self.assertIn("Export full evidence (.json)", index)
        self.assertIn("Export readable lesson (.md)", index)
        self.assertIn("deterministicLessonMarkdown(currentTeachLesson)", app_js)
        self.assertIn("teachExportMarkdownButton.addEventListener", app_js)
        self.assertIn('id="teach-stages"', index)
        self.assertIn('id="teach-evidence-details"', index)
        self.assertIn('<details class="reference-disclosure">', app_js)
        self.assertIn("escapeHtml(detail.content)", app_js)
        self.assertNotIn(
            "<code>${escapeHtml(item.reference.evidence_id)}</code>", app_js
        )
        self.assertIn('id="teach-tab"', index)
        self.assertIn('id="teach-view"', index)
        self.assertIn(
            "grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr)", styles
        )
        self.assertIn(".teach-card .confidence", styles)
        self.assertIn("overflow-wrap: anywhere", styles)


if __name__ == "__main__":
    unittest.main()

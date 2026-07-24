from pathlib import Path
import unittest


class DebugUITests(unittest.TestCase):
    def test_debug_ui_is_offline_safe_and_exports_are_user_triggered(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        app_js = (project_root / "project_mentor" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        index = (project_root / "project_mentor" / "static" / "index.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="debug-tab"', index)
        self.assertIn('id="debug-view"', index)
        self.assertIn('id="debug-hypotheses"', index)
        self.assertIn('id="debug-diagnostics"', index)
        self.assertIn("It does not run code, commands, or Ollama", index)
        self.assertIn(
            'document.querySelector("#debug-failure-statement").textContent = investigation.failure_statement',
            app_js,
        )
        self.assertNotIn(
            'document.querySelector("#debug-failure-statement").innerHTML', app_js
        )
        self.assertIn("escapeHtml(detail.content)", app_js)
        self.assertIn('fetch("/api/debug/investigation"', app_js)
        self.assertNotIn('fetch("/api/debug/explain"', app_js)
        self.assertIn("debugExportJsonButton.addEventListener", app_js)
        self.assertIn("debugExportMarkdownButton.addEventListener", app_js)
        self.assertIn("deterministicDebugMarkdown(currentDebugInvestigation)", app_js)


if __name__ == "__main__":
    unittest.main()

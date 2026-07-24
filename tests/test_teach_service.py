import json
from pathlib import Path
import tempfile
import unittest

from project_mentor.context_builder import EvidenceContextBuilder
from project_mentor.scanner import scan_project
from project_mentor.teach_service import TeachLessonError, TeachLessonService


class TeachLessonServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "helpers.py").write_text(
            "def normalize(value: str) -> str:\n    return value.strip()\n",
            encoding="utf-8",
        )
        (self.root / "app.py").write_text(
            "from helpers import normalize\n\n"
            "class Processor:\n"
            "    def process(self, value: str, store: dict) -> str:\n"
            "        cleaned = normalize(value)\n"
            "        store['last'] = cleaned\n"
            "        if not cleaned:\n"
            "            raise ValueError('empty')\n"
            "        return cleaned\n",
            encoding="utf-8",
        )
        self.analysis = scan_project(self.root)
        self.service = TeachLessonService()
        self.symbol_id = "app:Processor.process"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_unchanged_evidence_produces_byte_stable_lesson(self) -> None:
        first = self.service.build(self.analysis, self.symbol_id).lesson.to_dict()
        second = self.service.build(self.analysis, self.symbol_id).lesson.to_dict()
        first_bytes = json.dumps(
            first, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        second_bytes = json.dumps(
            second, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

        self.assertEqual(first_bytes, second_bytes)
        self.assertTrue(first["lesson_id"].startswith("LESSON-"))
        self.assertNotIn("generated_at", first)

    def test_lesson_contains_grounded_vertical_slice(self) -> None:
        lesson = self.service.build(self.analysis, self.symbol_id).lesson.to_dict()

        self.assertEqual(lesson["lesson_schema_version"], "1.1.0")
        self.assertEqual(lesson["symbol_id"], self.symbol_id)
        self.assertEqual(len(lesson["quiz"]), 3)
        self.assertTrue(lesson["stages"])
        self.assertTrue(lesson["prediction_exercise"]["expected_answer"])
        self.assertTrue(all(item["answer_explanation"] for item in lesson["quiz"]))
        self.assertTrue(lesson["vocabulary"])
        self.assertTrue(lesson["evidence_references"])
        self.assertTrue(lesson["evidence_groups"])
        self.assertLessEqual(lesson["teaching_evidence_count"], 12)
        self.assertTrue(
            any(item["relationship"] == "resolved_internal_call" for item in lesson["prerequisites"])
        )
        self.assertTrue(
            any(section["heading"] == "Errors and runtime boundary" for section in lesson["sections"])
        )
        self.assertTrue(
            any("Runtime boundary" in label for label in lesson["uncertainty_labels"])
        )

    def test_lesson_reuses_map_evidence_ids(self) -> None:
        bundle = self.service.build(self.analysis, self.symbol_id)
        context = EvidenceContextBuilder(200_000).build(
            self.analysis,
            question="Explain this method.",
            selected_symbol_id=self.symbol_id,
            workflow="map",
        )
        lesson_ids = {item.evidence_id for item in bundle.evidence_items}
        map_ids = {item.evidence_id for item in context.evidence_items}

        self.assertTrue(lesson_ids & map_ids)
        self.assertIn(bundle.evidence_items[0].evidence_id, map_ids)

    def test_missing_and_non_function_symbols_fail_clearly(self) -> None:
        with self.assertRaises(TeachLessonError) as missing:
            self.service.build(self.analysis, "app:missing")
        with self.assertRaises(TeachLessonError) as unsupported:
            self.service.build(self.analysis, "app:Processor")

        self.assertEqual(missing.exception.code, "symbol_not_found")
        self.assertEqual(unsupported.exception.code, "unsupported_symbol_kind")

    def test_building_a_lesson_does_not_execute_scanned_source(self) -> None:
        marker = self.root / "executed.txt"
        (self.root / "danger.py").write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed')\n"
            "def inspect_only():\n    return 1\n",
            encoding="utf-8",
        )
        analysis = scan_project(self.root)
        lesson = self.service.build(analysis, "danger:inspect_only").lesson

        self.assertFalse(marker.exists())
        self.assertEqual(lesson.symbol_id, "danger:inspect_only")

    def test_large_function_lesson_is_bounded_and_reports_omissions(self) -> None:
        parameters = ", ".join(f"p{index}" for index in range(40))
        assignments = "\n".join(
            f"    value_{index} = p0" for index in range(60)
        )
        (self.root / "large.py").write_text(
            f"def bounded({parameters}):\n{assignments}\n    return p0\n",
            encoding="utf-8",
        )
        analysis = scan_project(self.root)
        lesson = self.service.build(analysis, "large:bounded").lesson

        self.assertGreater(lesson.evidence_candidate_count, lesson.evidence_included_count)
        self.assertGreater(lesson.evidence_omitted_count, 0)
        self.assertTrue(
            any("Technical evidence limit" in label for label in lesson.uncertainty_labels)
        )

    def test_beginner_prose_hides_ids_and_keeps_exact_evidence_separate(self) -> None:
        lesson = self.service.build(self.analysis, self.symbol_id).lesson.to_dict()
        beginner_strings = [
            lesson["title"],
            lesson["learning_objective"],
            *(item["title"] for item in lesson["prerequisites"]),
            *(item["reason"] for item in lesson["prerequisites"]),
            *(item["title"] for item in lesson["stages"]),
            *(item["explanation"] for item in lesson["stages"]),
            *(item["body"] for item in lesson["sections"]),
            *(item["definition"] for item in lesson["vocabulary"]),
            lesson["prediction_exercise"]["prompt"],
            lesson["prediction_exercise"]["expected_answer"],
            lesson["prediction_exercise"]["answer_explanation"],
            *(item["prompt"] for item in lesson["quiz"]),
            *(item["answer_explanation"] for item in lesson["quiz"]),
        ]

        self.assertNotIn("EV-", " ".join(beginner_strings))
        detail_count = sum(
            len(group["details"]) for group in lesson["evidence_groups"]
        )
        self.assertEqual(detail_count, lesson["evidence_included_count"])
        self.assertTrue(
            all(
                detail["reference"]["evidence_id"].startswith("EV-")
                and detail["content"]
                for group in lesson["evidence_groups"]
                for detail in group["details"]
            )
        )

    def test_scan_project_lesson_is_grouped_bounded_and_meaningful(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        analysis = scan_project(project_root)
        bundle = self.service.build(
            analysis, "project_mentor.scanner:scan_project"
        )
        lesson = bundle.lesson.to_dict()
        section_bodies = [item["body"] for item in lesson["sections"]]
        beginner_text = " ".join(
            section_bodies
            + [item["explanation"] for item in lesson["stages"]]
            + [lesson["prediction_exercise"]["expected_answer"]]
            + [item["prompt"] for item in lesson["quiz"]]
        )

        self.assertLessEqual(bundle.lesson.teaching_evidence_count, 12)
        self.assertLessEqual(max(map(len, section_bodies)), 700)
        self.assertLessEqual(sum(map(len, section_bodies)), 2_000)
        self.assertNotIn("The AST does not reveal actual exception behavior", beginner_text)
        self.assertNotIn("EV-", beginner_text)
        self.assertLess(len(lesson["prediction_exercise"]["expected_answer"]), 160)
        self.assertIn("ValueError", lesson["prediction_exercise"]["expected_answer"])
        self.assertFalse(
            any("What kind of symbol" in item["prompt"] for item in lesson["quiz"])
        )
        self.assertFalse(
            any("at least one parameter" in item["prompt"] for item in lesson["quiz"])
        )
        self.assertTrue(
            all("__init__.py" not in item["title"] for item in lesson["prerequisites"])
        )

        call_targets = []
        for item in bundle.evidence_items:
            if item.kind == "call_relationship":
                call_targets.append(json.loads(item.content)["target_expression"])
        self.assertIn("discover_python_files", call_targets)
        self.assertIn("infer_error_propagation", call_targets)
        self.assertNotIn("len", call_targets)
        self.assertNotIn("sum", call_targets)

        exact_contents = [
            detail["content"]
            for group in lesson["evidence_groups"]
            for detail in group["details"]
        ]
        self.assertTrue(
            any("ProjectAnalysis(schema_version=SCHEMA_VERSION" in item for item in exact_contents)
        )

    def test_evidence_group_order_and_summaries_are_stable(self) -> None:
        first = self.service.build(self.analysis, self.symbol_id).lesson.to_dict()
        second = self.service.build(self.analysis, self.symbol_id).lesson.to_dict()

        first_groups = [item["heading"] for item in first["evidence_groups"]]
        second_groups = [item["heading"] for item in second["evidence_groups"]]
        self.assertEqual(first_groups, second_groups)
        self.assertEqual(
            first_groups,
            [
                "Definition and inputs",
                "Outputs and state",
                "Explicit errors and exception paths",
                "Calls",
                "Data flow",
                "Call error propagation",
                "Internal imports",
            ],
        )
        self.assertTrue(
            all("record" in item["summary"] for item in first["evidence_groups"])
        )


if __name__ == "__main__":
    unittest.main()

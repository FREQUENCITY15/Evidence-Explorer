import copy
import json
from pathlib import Path
import unittest

from project_mentor.evidence_schema import (
    EvidenceSchemaError,
    MAX_EVIDENCE_REFS,
    VERDICT_LAYERS,
    resolve_json_pointer,
    validate_evidence_record,
)


SAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "evidence"
    / "sample"
    / "QWEN-VSCODE-MCP-ECHO-001.json"
)


def sample_record():
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


class EvidenceSchemaTests(unittest.TestCase):
    def test_legacy_sample_normalizes_without_losing_its_meaning(self) -> None:
        validated = validate_evidence_record(sample_record())

        self.assertTrue(validated.is_complete)
        self.assertEqual(set(validated.verdicts), set(VERDICT_LAYERS))
        self.assertEqual(validated.verdicts["selection"].classification, "fail")
        self.assertEqual(validated.verdicts["selection"].determination, "invalid_test")
        self.assertTrue(validated.verdicts["selection"].legacy)
        self.assertEqual(len(validated.warnings), len(VERDICT_LAYERS))

    def test_structured_verdicts_resolve_stable_local_pointers(self) -> None:
        record = sample_record()
        record["pointer/source"] = {"tilde~key": False}
        for layer in VERDICT_LAYERS:
            record["verdicts"][layer] = {
                "determination": "pass",
                "category": None,
                "evidenceRefs": [
                    "#/modelInteraction/parsedToolName",
                    "#/pointer~1source/tilde~0key",
                ],
                "notes": "Verified from captured evidence.",
            }

        validated = validate_evidence_record(record)

        self.assertEqual(validated.warnings, ())
        self.assertFalse(validated.verdicts["selection"].legacy)
        self.assertEqual(
            resolve_json_pointer(record, "#/pointer~1source/tilde~0key"),
            False,
        )

    def test_null_and_false_evidence_values_are_preserved(self) -> None:
        record = sample_record()
        record["modelInteraction"]["parsedToolName"] = None
        record["modelInteraction"]["rawArguments"] = None
        record["modelInteraction"]["finalAnswer"] = None
        record["execution"]["successful"] = False
        record["execution"]["boundedToolResult"] = None

        validated = validate_evidence_record(record)

        self.assertTrue(validated.is_complete)
        self.assertIsNone(validated.record["modelInteraction"]["parsedToolName"])
        self.assertIs(validated.record["execution"]["successful"], False)
        self.assertIsNone(validated.record["execution"]["boundedToolResult"])

    def test_missing_observations_are_reported_without_hiding_the_record(self) -> None:
        record = sample_record()
        del record["task"]["exactPrompt"]
        del record["modelInteraction"]["parsedToolName"]
        del record["verdicts"]["completion"]

        validated = validate_evidence_record(record)

        self.assertFalse(validated.is_complete)
        self.assertIn("missing:/task/exactPrompt", validated.completeness_gaps)
        self.assertIn(
            "missing:/modelInteraction/parsedToolName",
            validated.completeness_gaps,
        )
        self.assertIn("missing:/verdicts/completion", validated.completeness_gaps)

    def test_malformed_or_unresolvable_evidence_references_are_rejected(self) -> None:
        bad_refs = (
            "https://example.test/evidence",
            "#/missing/path",
            "#/bad~2escape",
            "#/observations/01",
        )
        for reference in bad_refs:
            with self.subTest(reference=reference):
                record = sample_record()
                record["verdicts"]["selection"] = {
                    "determination": "pass",
                    "evidenceRefs": [reference],
                }
                with self.assertRaises(EvidenceSchemaError):
                    validate_evidence_record(record)

    def test_reference_count_is_bounded_and_duplicates_are_deduplicated(self) -> None:
        record = sample_record()
        record["verdicts"]["selection"] = {
            "determination": "pass",
            "evidenceRefs": ["#/attemptId", "#/attemptId"],
        }
        validated = validate_evidence_record(record)
        self.assertEqual(validated.verdicts["selection"].evidence_refs, ("#/attemptId",))

        record["verdicts"]["selection"]["evidenceRefs"] = [
            "#/attemptId"
        ] * (MAX_EVIDENCE_REFS + 1)
        with self.assertRaises(EvidenceSchemaError):
            validate_evidence_record(record)

    def test_wrong_schema_types_and_unknown_determinations_are_rejected(self) -> None:
        mutations = []
        wrong_version = sample_record()
        wrong_version["schemaVersion"] = "2.0.0"
        mutations.append(wrong_version)
        wrong_boolean = sample_record()
        wrong_boolean["execution"]["successful"] = 1
        mutations.append(wrong_boolean)
        wrong_tools = sample_record()
        wrong_tools["toolSurface"]["hostInternalTools"] = [False]
        mutations.append(wrong_tools)
        unknown_verdict = sample_record()
        unknown_verdict["verdicts"]["selection"] = "probably"
        mutations.append(unknown_verdict)

        for record in mutations:
            with self.subTest(record=record):
                with self.assertRaises(EvidenceSchemaError):
                    validate_evidence_record(record)

    def test_validation_does_not_mutate_input(self) -> None:
        record = sample_record()
        before = copy.deepcopy(record)

        validate_evidence_record(record)

        self.assertEqual(record, before)


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import unittest

from project_mentor.governance import evaluate_governance


CASES_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "governance" / "cases.json"
)


class GovernanceTests(unittest.TestCase):
    def test_six_acceptance_cases_are_deterministic(self) -> None:
        cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 6)

        for case in cases:
            with self.subTest(case=case["name"]):
                record = {
                    "overallOutcome": case["overallOutcome"],
                    "toolSurface": case["toolSurface"],
                }
                first = evaluate_governance(record, case["completenessGaps"])
                second = evaluate_governance(record, case["completenessGaps"])

                self.assertEqual(first, second)
                self.assertEqual(first.status, case["expectedStatus"])
                self.assertEqual(
                    [finding.code for finding in first.findings],
                    case["expectedCodes"],
                )

    def test_ordinary_attempt_failure_is_not_a_policy_violation(self) -> None:
        record = {
            "overallOutcome": "fail",
            "toolSurface": {
                "effectiveExperimentalTools": ["echo"],
                "hostInternalTools": [],
                "forbiddenExtraTools": [],
                "hostInvokedTools": ["echo"],
            },
        }

        result = evaluate_governance(record)

        self.assertEqual(result.status, "green")
        self.assertIn("No tool-policy violation", result.summary)

    def test_surface_drift_is_unscored_even_when_a_violation_is_observed(self) -> None:
        record = {
            "toolSurface": {
                "effectiveExperimentalTools": [],
                "hostInternalTools": ["session_store"],
                "forbiddenExtraTools": [],
                "hostInvokedTools": ["session_store"],
                "hostInternalBaseline": {"matchesExpected": False},
            }
        }

        result = evaluate_governance(record)

        self.assertEqual(result.status, "unscored")
        self.assertFalse(result.scoreable)
        self.assertEqual(
            [finding.severity for finding in result.findings],
            ["unscored", "red"],
        )

    def test_canonical_failure_category_marks_surface_drift_unscored(self) -> None:
        record = {
            "failureCategory": "host_surface_drift",
            "toolSurface": {
                "effectiveExperimentalTools": ["echo"],
                "hostInternalTools": ["session_store"],
                "forbiddenExtraTools": [],
                "modelVisibleTools": ["echo", "session_store"],
                "hostInvokedTools": ["echo"],
            },
        }

        result = evaluate_governance(record)

        self.assertEqual(result.status, "unscored")
        self.assertEqual(result.findings[0].evidence_refs, ("#/failureCategory",))
        self.assertEqual(result.findings[1].severity, "amber")

    def test_unknown_invoked_tool_is_forbidden_by_default(self) -> None:
        record = {
            "toolSurface": {
                "effectiveExperimentalTools": [],
                "hostInternalTools": [],
                "forbiddenExtraTools": [],
                "hostInvokedTools": [
                    {
                        "name": "undeclared_tool",
                        "classification": "experimental",
                    }
                ],
            }
        }

        result = evaluate_governance(record)

        self.assertEqual(result.status, "red")
        self.assertEqual(result.findings[0].code, "forbidden_tool_invoked")

    def test_incomplete_evidence_cites_the_nearest_present_parent(self) -> None:
        record = {"toolSurface": {}, "execution": {"successful": False}}

        result = evaluate_governance(
            record,
            ("missing:/execution/boundedToolResult", "missing:/checksums"),
        )

        self.assertEqual(result.status, "flagged")
        self.assertEqual(
            result.findings[0].evidence_refs,
            ("#/execution", "#"),
        )


if __name__ == "__main__":
    unittest.main()

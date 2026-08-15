"""Deterministic audit analysis and export for canonical evidence records."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from project_mentor.evidence_schema import validate_evidence_record
from project_mentor.governance import evaluate_governance


AUDIT_EXPORT_VERSION = "1.0.0"


def build_validation_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    """Build the shared deterministic validation and governance payload."""
    validated = validate_evidence_record(record)
    governance = evaluate_governance(record, validated.completeness_gaps)
    return {
        "schemaVersion": record["schemaVersion"],
        "isComplete": validated.is_complete,
        "completenessGaps": list(validated.completeness_gaps),
        "warnings": list(validated.warnings),
        "verdicts": {
            layer: {
                "determination": verdict.determination,
                "classification": verdict.classification,
                "category": verdict.category,
                "evidenceRefs": list(verdict.evidence_refs),
                "notes": verdict.notes,
                "legacy": verdict.legacy,
            }
            for layer, verdict in validated.verdicts.items()
        },
        "governance": {
            "status": governance.status,
            "scoreable": governance.scoreable,
            "summary": governance.summary,
            "findings": [
                {
                    "code": finding.code,
                    "severity": finding.severity,
                    "message": finding.message,
                    "evidenceRefs": list(finding.evidence_refs),
                }
                for finding in governance.findings
            ],
        },
    }


def build_audit_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the versioned, lossless audit export data model."""
    validation = build_validation_payload(record)
    checksums = record.get("checksums")
    main_checksum = (
        checksums.get("main_jsonl") if isinstance(checksums, Mapping) else None
    )
    return {
        "auditExportVersion": AUDIT_EXPORT_VERSION,
        "source": {
            "attemptId": record.get("attemptId"),
            "recordedAt": record.get("recordedAt"),
            "schemaVersion": record.get("schemaVersion"),
            "mainJsonlChecksum": main_checksum,
            "checksumVerification": "not_performed",
        },
        "validation": validation,
        "record": dict(record),
    }


def render_audit_json(record: Mapping[str, Any]) -> str:
    """Render a byte-stable JSON audit artifact without runtime timestamps."""
    return json.dumps(
        build_audit_payload(record),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _inline_code(value: Any) -> str:
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    delimiter = "`" * max(1, longest + 1)
    return f"{delimiter} {text} {delimiter}"


def _json_fence(raw_json: str) -> str:
    longest = max(
        (len(match.group(0)) for match in re.finditer(r"`+", raw_json)),
        default=0,
    )
    return "`" * max(3, longest + 1)


def render_audit_markdown(record: Mapping[str, Any]) -> str:
    """Render a readable Markdown audit with literal, injection-safe values."""
    payload = build_audit_payload(record)
    validation = payload["validation"]
    governance = validation["governance"]
    source = payload["source"]

    findings = "\n".join(
        "- "
        + " · ".join(
            (
                _inline_code(finding["severity"]),
                _inline_code(finding["code"]),
                _inline_code(finding["message"]),
                _inline_code(", ".join(finding["evidenceRefs"]) or "no citation"),
            )
        )
        for finding in governance["findings"]
    ) or "- No governance findings."
    verdicts = "\n".join(
        "- "
        + " · ".join(
            (
                _inline_code(layer),
                _inline_code(verdict["determination"]),
                _inline_code(verdict["classification"]),
                _inline_code(", ".join(verdict["evidenceRefs"]) or "unmoored"),
            )
        )
        for layer, verdict in validation["verdicts"].items()
    ) or "- No verdicts were available."
    gaps = "\n".join(
        f"- {_inline_code(gap)}" for gap in validation["completenessGaps"]
    ) or "- None."
    warnings = "\n".join(
        f"- {_inline_code(warning)}" for warning in validation["warnings"]
    ) or "- None."
    raw_json = json.dumps(payload["record"], ensure_ascii=False, indent=2, sort_keys=True)
    fence = _json_fence(raw_json)

    return f"""# Evidence Explorer audit

## Source

- Attempt: {_inline_code(source['attemptId'])}
- Recorded: {_inline_code(source['recordedAt'])}
- Record schema: {_inline_code(source['schemaVersion'])}
- Audit export schema: {_inline_code(payload['auditExportVersion'])}
- Main JSONL checksum: {_inline_code(source['mainJsonlChecksum'])}
- Checksum verification: {_inline_code(source['checksumVerification'])}

## Govern

- Status: {_inline_code(governance['status'])}
- Scoreable: {_inline_code(str(governance['scoreable']).lower())}
- Summary: {_inline_code(governance['summary'])}

### Findings

{findings}

## Reliability verdicts

{verdicts}

## Evidence completeness gaps

{gaps}

## Validation warnings

{warnings}

## Canonical record

{fence}json
{raw_json}
{fence}

The JSON audit export is the lossless source of truth. Checksum verification is
reported as not performed until the corresponding raw artifact is supplied and checked.
"""

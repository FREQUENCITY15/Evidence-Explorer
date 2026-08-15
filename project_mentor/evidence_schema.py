"""Canonical validation for Evidence Explorer attempt records.

The validator deliberately separates malformed data from incomplete evidence.
Malformed structures and unresolvable citations raise ``EvidenceSchemaError``;
missing observations are returned as completeness gaps so failed experiments
remain inspectable in the viewer.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


SCHEMA_VERSION = "1.0.0"
VERDICT_LAYERS = (
    "selection",
    "arguments",
    "protocol",
    "execution",
    "interpretation",
    "completion",
)
MAX_EVIDENCE_REFS = 50
MAX_POINTER_DEPTH = 64
MAX_POINTER_LENGTH = 2_000

_DETERMINATIONS = {
    "pass": "pass",
    "valid": "pass",
    "success": "pass",
    "successful": "pass",
    "compliant": "pass",
    "accepted": "pass",
    "fail": "fail",
    "failed": "fail",
    "invalid": "fail",
    "invalid_test": "fail",
    "forbidden": "fail",
    "error": "fail",
    "reject": "fail",
    "rejected": "fail",
    "violation": "fail",
    "flag": "warn",
    "flagged": "warn",
    "warn": "warn",
    "warning": "warn",
    "incomplete": "warn",
    "unknown": "warn",
    "missing": "warn",
    "not observed": "warn",
    "uncertain": "warn",
}
_CHECKSUM_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_MISSING = object()


class EvidenceSchemaError(ValueError):
    """Raised when an attempt record cannot be interpreted safely."""


@dataclass(frozen=True)
class NormalizedVerdict:
    determination: str
    classification: str
    category: str | None
    evidence_refs: tuple[str, ...]
    notes: str | None
    legacy: bool


@dataclass(frozen=True)
class ValidatedEvidenceRecord:
    record: Mapping[str, Any]
    verdicts: Mapping[str, NormalizedVerdict]
    completeness_gaps: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.completeness_gaps


def classify_determination(value: str) -> str:
    """Return the stable pass/fail/warn class for a verdict determination."""
    if not isinstance(value, str):
        raise EvidenceSchemaError("Verdict determination must be text.")
    normalized = value.strip().casefold()
    try:
        return _DETERMINATIONS[normalized]
    except KeyError as exc:
        raise EvidenceSchemaError(f"Unknown verdict determination: {value!r}.") from exc


def _decode_pointer_token(token: str) -> str:
    output: list[str] = []
    index = 0
    while index < len(token):
        if token[index] != "~":
            output.append(token[index])
            index += 1
            continue
        if index + 1 >= len(token) or token[index + 1] not in "01":
            raise EvidenceSchemaError("Evidence reference contains an invalid JSON Pointer escape.")
        output.append("~" if token[index + 1] == "0" else "/")
        index += 2
    return "".join(output)


def resolve_json_pointer(record: Mapping[str, Any], reference: str) -> Any:
    """Resolve a bounded, record-local RFC 6901 JSON Pointer fragment."""
    if not isinstance(reference, str) or not reference.startswith("#/"):
        raise EvidenceSchemaError("Evidence references must be record-local '#/...' pointers.")
    if len(reference) > MAX_POINTER_LENGTH:
        raise EvidenceSchemaError("Evidence reference exceeds the length limit.")
    raw_tokens = reference[2:].split("/")
    if len(raw_tokens) > MAX_POINTER_DEPTH:
        raise EvidenceSchemaError("Evidence reference exceeds the depth limit.")

    current: Any = record
    for raw_token in raw_tokens:
        token = _decode_pointer_token(raw_token)
        if isinstance(current, Mapping):
            if token not in current:
                raise EvidenceSchemaError(f"Evidence reference does not resolve: {reference!r}.")
            current = current[token]
        elif isinstance(current, list):
            if not token.isascii() or not token.isdigit() or (
                len(token) > 1 and token.startswith("0")
            ):
                raise EvidenceSchemaError(f"Invalid array index in evidence reference: {reference!r}.")
            array_index = int(token)
            if array_index >= len(current):
                raise EvidenceSchemaError(f"Evidence reference does not resolve: {reference!r}.")
            current = current[array_index]
        else:
            raise EvidenceSchemaError(f"Evidence reference traverses a scalar: {reference!r}.")
    return current


def _normalize_verdict(
    layer: str,
    value: Any,
    record: Mapping[str, Any],
) -> tuple[NormalizedVerdict, str | None]:
    if isinstance(value, str):
        determination = value
        category = None
        evidence_refs: list[str] = []
        notes = None
        legacy = True
    elif isinstance(value, Mapping):
        determination = value.get("determination")
        if not isinstance(determination, str) or not determination.strip():
            raise EvidenceSchemaError(f"Verdict {layer!r} requires a text determination.")
        category = value.get("category")
        notes = value.get("notes")
        refs_value = value.get("evidenceRefs", [])
        if category is not None and not isinstance(category, str):
            raise EvidenceSchemaError(f"Verdict {layer!r} category must be text or null.")
        if notes is not None and not isinstance(notes, str):
            raise EvidenceSchemaError(f"Verdict {layer!r} notes must be text or null.")
        if not isinstance(refs_value, list) or not all(isinstance(ref, str) for ref in refs_value):
            raise EvidenceSchemaError(f"Verdict {layer!r} evidenceRefs must be a list of text pointers.")
        if len(refs_value) > MAX_EVIDENCE_REFS:
            raise EvidenceSchemaError(f"Verdict {layer!r} has too many evidence references.")
        evidence_refs = list(dict.fromkeys(refs_value))
        legacy = False
    else:
        raise EvidenceSchemaError(f"Verdict {layer!r} must be text or an object.")

    classification = classify_determination(determination)
    for reference in evidence_refs:
        resolve_json_pointer(record, reference)
    warning = None if evidence_refs else f"unmoored_verdict:{layer}"
    return (
        NormalizedVerdict(
            determination=determination,
            classification=classification,
            category=category,
            evidence_refs=tuple(evidence_refs),
            notes=notes,
            legacy=legacy,
        ),
        warning,
    )


def _container(
    record: Mapping[str, Any],
    name: str,
    gaps: list[str],
) -> Mapping[str, Any] | None:
    value = record.get(name, _MISSING)
    if value is _MISSING or value is None:
        gaps.append(f"missing:/{name}")
        return None
    if not isinstance(value, Mapping):
        raise EvidenceSchemaError(f"/{name} must be an object.")
    return value


def _required_value(
    container: Mapping[str, Any] | None,
    path: str,
    key: str,
    expected_type: type | tuple[type, ...],
    gaps: list[str],
    *,
    nullable: bool = False,
    nonempty: bool = False,
) -> Any:
    if container is None:
        return _MISSING
    value = container.get(key, _MISSING)
    if value is _MISSING:
        gaps.append(f"missing:{path}")
        return value
    if value is None:
        if not nullable:
            gaps.append(f"missing:{path}")
        return value
    if not isinstance(value, expected_type) or (expected_type is bool and type(value) is not bool):
        raise EvidenceSchemaError(f"{path} has the wrong type.")
    if nonempty and isinstance(value, str) and not value.strip():
        gaps.append(f"empty:{path}")
    return value


def validate_evidence_record(record: Mapping[str, Any]) -> ValidatedEvidenceRecord:
    """Validate and normalize one canonical Evidence Explorer attempt record."""
    if not isinstance(record, Mapping):
        raise EvidenceSchemaError("Evidence record must be a JSON object.")
    if record.get("schemaVersion") != SCHEMA_VERSION:
        raise EvidenceSchemaError(f"schemaVersion must be {SCHEMA_VERSION!r}.")

    gaps: list[str] = []
    warnings: list[str] = []
    _required_value(record, "/experimentId", "experimentId", str, gaps, nonempty=True)
    _required_value(record, "/attemptId", "attemptId", str, gaps, nonempty=True)
    _required_value(record, "/recordedAt", "recordedAt", str, gaps, nonempty=True)
    _required_value(record, "/overallOutcome", "overallOutcome", str, gaps, nonempty=True)

    model = _container(record, "model", gaps)
    task = _container(record, "task", gaps)
    tool_surface = _container(record, "toolSurface", gaps)
    interaction = _container(record, "modelInteraction", gaps)
    execution = _container(record, "execution", gaps)
    checksums = _container(record, "checksums", gaps)

    _required_value(model, "/model/name", "name", str, gaps, nonempty=True)
    _required_value(task, "/task/exactPrompt", "exactPrompt", str, gaps, nonempty=True)
    for key in ("effectiveExperimentalTools", "hostInternalTools", "forbiddenExtraTools"):
        tools = _required_value(tool_surface, f"/toolSurface/{key}", key, list, gaps)
        if tools is not _MISSING and tools is not None and not all(isinstance(tool, str) for tool in tools):
            raise EvidenceSchemaError(f"/toolSurface/{key} must contain only tool names.")

    # These keys must exist in canonical records, but null is meaningful evidence
    # for failed or incomplete attempts and must not be coerced away.
    for key in ("parsedToolName", "rawArguments", "finalAnswer"):
        _required_value(interaction, f"/modelInteraction/{key}", key, str, gaps, nullable=True)
    _required_value(execution, "/execution/successful", "successful", bool, gaps)
    _required_value(
        execution,
        "/execution/boundedToolResult",
        "boundedToolResult",
        (str, bool, int, float, list, dict),
        gaps,
        nullable=True,
    )

    checksum = _required_value(
        checksums,
        "/checksums/main_jsonl",
        "main_jsonl",
        str,
        gaps,
        nonempty=True,
    )
    if checksum is not _MISSING and checksum is not None and not _CHECKSUM_RE.fullmatch(checksum):
        raise EvidenceSchemaError("/checksums/main_jsonl must be a 64-character hexadecimal checksum.")

    normalized_verdicts: dict[str, NormalizedVerdict] = {}
    verdicts = _container(record, "verdicts", gaps)
    if verdicts is not None:
        extras = set(verdicts) - set(VERDICT_LAYERS)
        if extras:
            raise EvidenceSchemaError(f"Unknown verdict layers: {', '.join(sorted(extras))}.")
        for layer in VERDICT_LAYERS:
            if layer not in verdicts:
                gaps.append(f"missing:/verdicts/{layer}")
                continue
            normalized, warning = _normalize_verdict(layer, verdicts[layer], record)
            normalized_verdicts[layer] = normalized
            if warning:
                warnings.append(warning)

    return ValidatedEvidenceRecord(
        record=record,
        verdicts=normalized_verdicts,
        completeness_gaps=tuple(gaps),
        warnings=tuple(warnings),
    )

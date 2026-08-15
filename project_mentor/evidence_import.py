"""Validation-first persistence for user-imported evidence records."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping

from project_mentor.audit_export import build_validation_payload
from project_mentor.evidence_loader import (
    MAX_RECORD_BYTES,
    RECORD_ID_PATTERN,
    get_records_dir,
)


class EvidenceImportConflict(ValueError):
    """Raised when an import would replace an existing evidence record."""


@dataclass(frozen=True)
class EvidenceImportResult:
    record_id: str
    validation: Mapping[str, Any]


def _import_record_id(record: Mapping[str, Any]) -> str:
    attempt_id = record.get("attemptId")
    if not isinstance(attempt_id, str) or not RECORD_ID_PATTERN.fullmatch(attempt_id):
        raise ValueError(
            "Imported attemptId must contain only letters, digits, hyphens, "
            "or underscores and be at most 200 characters"
        )
    return attempt_id


def _canonical_bytes(record: Mapping[str, Any]) -> bytes:
    try:
        encoded = (
            json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Imported evidence is not JSON serializable: {exc}") from exc
    if len(encoded) > MAX_RECORD_BYTES:
        raise ValueError(
            f"Imported evidence exceeds the {MAX_RECORD_BYTES}-byte limit"
        )
    return encoded


def _write_new_record(path: Path, content: bytes) -> None:
    created = False
    try:
        with path.open("xb") as output:
            created = True
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError as exc:
        raise EvidenceImportConflict(
            f"Evidence record '{path.stem}' already exists; imports never overwrite records"
        ) from exc
    except OSError as exc:
        if created:
            try:
                path.unlink()
            except OSError:
                pass
        raise ValueError(
            f"Evidence record '{path.stem}' could not be saved: {exc.strerror or exc}"
        ) from exc


def import_evidence_record(record: Mapping[str, Any]) -> EvidenceImportResult:
    """Validate and persist one new canonical record without overwriting data."""
    if not isinstance(record, Mapping):
        raise ValueError("Imported evidence must be a JSON object")

    record_id = _import_record_id(record)
    validation = build_validation_payload(record)
    content = _canonical_bytes(record)
    records_dir = get_records_dir()
    if not records_dir.is_dir():
        raise ValueError(f"Evidence records directory is unavailable: {records_dir}")

    _write_new_record(records_dir / f"{record_id}.json", content)
    return EvidenceImportResult(record_id=record_id, validation=validation)

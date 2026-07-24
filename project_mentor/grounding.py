"""Validate local-model answers and resolve citations to real evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from project_mentor.context_builder import EvidenceItem


class GroundingValidationError(ValueError):
    """Raised when a structured model answer is malformed."""


@dataclass(frozen=True)
class ValidatedGroundedAnswer:
    answer: str
    citations: tuple[EvidenceItem, ...]
    rejected_citation_ids: tuple[str, ...]
    evidence_insufficient: bool
    grounding_warning: str | None


def _clean_display_text(value: str) -> str:
    cleaned = "".join(
        character
        for character in value
        if character in "\n\r\t" or ord(character) >= 32
    ).strip()
    if not cleaned:
        raise GroundingValidationError("The local model returned an empty answer.")
    if len(cleaned) > 20_000:
        raise GroundingValidationError("The local model answer exceeded the display limit.")
    return cleaned


def validate_grounded_answer(
    raw_content: str,
    allowed_evidence: Mapping[str, EvidenceItem],
) -> ValidatedGroundedAnswer:
    try:
        payload: Any = json.loads(raw_content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise GroundingValidationError(
            "The local model did not return the required JSON answer."
        ) from exc
    if not isinstance(payload, dict):
        raise GroundingValidationError("The local model answer was not a JSON object.")
    answer = payload.get("answer")
    citation_ids = payload.get("citations")
    insufficient = payload.get("evidence_insufficient")
    if not isinstance(answer, str):
        raise GroundingValidationError("The local model answer field was not text.")
    if not isinstance(citation_ids, list) or not all(
        isinstance(item, str) for item in citation_ids
    ):
        raise GroundingValidationError(
            "The local model citations field was not a list of evidence IDs."
        )
    if not isinstance(insufficient, bool):
        raise GroundingValidationError(
            "The local model evidence_insufficient field was not true or false."
        )
    if len(citation_ids) > 50:
        raise GroundingValidationError("The local model returned too many citations.")

    unique_ids = list(dict.fromkeys(citation_ids))
    supported = tuple(
        allowed_evidence[item] for item in unique_ids if item in allowed_evidence
    )
    rejected = tuple(item for item in unique_ids if item not in allowed_evidence)
    evidence_insufficient = insufficient or not supported
    warning_parts: list[str] = []
    if rejected:
        warning_parts.append(
            f"Rejected {len(rejected)} citation(s) that were not in the supplied evidence."
        )
    if not supported:
        warning_parts.append("No supported evidence citation remained after validation.")
    cleaned_answer = _clean_display_text(answer)
    if evidence_insufficient and not cleaned_answer.casefold().startswith(
        "evidence is insufficient"
    ):
        cleaned_answer = "Evidence is insufficient to fully support this response. " + cleaned_answer
    return ValidatedGroundedAnswer(
        answer=cleaned_answer,
        citations=supported,
        rejected_citation_ids=rejected,
        evidence_insufficient=evidence_insufficient,
        grounding_warning=" ".join(warning_parts) or None,
    )

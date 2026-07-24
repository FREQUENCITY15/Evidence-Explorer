"""Deterministic data models for source-backed Debug investigations.

Debug data stays separate from Map and Teach so their stable export schemas do
not change when the Debug workflow evolves.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DebugEvidenceReference:
    evidence_id: str
    category: str
    kind: str
    file_path: str | None
    line_start: int | None
    line_end: int | None
    symbol_id: str | None


@dataclass(frozen=True)
class DebugEvidenceDetail:
    reference: DebugEvidenceReference
    content: str


@dataclass(frozen=True)
class DebugEvidenceGroup:
    heading: str
    summary: str
    details: tuple[DebugEvidenceDetail, ...]


@dataclass(frozen=True)
class DebugHypothesis:
    rank: int
    hypothesis_id: str
    title: str
    rationale: str
    confidence: str
    status: str
    references: tuple[DebugEvidenceReference, ...]


@dataclass(frozen=True)
class DebugDiagnosticStep:
    step_id: str
    hypothesis_id: str
    title: str
    instruction: str
    supported_when: str
    weakened_when: str
    safety: str
    references: tuple[DebugEvidenceReference, ...]


@dataclass(frozen=True)
class DebugInvestigation:
    debug_schema_version: str
    investigation_id: str
    failure_statement: str
    symbol_id: str
    symbol_kind: str
    file_path: str
    line_start: int
    line_end: int | None
    conclusion_status: str
    boundary_notice: str
    hypotheses: tuple[DebugHypothesis, ...]
    diagnostic_steps: tuple[DebugDiagnosticStep, ...]
    evidence_candidate_count: int
    evidence_included_count: int
    evidence_omitted_count: int
    evidence_references: tuple[DebugEvidenceReference, ...]
    evidence_groups: tuple[DebugEvidenceGroup, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-ready investigation structure."""

        return asdict(self)

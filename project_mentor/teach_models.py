"""Deterministic data models for Project Mentor Teach lessons.

Teach data is deliberately separate from the scan-report models so adding a
lesson API does not change the stable Map export schema.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TeachEvidenceReference:
    evidence_id: str
    category: str
    kind: str
    file_path: str | None
    line_start: int | None
    line_end: int | None
    symbol_id: str | None


@dataclass(frozen=True)
class TeachPrerequisite:
    title: str
    reason: str
    relationship: str
    learning_position: int | None
    references: tuple[TeachEvidenceReference, ...]


@dataclass(frozen=True)
class TeachSection:
    heading: str
    body: str
    certainty: str
    references: tuple[TeachEvidenceReference, ...]


@dataclass(frozen=True)
class TeachStage:
    number: int
    title: str
    explanation: str
    certainty: str
    references: tuple[TeachEvidenceReference, ...]


@dataclass(frozen=True)
class TeachVocabularyTerm:
    term: str
    definition: str
    reference: TeachEvidenceReference


@dataclass(frozen=True)
class TeachPredictionExercise:
    prompt: str
    expected_answer: str
    answer_explanation: str
    certainty: str
    references: tuple[TeachEvidenceReference, ...]


@dataclass(frozen=True)
class TeachQuizOption:
    option_id: str
    text: str


@dataclass(frozen=True)
class TeachQuizQuestion:
    question_id: str
    prompt: str
    options: tuple[TeachQuizOption, ...]
    correct_option_id: str
    answer_explanation: str
    references: tuple[TeachEvidenceReference, ...]


@dataclass(frozen=True)
class TeachEvidenceDetail:
    reference: TeachEvidenceReference
    content: str


@dataclass(frozen=True)
class TeachEvidenceGroup:
    heading: str
    summary: str
    details: tuple[TeachEvidenceDetail, ...]


@dataclass(frozen=True)
class TeachLesson:
    lesson_schema_version: str
    lesson_id: str
    title: str
    learning_objective: str
    symbol_id: str
    symbol_kind: str
    file_path: str
    line_start: int
    line_end: int | None
    prerequisites: tuple[TeachPrerequisite, ...]
    stages: tuple[TeachStage, ...]
    sections: tuple[TeachSection, ...]
    vocabulary: tuple[TeachVocabularyTerm, ...]
    prediction_exercise: TeachPredictionExercise
    quiz: tuple[TeachQuizQuestion, ...]
    uncertainty_labels: tuple[str, ...]
    evidence_candidate_count: int
    evidence_included_count: int
    evidence_omitted_count: int
    teaching_evidence_count: int
    evidence_references: tuple[TeachEvidenceReference, ...]
    evidence_groups: tuple[TeachEvidenceGroup, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-ready lesson structure."""

        return asdict(self)

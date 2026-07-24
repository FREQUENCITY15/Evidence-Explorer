"""Build bounded, deterministic Debug investigations from scan evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from project_mentor.context_builder import (
    ContextBuildError,
    EvidenceContextBuilder,
    EvidenceItem,
)
from project_mentor.debug_models import (
    DebugDiagnosticStep,
    DebugEvidenceDetail,
    DebugEvidenceGroup,
    DebugEvidenceReference,
    DebugHypothesis,
    DebugInvestigation,
)
from project_mentor.models import ProjectAnalysis, SymbolDefinition


DEBUG_SCHEMA_VERSION = "1.0.0"
TRACEABLE_KINDS = {"function", "async_function", "method", "async_method"}
MAX_DEBUG_EVIDENCE = 12
MAX_HYPOTHESES = 4
DEBUG_EVIDENCE_CHARS = 16_000


class DebugInvestigationError(ValueError):
    """A requested investigation cannot be built safely from the scan."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DebugInvestigationBundle:
    investigation: DebugInvestigation
    evidence_items: tuple[EvidenceItem, ...]


def _reference(item: EvidenceItem) -> DebugEvidenceReference:
    return DebugEvidenceReference(
        evidence_id=item.evidence_id,
        category=item.category,
        kind=item.kind,
        file_path=item.file_path,
        line_start=item.line_start,
        line_end=item.line_end,
        symbol_id=item.symbol_id,
    )


def _bounded(text: str, limit: int = 500) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _items_of_kind(items: tuple[EvidenceItem, ...], *kinds: str) -> list[EvidenceItem]:
    wanted = set(kinds)
    return [item for item in items if item.kind in wanted]


def _first_reference(items: tuple[EvidenceItem, ...]) -> tuple[DebugEvidenceReference, ...]:
    if not items:
        return ()
    return (_reference(items[0]),)


def _refs(items: list[EvidenceItem], fallback: tuple[EvidenceItem, ...]) -> tuple[DebugEvidenceReference, ...]:
    chosen = items[:2] or list(fallback[:1])
    return tuple(_reference(item) for item in chosen)


class DebugInvestigationService:
    """Create reproducible investigations without executing code or using Ollama."""

    def __init__(self) -> None:
        self._context_builder = EvidenceContextBuilder(DEBUG_EVIDENCE_CHARS)

    @staticmethod
    def _selected_symbol(
        analysis: ProjectAnalysis, symbol_id: str
    ) -> SymbolDefinition:
        symbol = next(
            (item for item in analysis.symbols if item.symbol_id == symbol_id), None
        )
        if symbol is None:
            raise DebugInvestigationError(
                "symbol_not_found",
                "The selected symbol is not present in this scan's evidence.",
            )
        if symbol.kind not in TRACEABLE_KINDS:
            raise DebugInvestigationError(
                "unsupported_symbol_kind",
                "Debug investigations currently support functions and methods only.",
            )
        return symbol

    @staticmethod
    def _failure_statement(value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise DebugInvestigationError(
                "missing_failure_statement", "Describe the failure you observed."
            )
        if len(cleaned) > 2_000:
            raise DebugInvestigationError(
                "failure_statement_too_long",
                "The failure description must be 2,000 characters or fewer.",
            )
        return cleaned

    @staticmethod
    def _hypothesis_specs(
        evidence: tuple[EvidenceItem, ...]
    ) -> list[tuple[str, str, str, list[EvidenceItem]]]:
        parameters = _items_of_kind(evidence, "parameter")
        exceptions = _items_of_kind(
            evidence, "raise_site", "exception_path", "error_propagation"
        )
        calls = _items_of_kind(evidence, "call_relationship")
        state = _items_of_kind(evidence, "mutation_site", "data_flow")
        outputs = _items_of_kind(evidence, "output_site")
        specs: list[tuple[str, str, str, list[EvidenceItem]]] = []
        if parameters:
            specs.append(
                (
                    "Unexpected input reaches the selected symbol",
                    "The source declares inputs, but static analysis cannot reveal their runtime values or whether callers satisfy the intended assumptions.",
                    "possible",
                    parameters,
                )
            )
        if exceptions:
            specs.append(
                (
                    "An exception path is reached",
                    "The scan found explicit or conservatively inferred exception evidence. It does not prove that this path occurred in the reported failure.",
                    "possible",
                    exceptions,
                )
            )
        if calls:
            specs.append(
                (
                    "A dependency call behaves differently at runtime",
                    "The selected symbol calls another target. Static call evidence cannot establish the returned value, side effects, or runtime exception.",
                    "possible",
                    calls,
                )
            )
        if state:
            specs.append(
                (
                    "A state or data transformation differs from expectation",
                    "The scan recorded a mutation or conservative data-flow relationship, while the concrete runtime value remains unknown.",
                    "possible",
                    state,
                )
            )
        if outputs:
            specs.append(
                (
                    "The selected output site produces an unexpected value",
                    "The source contains a return or yield site, but static evidence cannot prove the value produced for the failing input.",
                    "possible",
                    outputs,
                )
            )
        if not specs:
            specs.append(
                (
                    "The failure depends on runtime behavior not captured by the scan",
                    "The selected source definition is known, but the scan contains no stronger input, call, state, output, or exception lead.",
                    "uncertain",
                    list(evidence[:1]),
                )
            )
        return specs[:MAX_HYPOTHESES]

    @staticmethod
    def _diagnostic(
        rank: int,
        hypothesis_id: str,
        title: str,
        references: tuple[DebugEvidenceReference, ...],
    ) -> DebugDiagnosticStep:
        instructions = {
            "Unexpected input reaches the selected symbol": (
                "Reproduce once and record the selected function's input values immediately before it begins. Compare them with the input you expected.",
                "At least one recorded input differs from the expected type, shape, range, or value.",
                "The recorded inputs match the expected values for the same reproduction.",
            ),
            "An exception path is reached": (
                "Reproduce once and capture the exact exception type, message, and first traceback line inside the selected symbol.",
                "The traceback reaches one of the cited exception locations or an unprotected cited call.",
                "No exception occurs, or the traceback points to a different location.",
            ),
            "A dependency call behaves differently at runtime": (
                "Record the cited dependency call's returned value or raised exception for one failing reproduction.",
                "The call returns an unexpected value, changes unexpected state, or raises.",
                "The call result and side effects match the expected contract.",
            ),
            "A state or data transformation differs from expectation": (
                "Compare the cited target value immediately before and after the recorded assignment or mutation during one reproduction.",
                "The after-value differs from the expected transformation.",
                "The before/after values match the expected transformation.",
            ),
            "The selected output site produces an unexpected value": (
                "Record the value produced at the cited return or yield site for one failing reproduction.",
                "The recorded output differs from the expected value.",
                "The output matches expectation, so investigation should move to its caller.",
            ),
        }
        instruction, supported, weakened = instructions.get(
            title,
            (
                "Reproduce once and record the first observable point where actual behavior differs from expected behavior.",
                "The first difference occurs inside the selected symbol.",
                "The selected symbol's observable behavior matches expectation.",
            ),
        )
        return DebugDiagnosticStep(
            step_id=f"TEST-{rank}",
            hypothesis_id=hypothesis_id,
            title=f"Test hypothesis {rank} with one focused observation",
            instruction=instruction,
            supported_when=supported,
            weakened_when=weakened,
            safety="manual_observation_only; no command or repository edit was performed",
            references=references,
        )

    @staticmethod
    def _groups(evidence: tuple[EvidenceItem, ...]) -> tuple[DebugEvidenceGroup, ...]:
        groups: list[DebugEvidenceGroup] = []
        for category, heading in (
            ("observed_fact", "Observed source facts"),
            ("project_mentor_inference", "Project Mentor inferences"),
        ):
            selected = [item for item in evidence if item.category == category]
            if selected:
                groups.append(
                    DebugEvidenceGroup(
                        heading=heading,
                        summary=(
                            "Facts recorded directly from Python source."
                            if category == "observed_fact"
                            else "Conservative static relationships; these are not runtime proof."
                        ),
                        details=tuple(
                            DebugEvidenceDetail(
                                reference=_reference(item), content=item.content
                            )
                            for item in selected
                        ),
                    )
                )
        return tuple(groups)

    def build(
        self,
        analysis: ProjectAnalysis,
        symbol_id: str,
        failure_statement: str,
    ) -> DebugInvestigationBundle:
        symbol = self._selected_symbol(analysis, symbol_id.strip())
        failure = self._failure_statement(failure_statement)
        try:
            context = self._context_builder.build(
                analysis,
                question=failure,
                selected_symbol_id=symbol.symbol_id,
                workflow="debug",
            )
        except (ContextBuildError, OSError) as exc:
            raise DebugInvestigationError("evidence_unavailable", str(exc)) from exc

        evidence = tuple(context.evidence_items[:MAX_DEBUG_EVIDENCE])
        if not evidence:
            raise DebugInvestigationError(
                "evidence_unavailable",
                "No bounded evidence is available for this investigation.",
            )
        allowed_ids = {item.evidence_id for item in evidence}
        hypotheses: list[DebugHypothesis] = []
        diagnostics: list[DebugDiagnosticStep] = []
        for rank, (title, rationale, confidence, supporting) in enumerate(
            self._hypothesis_specs(evidence), start=1
        ):
            references = _refs(
                [item for item in supporting if item.evidence_id in allowed_ids],
                evidence,
            )
            hypothesis_id = f"HYP-{rank}"
            hypotheses.append(
                DebugHypothesis(
                    rank=rank,
                    hypothesis_id=hypothesis_id,
                    title=title,
                    rationale=_bounded(rationale),
                    confidence=confidence,
                    status="unverified",
                    references=references,
                )
            )
            diagnostics.append(
                self._diagnostic(rank, hypothesis_id, title, references)
            )

        canonical = json.dumps(
            [
                DEBUG_SCHEMA_VERSION,
                symbol.symbol_id,
                failure,
                [item.evidence_id for item in evidence],
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        investigation_id = "DEBUG-" + hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()[:12].upper()
        all_references = tuple(_reference(item) for item in evidence)
        cited_ids = {
            reference.evidence_id
            for item in (*hypotheses, *diagnostics)
            for reference in item.references
        }
        if not cited_ids.issubset(allowed_ids):
            raise DebugInvestigationError(
                "citation_validation_failed",
                "The investigation produced a citation outside its evidence allow-list.",
            )

        investigation = DebugInvestigation(
            debug_schema_version=DEBUG_SCHEMA_VERSION,
            investigation_id=investigation_id,
            failure_statement=failure,
            symbol_id=symbol.symbol_id,
            symbol_kind=symbol.kind,
            file_path=symbol.file_path,
            line_start=symbol.line,
            line_end=symbol.end_line,
            conclusion_status="root_cause_not_established",
            boundary_notice=(
                "This investigation ranks source-backed possibilities only. "
                "It did not run code, execute diagnostics, edit files, or contact Ollama."
            ),
            hypotheses=tuple(hypotheses),
            diagnostic_steps=tuple(diagnostics),
            evidence_candidate_count=context.candidate_count,
            evidence_included_count=len(evidence),
            evidence_omitted_count=max(0, context.candidate_count - len(evidence)),
            evidence_references=all_references,
            evidence_groups=self._groups(evidence),
        )
        return DebugInvestigationBundle(
            investigation=investigation, evidence_items=evidence
        )

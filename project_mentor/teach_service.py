"""Build concise deterministic lessons from trusted Project Mentor evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath

from project_mentor.context_builder import EvidenceItem, make_evidence_item
from project_mentor.models import (
    CallRelationship,
    DataFlowRelationship,
    ErrorPropagationEvidence,
    FunctionEvidence,
    ImportEdge,
    ProjectAnalysis,
    SymbolDefinition,
)
from project_mentor.teach_models import (
    TeachEvidenceDetail,
    TeachEvidenceGroup,
    TeachEvidenceReference,
    TeachLesson,
    TeachPredictionExercise,
    TeachPrerequisite,
    TeachQuizOption,
    TeachQuizQuestion,
    TeachSection,
    TeachStage,
    TeachVocabularyTerm,
)


TEACH_LESSON_SCHEMA_VERSION = "1.1.0"
TRACEABLE_KINDS = {"function", "async_function", "method", "async_method"}

# Technical evidence remains bounded for unusually large source files. These are
# inspector/export limits, not the much smaller default teaching budget.
MAX_PARAMETERS = 24
MAX_OUTPUTS = 24
MAX_MUTATIONS = 24
MAX_RAISES = 16
MAX_EXCEPTION_PATHS = 24
MAX_CALLS = 32
MAX_DATA_FLOWS = 32
MAX_ERROR_RECORDS = 32
MAX_IMPORTS = 16
MAX_TEACHING_EVIDENCE = 12
MAX_PREREQUISITES = 5

LOW_TEACHING_VALUE_CALLS = {
    "bool",
    "dict",
    "enumerate",
    "float",
    "int",
    "len",
    "list",
    "max",
    "min",
    "next",
    "Path",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "ValueError",
    "zip",
}


class TeachLessonError(ValueError):
    """A requested deterministic lesson cannot be built from the scan."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TeachLessonBundle:
    lesson: TeachLesson
    # Only this small, prioritised allow-list may reach the optional model.
    evidence_items: tuple[EvidenceItem, ...]


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _reference(item: EvidenceItem) -> TeachEvidenceReference:
    return TeachEvidenceReference(
        evidence_id=item.evidence_id,
        category=item.category,
        kind=item.kind,
        file_path=item.file_path,
        line_start=item.line_start,
        line_end=item.line_end,
        symbol_id=item.symbol_id,
    )


def _record_item(
    category: str,
    kind: str,
    record: object,
    *,
    file_path: str,
    symbol_id: str,
) -> EvidenceItem:
    values = asdict(record)
    line = values.get("line")
    record_path = values.get("file_path")
    return make_evidence_item(
        category,
        kind,
        _compact(values),
        file_path=record_path if isinstance(record_path, str) else file_path,
        line_start=line if isinstance(line, int) else None,
        line_end=line if isinstance(line, int) else None,
        symbol_id=symbol_id,
    )


def _bounded(text: str, limit: int = 700) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _join_names(values: list[str], *, limit: int = 6) -> str:
    unique = list(dict.fromkeys(value for value in values if value))
    shown = unique[:limit]
    if not shown:
        return "none"
    result = ", ".join(shown)
    if len(unique) > len(shown):
        result += f", and {len(unique) - len(shown)} more"
    return result


def _return_annotation(signature: str | None) -> str | None:
    if not signature or "->" not in signature:
        return None
    annotation = signature.rsplit("->", 1)[1].strip()
    return _bounded(annotation, 120) or None


def _leading_call(expression: str | None) -> str | None:
    if not expression:
        return None
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\(", expression)
    return match.group(1) if match else None


def _exception_name(expression: str | None) -> str:
    return _leading_call(expression) or "the current exception"


def _expression_summary(expression: str | None) -> str:
    if not expression:
        return "no expression"
    call = _leading_call(expression)
    if call and len(expression) > 100:
        return f"a value constructed with {call}(...)"
    if len(expression) > 120:
        return _bounded(expression, 117)
    return expression


def _deduplicate(items: list[EvidenceItem]) -> list[EvidenceItem]:
    result: list[EvidenceItem] = []
    seen: set[str] = set()
    for item in items:
        if item.evidence_id not in seen:
            result.append(item)
            seen.add(item.evidence_id)
    return result


def _spread_calls(
    pairs: list[tuple[CallRelationship, EvidenceItem]], limit: int
) -> list[tuple[CallRelationship, EvidenceItem]]:
    """Keep early orchestration calls and final analysis calls deterministically."""

    if len(pairs) <= limit:
        return pairs
    if limit <= 2:
        return pairs[:limit]
    return pairs[: limit - 2] + pairs[-2:]


def _refs(items: list[EvidenceItem], allowed_ids: set[str]) -> tuple[TeachEvidenceReference, ...]:
    return tuple(_reference(item) for item in items if item.evidence_id in allowed_ids)


def _evidence_group(
    heading: str, summary: str, items: list[EvidenceItem]
) -> TeachEvidenceGroup | None:
    if not items:
        return None
    return TeachEvidenceGroup(
        heading=heading,
        summary=summary,
        details=tuple(
            TeachEvidenceDetail(reference=_reference(item), content=item.content)
            for item in items
        ),
    )


class TeachLessonService:
    """Create reproducible lessons without importing, executing, or using an LLM."""

    @staticmethod
    def _selected_symbol(
        analysis: ProjectAnalysis, symbol_id: str
    ) -> SymbolDefinition:
        symbol = next(
            (item for item in analysis.symbols if item.symbol_id == symbol_id), None
        )
        if symbol is None:
            raise TeachLessonError(
                "symbol_not_found",
                "The selected symbol is not present in this scan's evidence.",
            )
        if symbol.kind not in TRACEABLE_KINDS:
            raise TeachLessonError(
                "unsupported_symbol_kind",
                "Teach lessons currently support functions and methods only.",
            )
        return symbol

    @staticmethod
    def _function_evidence(
        analysis: ProjectAnalysis, symbol: SymbolDefinition
    ) -> FunctionEvidence:
        return next(
            (
                item
                for item in analysis.function_evidence
                if item.symbol_id == symbol.symbol_id
            ),
            FunctionEvidence(symbol_id=symbol.symbol_id, file_path=symbol.file_path),
        )

    @staticmethod
    def _ordered_calls(
        analysis: ProjectAnalysis, symbol: SymbolDefinition
    ) -> list[CallRelationship]:
        return sorted(
            (
                item
                for item in analysis.call_relationships
                if item.caller_symbol_id == symbol.symbol_id
            ),
            key=lambda item: (
                item.file_path,
                item.line,
                item.column,
                item.target_expression,
                item.resolved_target_symbol_id or "",
            ),
        )

    @staticmethod
    def _ordered_flows(
        analysis: ProjectAnalysis, symbol: SymbolDefinition
    ) -> list[DataFlowRelationship]:
        return sorted(
            (
                item
                for item in analysis.data_flows
                if item.function_symbol_id == symbol.symbol_id
            ),
            key=lambda item: (
                item.file_path,
                item.line,
                item.column,
                item.target_expression,
                item.source_expression,
            ),
        )

    @staticmethod
    def _ordered_errors(
        analysis: ProjectAnalysis, symbol: SymbolDefinition
    ) -> list[ErrorPropagationEvidence]:
        return sorted(
            (
                item
                for item in analysis.error_propagation
                if item.caller_symbol_id == symbol.symbol_id
            ),
            key=lambda item: (
                item.file_path,
                item.line,
                item.column,
                item.target_expression,
            ),
        )

    @staticmethod
    def _ordered_imports(
        analysis: ProjectAnalysis, symbol: SymbolDefinition
    ) -> list[ImportEdge]:
        return sorted(
            (
                item
                for item in analysis.import_edges
                if item.source_path == symbol.file_path
            ),
            key=lambda item: (
                item.target_path,
                item.target_module,
                item.source_module,
            ),
        )

    @staticmethod
    def _lesson_id(
        symbol_id: str, evidence_items: list[EvidenceItem], candidate_count: int
    ) -> str:
        canonical = _compact(
            {
                "lesson_schema_version": TEACH_LESSON_SCHEMA_VERSION,
                "symbol_id": symbol_id,
                "evidence_ids": [item.evidence_id for item in evidence_items],
                "candidate_count": candidate_count,
            }
        )
        return "LESSON-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[
            :16
        ].upper()

    def build(self, analysis: ProjectAnalysis, symbol_id: str) -> TeachLessonBundle:
        symbol = self._selected_symbol(analysis, symbol_id)
        raw_function_evidence = self._function_evidence(analysis, symbol)
        raw_calls = self._ordered_calls(analysis, symbol)
        raw_flows = self._ordered_flows(analysis, symbol)
        raw_errors = self._ordered_errors(analysis, symbol)
        raw_imports = self._ordered_imports(analysis, symbol)
        candidate_count = 1 + sum(
            (
                len(raw_function_evidence.parameters),
                len(raw_function_evidence.output_sites),
                len(raw_function_evidence.mutations),
                len(raw_function_evidence.raise_sites),
                len(raw_function_evidence.exception_paths),
                len(raw_calls),
                len(raw_flows),
                len(raw_errors),
                len(raw_imports),
            )
        )

        function_evidence = FunctionEvidence(
            symbol_id=raw_function_evidence.symbol_id,
            file_path=raw_function_evidence.file_path,
            parameters=raw_function_evidence.parameters[:MAX_PARAMETERS],
            output_sites=raw_function_evidence.output_sites[:MAX_OUTPUTS],
            mutations=raw_function_evidence.mutations[:MAX_MUTATIONS],
            raise_sites=raw_function_evidence.raise_sites[:MAX_RAISES],
            exception_paths=raw_function_evidence.exception_paths[:MAX_EXCEPTION_PATHS],
        )
        calls = raw_calls[:MAX_CALLS]
        flows = raw_flows[:MAX_DATA_FLOWS]
        errors = raw_errors[:MAX_ERROR_RECORDS]
        imports = raw_imports[:MAX_IMPORTS]

        symbol_item = make_evidence_item(
            "observed_fact",
            "symbol_definition",
            _compact(asdict(symbol)),
            file_path=symbol.file_path,
            line_start=symbol.line,
            line_end=symbol.end_line or symbol.line,
            symbol_id=symbol.symbol_id,
        )
        parameter_items = [
            _record_item(
                "observed_fact",
                "parameter",
                item,
                file_path=symbol.file_path,
                symbol_id=symbol.symbol_id,
            )
            for item in function_evidence.parameters
        ]
        output_items = [
            _record_item(
                "observed_fact",
                "output_site",
                item,
                file_path=symbol.file_path,
                symbol_id=symbol.symbol_id,
            )
            for item in function_evidence.output_sites
        ]
        mutation_items = [
            _record_item(
                "observed_fact",
                "mutation_site",
                item,
                file_path=symbol.file_path,
                symbol_id=symbol.symbol_id,
            )
            for item in function_evidence.mutations
        ]
        raise_items = [
            _record_item(
                "observed_fact",
                "raise_site",
                item,
                file_path=symbol.file_path,
                symbol_id=symbol.symbol_id,
            )
            for item in function_evidence.raise_sites
        ]
        exception_items = [
            _record_item(
                "observed_fact",
                "exception_path",
                item,
                file_path=symbol.file_path,
                symbol_id=symbol.symbol_id,
            )
            for item in function_evidence.exception_paths
        ]
        call_items = [
            _record_item(
                "project_mentor_inference",
                "call_relationship",
                item,
                file_path=symbol.file_path,
                symbol_id=symbol.symbol_id,
            )
            for item in calls
        ]
        flow_items = [
            _record_item(
                "project_mentor_inference",
                "data_flow",
                item,
                file_path=symbol.file_path,
                symbol_id=symbol.symbol_id,
            )
            for item in flows
        ]
        error_items = [
            _record_item(
                "project_mentor_inference",
                "error_propagation",
                item,
                file_path=symbol.file_path,
                symbol_id=symbol.symbol_id,
            )
            for item in errors
        ]
        import_items = [
            make_evidence_item(
                "project_mentor_inference",
                "import_relationship",
                _compact(asdict(item)),
                file_path=item.source_path,
                symbol_id=symbol.symbol_id,
            )
            for item in imports
        ]

        technical_items = _deduplicate(
            [symbol_item]
            + parameter_items
            + output_items
            + mutation_items
            + raise_items
            + exception_items
            + call_items
            + flow_items
            + error_items
            + import_items
        )
        omitted_count = max(0, candidate_count - len(technical_items))

        # Build a small, deterministic teaching allow-list. Exact technical records
        # remain in evidence_groups, but routine built-ins cannot crowd out calls that
        # explain the selected function's architecture.
        teaching_items: list[EvidenceItem] = [symbol_item]
        teaching_items.extend(parameter_items[:4])
        teaching_items.extend(raise_items[:2])
        teaching_items.extend(mutation_items[:2])

        resolved_pairs = [
            (call, item)
            for call, item in zip(calls, call_items)
            if call.resolved_target_symbol_id
        ]
        remaining_for_calls = max(
            0,
            MAX_TEACHING_EVIDENCE
            - len(_deduplicate(teaching_items))
            - (1 if output_items else 0),
        )
        selected_resolved_pairs = _spread_calls(resolved_pairs, remaining_for_calls)
        teaching_items.extend(item for _, item in selected_resolved_pairs)
        teaching_items.extend(output_items[:1])

        for collection in (
            exception_items[:1],
            flow_items[:2],
            [
                item
                for error, item in zip(errors, error_items)
                if error.protected_by_try_line is not None or error.target_raise_lines
            ][:1],
            [
                item
                for call, item in zip(calls, call_items)
                if not call.resolved_target_symbol_id
                and call.target_expression not in LOW_TEACHING_VALUE_CALLS
            ][:1],
        ):
            if len(_deduplicate(teaching_items)) >= MAX_TEACHING_EVIDENCE:
                break
            teaching_items.extend(collection)
        teaching_items = _deduplicate(teaching_items)[:MAX_TEACHING_EVIDENCE]
        teaching_ids = {item.evidence_id for item in teaching_items}

        learning_positions = {
            item.path: item.position for item in analysis.learning_order
        }
        symbols_by_id = {item.symbol_id: item for item in analysis.symbols}
        empty_markers = {
            item.path for item in analysis.files if item.is_empty_package_marker
        }
        prerequisites: list[TeachPrerequisite] = []
        seen_targets: set[str] = set()
        for call, call_item in resolved_pairs:
            target = symbols_by_id.get(call.resolved_target_symbol_id or "")
            if (
                target is None
                or target.symbol_id == symbol.symbol_id
                or target.symbol_id in seen_targets
                or target.file_path in empty_markers
                or PurePosixPath(target.file_path).name == "__init__.py"
            ):
                continue
            seen_targets.add(target.symbol_id)
            prerequisites.append(
                TeachPrerequisite(
                    title=target.symbol_id,
                    reason=(
                        f"This supporting project function is called at line {call.line}. "
                        "Reading it may help explain one step of the selected function."
                    ),
                    relationship="resolved_internal_call",
                    learning_position=learning_positions.get(target.file_path),
                    references=(_reference(call_item),),
                )
            )
            if len(prerequisites) >= MAX_PREREQUISITES:
                break

        parameters = function_evidence.parameters
        parameter_names = [item.name for item in parameters]
        return_annotation = _return_annotation(symbol.signature)
        resolved_calls = [item for item in calls if item.resolved_target_symbol_id]
        unresolved_calls = [item for item in calls if not item.resolved_target_symbol_id]
        selected_call_records = [item for item, _ in selected_resolved_pairs]

        stage_values: list[
            tuple[str, str, str, tuple[TeachEvidenceReference, ...]]
        ] = []
        if parameters:
            stage_values.append(
                (
                    "Receive the inputs",
                    _bounded(
                        f"The function receives {_join_names(parameter_names)} through its recorded signature."
                    ),
                    "observed_source",
                    _refs(parameter_items, teaching_ids) or (_reference(symbol_item),),
                )
            )
        if function_evidence.raise_sites or function_evidence.exception_paths:
            exception_names = [
                _exception_name(item.exception_expression)
                for item in function_evidence.raise_sites
            ]
            raise_lines = [str(item.line) for item in function_evidence.raise_sites]
            explanation = (
                f"The source records {_join_names(exception_names)} raise site(s)"
                + (f" at line(s) {', '.join(raise_lines)}" if raise_lines else "")
                + f" and {len(function_evidence.exception_paths)} try/handler path record(s)."
            )
            stage_values.append(
                (
                    "Check explicit error paths",
                    _bounded(explanation),
                    "observed_source_with_runtime_uncertainty",
                    _refs(raise_items + exception_items, teaching_ids)
                    or (_reference(symbol_item),),
                )
            )

        if selected_call_records:
            midpoint = (len(selected_call_records) + 1) // 2
            call_chunks = [selected_call_records[:midpoint]]
            if selected_call_records[midpoint:]:
                call_chunks.append(selected_call_records[midpoint:])
            for index, chunk in enumerate(call_chunks):
                call_text = "; ".join(
                    f"{item.target_expression} at line {item.line}" for item in chunk
                )
                stage_values.append(
                    (
                        "Run supporting project operations"
                        if index == 0
                        else "Continue through supporting operations",
                        _bounded(
                            f"Project Mentor conservatively resolves these internal calls: {call_text}."
                        ),
                        "project_mentor_inference",
                        _refs(
                            [
                                item
                                for call, item in selected_resolved_pairs
                                if call in chunk
                            ],
                            teaching_ids,
                        ),
                    )
                )

        selected_mutations = mutation_items[:2]
        selected_flows = flow_items[:2]
        if selected_mutations or selected_flows:
            pieces: list[str] = []
            if function_evidence.mutations:
                pieces.append(
                    f"{len(function_evidence.mutations)} source-observed state change(s)"
                )
            if flows:
                pieces.append(f"{len(flows)} conservative assignment flow(s)")
            stage_values.append(
                (
                    "Build or update intermediate values",
                    _bounded("The scan records " + " and ".join(pieces) + "."),
                    "mixed_static_evidence",
                    _refs(selected_mutations + selected_flows, teaching_ids)
                    or (_reference(symbol_item),),
                )
            )

        if function_evidence.output_sites:
            output = function_evidence.output_sites[0]
            stage_values.append(
                (
                    "Return or yield the result",
                    _bounded(
                        f"At line {output.line}, the source records a {output.kind.replace('_', ' ')} using {_expression_summary(output.expression)}."
                    ),
                    "observed_source_with_runtime_uncertainty",
                    _refs(output_items[:1], teaching_ids) or (_reference(symbol_item),),
                )
            )
        if not stage_values:
            stage_values.append(
                (
                    "Locate the definition",
                    f"The source defines {symbol.symbol_id} at line {symbol.line}.",
                    "observed_source",
                    (_reference(symbol_item),),
                )
            )
        stages = tuple(
            TeachStage(
                number=index,
                title=title,
                explanation=explanation,
                certainty=certainty,
                references=references,
            )
            for index, (title, explanation, certainty, references) in enumerate(
                stage_values, start=1
            )
        )

        kind_label = symbol.kind.replace("_", " ")
        purpose_parts = [
            f"The source defines the {kind_label} {symbol.qualified_name}."
        ]
        if parameters:
            purpose_parts.append(f"It receives {_join_names(parameter_names)}.")
        if return_annotation:
            purpose_parts.append(
                f"Its signature records {return_annotation} as the return annotation."
            )
        if resolved_calls:
            purpose_parts.append(
                f"The bounded lesson evidence contains {len(resolved_calls)} conservatively resolved internal call(s)."
            )

        input_details = []
        for item in parameters[:6]:
            detail = item.name
            if item.annotation:
                detail += f" ({item.annotation})"
            input_details.append(detail)
        if len(parameters) > len(input_details):
            input_details.append(f"{len(parameters) - len(input_details)} additional parameter(s)")
        if function_evidence.output_sites:
            output = function_evidence.output_sites[0]
            output_text = (
                f"The first explicit {output.kind.replace('_', ' ')} site is at line "
                f"{output.line} and uses {_expression_summary(output.expression)}."
            )
        else:
            output_text = "No explicit return or yield site was recorded."

        selected_call_names = [
            item.resolved_target_symbol_id or item.target_expression
            for item in selected_call_records
        ]
        relationship_text = (
            f"Within {len(calls)} bounded call record(s), {len(resolved_calls)} resolve to "
            f"visible project symbols and {len(unresolved_calls)} remain unresolved."
        )
        if selected_call_names:
            relationship_text += (
                " Key supporting calls include "
                + _join_names(selected_call_names, limit=7)
                + "."
            )
        if flows:
            relationship_text += (
                f" It also records {len(flows)} conservative data-flow relationship(s)."
            )

        error_parts: list[str] = []
        if function_evidence.raise_sites:
            error_parts.append(
                f"{len(function_evidence.raise_sites)} explicit raise site(s): "
                + _join_names(
                    [
                        _exception_name(item.exception_expression)
                        for item in function_evidence.raise_sites
                    ]
                )
            )
        if function_evidence.exception_paths:
            error_parts.append(
                f"{len(function_evidence.exception_paths)} recorded try/handler path(s)"
            )
        if errors:
            distinct_reasons = len({item.reason for item in errors})
            error_parts.append(
                f"{len(errors)} bounded call-error record(s), grouped into {distinct_reasons} reason pattern(s)"
            )
        error_text = "; ".join(error_parts) if error_parts else "No explicit state or error evidence was recorded."
        if errors or function_evidence.exception_paths:
            error_text += " These static records do not prove which runtime path executes."

        sections = (
            TeachSection(
                heading="Purpose",
                body=_bounded(" ".join(purpose_parts)),
                certainty="mixed_static_evidence" if resolved_calls else "observed_source",
                references=(_reference(symbol_item),)
                + _refs(
                    [item for _, item in selected_resolved_pairs], teaching_ids
                ),
            ),
            TeachSection(
                heading="Inputs and output",
                body=_bounded(
                    (
                        "Recorded inputs: " + ", ".join(input_details) + ". "
                        if input_details
                        else "The scanner recorded no parameters. "
                    )
                    + output_text
                ),
                certainty="observed_source",
                references=_refs(parameter_items + output_items[:1], teaching_ids)
                or (_reference(symbol_item),),
            ),
            TeachSection(
                heading="Calls and data movement",
                body=_bounded(relationship_text),
                certainty="project_mentor_inference" if calls or flows else "static_limit",
                references=_refs(
                    [item for _, item in selected_resolved_pairs] + flow_items[:2],
                    teaching_ids,
                )
                or (_reference(symbol_item),),
            ),
            TeachSection(
                heading="Errors and runtime boundary",
                body=_bounded(error_text),
                certainty=(
                    "mixed_static_evidence"
                    if errors
                    else "observed_source"
                    if function_evidence.raise_sites or function_evidence.exception_paths
                    else "static_limit"
                ),
                references=_refs(raise_items + exception_items[:1], teaching_ids)
                or (_reference(symbol_item),),
            ),
        )

        vocabulary: list[TeachVocabularyTerm] = [
            TeachVocabularyTerm(
                term=kind_label,
                definition="A named block of Python code recorded directly from its source definition.",
                reference=_reference(symbol_item),
            )
        ]
        if parameter_items:
            vocabulary.append(
                TeachVocabularyTerm(
                    term="parameter",
                    definition="A named input declared by a function or method.",
                    reference=_reference(parameter_items[0]),
                )
            )
        if output_items:
            vocabulary.append(
                TeachVocabularyTerm(
                    term="return or yield site",
                    definition="A source location that explicitly returns or yields an expression.",
                    reference=_reference(output_items[0]),
                )
            )
        if selected_resolved_pairs:
            vocabulary.append(
                TeachVocabularyTerm(
                    term="resolved internal call",
                    definition="A cautious link from a call expression to a definition visible inside the scanned project.",
                    reference=_reference(selected_resolved_pairs[0][1]),
                )
            )
        if raise_items or exception_items:
            vocabulary.append(
                TeachVocabularyTerm(
                    term="exception path",
                    definition="Source evidence related to raising, catching, or finalising an error path.",
                    reference=_reference((raise_items + exception_items)[0]),
                )
            )

        if function_evidence.raise_sites:
            raised = function_evidence.raise_sites[0]
            raised_name = _exception_name(raised.exception_expression)
            exercise = TeachPredictionExercise(
                prompt=(
                    f"If execution reaches the explicit error branch at line {raised.line}, "
                    "what source-level action is recorded?"
                ),
                expected_answer=f"Raise {raised_name} at line {raised.line}.",
                answer_explanation=(
                    "The raise statement is directly visible in source. Static analysis does "
                    "not prove that execution reaches this branch."
                ),
                certainty="observed_source_with_runtime_uncertainty",
                references=(_reference(raise_items[0]),),
            )
        elif selected_resolved_pairs:
            call, call_item = selected_resolved_pairs[0]
            exercise = TeachPredictionExercise(
                prompt=(
                    f"When the source reaches line {call.line}, which supporting project "
                    "function does Project Mentor resolve?"
                ),
                expected_answer=call.resolved_target_symbol_id or call.target_expression,
                answer_explanation=(
                    "The call relationship is a conservative static resolution, not proof of "
                    "runtime dispatch."
                ),
                certainty="project_mentor_inference",
                references=(_reference(call_item),),
            )
        elif function_evidence.mutations:
            mutation = function_evidence.mutations[0]
            exercise = TeachPredictionExercise(
                prompt=(
                    f"If execution reaches line {mutation.line}, which target does the "
                    "recorded state change write to?"
                ),
                expected_answer=mutation.target_expression,
                answer_explanation=(
                    "The target is present in source, while runtime execution remains unknown."
                ),
                certainty="observed_source_with_runtime_uncertainty",
                references=(_reference(mutation_items[0]),),
            )
        elif function_evidence.output_sites:
            output = function_evidence.output_sites[0]
            exercise = TeachPredictionExercise(
                prompt=(
                    f"What broad result does the recorded {output.kind.replace('_', ' ')} "
                    f"site at line {output.line} use?"
                ),
                expected_answer=_expression_summary(output.expression),
                answer_explanation=(
                    "The answer summarises the explicit source expression instead of asking "
                    "you to memorise it."
                ),
                certainty="observed_source_with_runtime_uncertainty",
                references=(_reference(output_items[0]),),
            )
        else:
            exercise = TeachPredictionExercise(
                prompt="What can Project Mentor prove about this definition without running it?",
                expected_answer=(
                    f"It can prove that {symbol.symbol_id} is defined in {symbol.file_path} "
                    f"at line {symbol.line}."
                ),
                answer_explanation=(
                    "Definition syntax is observable in source, while runtime behaviour is not."
                ),
                certainty="observed_source",
                references=(_reference(symbol_item),),
            )

        if return_annotation:
            question_one = TeachQuizQuestion(
                question_id="Q1",
                prompt="What return annotation is recorded in this function's signature?",
                options=(
                    TeachQuizOption("A", return_annotation),
                    TeachQuizOption("B", "No return value is recorded"),
                    TeachQuizOption("C", "A module definition"),
                ),
                correct_option_id="A",
                answer_explanation=(
                    f"The signature records {return_annotation}. An annotation is source "
                    "evidence, not a runtime type guarantee."
                ),
                references=(_reference(symbol_item),),
            )
        else:
            has_output = bool(function_evidence.output_sites)
            question_one = TeachQuizQuestion(
                question_id="Q1",
                prompt="Does the source contain an explicit return or yield site?",
                options=(TeachQuizOption("A", "Yes"), TeachQuizOption("B", "No")),
                correct_option_id="A" if has_output else "B",
                answer_explanation=(
                    f"The scanner recorded {len(function_evidence.output_sites)} explicit "
                    "return or yield site(s)."
                ),
                references=tuple(map(_reference, output_items))
                or (_reference(symbol_item),),
            )

        if function_evidence.raise_sites:
            first_raise = function_evidence.raise_sites[0]
            correct_exception = _exception_name(first_raise.exception_expression)
            distractor = "SyntaxError" if correct_exception != "SyntaxError" else "ValueError"
            question_two = TeachQuizQuestion(
                question_id="Q2",
                prompt=(
                    f"Which exception is explicitly raised at the recorded error site on line {first_raise.line}?"
                ),
                options=(
                    TeachQuizOption("A", correct_exception),
                    TeachQuizOption("B", distractor),
                    TeachQuizOption("C", "No exception is recorded"),
                ),
                correct_option_id="A",
                answer_explanation=(
                    f"The source explicitly contains a {correct_exception} raise expression."
                ),
                references=(_reference(raise_items[0]),),
            )
        elif selected_resolved_pairs:
            first_call, first_call_item = selected_resolved_pairs[0]
            question_two = TeachQuizQuestion(
                question_id="Q2",
                prompt="Which supporting project definition is conservatively resolved from this function?",
                options=(
                    TeachQuizOption(
                        "A", first_call.resolved_target_symbol_id or first_call.target_expression
                    ),
                    TeachQuizOption("B", "No internal call is visible"),
                    TeachQuizOption("C", "The selected project is imported and executed"),
                ),
                correct_option_id="A",
                answer_explanation=(
                    "Project Mentor links the call to a visible source definition, while "
                    "runtime dispatch remains uncertain."
                ),
                references=(_reference(first_call_item),),
            )
        else:
            question_two = TeachQuizQuestion(
                question_id="Q2",
                prompt="What is the safest interpretation when no internal call is resolved?",
                options=(
                    TeachQuizOption("A", "The scan lacks a reliable internal target"),
                    TeachQuizOption("B", "The call can never run"),
                    TeachQuizOption("C", "The project has no dependencies"),
                ),
                correct_option_id="A",
                answer_explanation=(
                    "Missing static resolution is uncertainty, not proof that runtime behaviour is absent."
                ),
                references=(_reference(symbol_item),),
            )

        runtime_reference = (
            _reference(output_items[0])
            if output_items
            else _reference(call_items[0])
            if call_items
            else _reference(symbol_item)
        )
        quiz = (
            question_one,
            question_two,
            TeachQuizQuestion(
                question_id="Q3",
                prompt="What can this static lesson not prove?",
                options=(
                    TeachQuizOption("A", "That a particular path executes at runtime"),
                    TeachQuizOption("B", "Where the function is defined in source"),
                    TeachQuizOption("C", "Which parameters are written in the signature"),
                ),
                correct_option_id="A",
                answer_explanation=(
                    "Static analysis records source structure but cannot prove that a real "
                    "execution reaches a particular branch or call."
                ),
                references=(runtime_reference,),
            ),
        )

        uncertainty_labels = [
            "Observed source: syntax recorded directly without executing the project.",
            "Project Mentor inference: a conservative relationship, not runtime proof.",
            "Runtime boundary: static analysis cannot prove which path executes or what dynamic dispatch selects.",
        ]
        if omitted_count:
            uncertainty_labels.append(
                f"Technical evidence limit: {omitted_count} additional record(s) were omitted by fixed safety limits."
            )

        evidence_groups = tuple(
            group
            for group in (
                _evidence_group(
                    "Definition and inputs",
                    f"{1 + len(parameter_items)} exact definition/input record(s).",
                    [symbol_item] + parameter_items,
                ),
                _evidence_group(
                    "Outputs and state",
                    f"{len(output_items)} output and {len(mutation_items)} state-change record(s).",
                    output_items + mutation_items,
                ),
                _evidence_group(
                    "Explicit errors and exception paths",
                    f"{len(raise_items)} raise and {len(exception_items)} try/handler record(s).",
                    raise_items + exception_items,
                ),
                _evidence_group(
                    "Calls",
                    f"{len(call_items)} bounded call record(s); {len(resolved_calls)} of these resolve within the project.",
                    call_items,
                ),
                _evidence_group(
                    "Data flow",
                    f"{len(flow_items)} bounded assignment-flow record(s), grouped here instead of repeated in beginner prose.",
                    flow_items,
                ),
                _evidence_group(
                    "Call error propagation",
                    f"{len(error_items)} bounded call-error record(s) across {len({item.reason for item in errors})} reason pattern(s).",
                    error_items,
                ),
                _evidence_group(
                    "Internal imports",
                    f"{len(import_items)} file-level internal import record(s). These are technical context, not automatic learning prerequisites.",
                    import_items,
                ),
            )
            if group is not None
        )

        lesson = TeachLesson(
            lesson_schema_version=TEACH_LESSON_SCHEMA_VERSION,
            lesson_id=self._lesson_id(
                symbol.symbol_id, technical_items, candidate_count
            ),
            title=f"Understanding {symbol.qualified_name}",
            learning_objective=(
                f"Explain the main stages, inputs, output, and error boundaries of "
                f"{symbol.qualified_name} using a small set of source-backed facts."
            ),
            symbol_id=symbol.symbol_id,
            symbol_kind=symbol.kind,
            file_path=symbol.file_path,
            line_start=symbol.line,
            line_end=symbol.end_line,
            prerequisites=tuple(prerequisites),
            stages=stages,
            sections=sections,
            vocabulary=tuple(vocabulary),
            prediction_exercise=exercise,
            quiz=quiz,
            uncertainty_labels=tuple(uncertainty_labels),
            evidence_candidate_count=candidate_count,
            evidence_included_count=len(technical_items),
            evidence_omitted_count=omitted_count,
            teaching_evidence_count=len(teaching_items),
            evidence_references=tuple(map(_reference, technical_items)),
            evidence_groups=evidence_groups,
        )
        return TeachLessonBundle(
            lesson=lesson, evidence_items=tuple(teaching_items)
        )

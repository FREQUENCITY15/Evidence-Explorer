"""Serializable evidence models for Project Mentor reports.

The report deliberately separates syntax observed in source files from
relationships inferred by conservative static analysis. Compatibility
properties keep the in-process Phase 1.1 scanner API convenient while JSON
exports use the clearer Phase 1.3 structure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ImportAlias:
    imported_name: str
    bound_name: str


@dataclass
class ImportInfo:
    module: str
    names: list[str]
    line: int
    level: int = 0
    classification: str = "unclassified"
    resolved_modules: list[str] = field(default_factory=list)
    aliases: list[ImportAlias] = field(default_factory=list)
    scope_id: str = ""


@dataclass
class CallInfo:
    caller: str
    target: str
    line: int
    column: int = 0


@dataclass
class FunctionInfo:
    name: str
    line: int
    end_line: int | None
    is_async: bool
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None


@dataclass
class ClassInfo:
    name: str
    line: int
    end_line: int | None
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    docstring: str | None = None


@dataclass
class FileAnalysis:
    path: str
    module: str
    line_count: int = 0
    imports: list[ImportInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    calls: list[CallInfo] = field(default_factory=list)
    has_main_guard: bool = False
    is_empty_package_marker: bool = False
    possibly_unused: bool = False
    parse_error: str | None = None


@dataclass
class SymbolDefinition:
    symbol_id: str
    kind: str
    name: str
    qualified_name: str
    module: str
    file_path: str
    line: int
    end_line: int | None
    signature: str | None
    docstring_first_line: str | None
    parent_symbol_id: str | None = None


@dataclass
class ParameterEvidence:
    name: str
    kind: str
    annotation: str | None
    default: str | None
    line: int


@dataclass
class OutputSiteEvidence:
    kind: str
    expression: str | None
    line: int
    column: int
    confidence: str
    reason: str


@dataclass
class MutationEvidence:
    target_expression: str
    mutation_kind: str
    value_expression: str | None
    line: int
    column: int
    confidence: str
    reason: str


@dataclass
class RaiseEvidence:
    exception_expression: str | None
    cause_expression: str | None
    line: int
    column: int
    confidence: str
    reason: str


@dataclass
class ExceptionPathEvidence:
    path_kind: str
    try_line: int
    line: int
    end_line: int | None
    exception_expression: str | None
    bound_name: str | None
    confidence: str
    reason: str


@dataclass
class FunctionEvidence:
    symbol_id: str
    file_path: str
    parameters: list[ParameterEvidence] = field(default_factory=list)
    output_sites: list[OutputSiteEvidence] = field(default_factory=list)
    mutations: list[MutationEvidence] = field(default_factory=list)
    raise_sites: list[RaiseEvidence] = field(default_factory=list)
    exception_paths: list[ExceptionPathEvidence] = field(default_factory=list)


@dataclass
class DataFlowRelationship:
    function_symbol_id: str
    target_expression: str
    source_expression: str
    source_names: list[str]
    relationship_kind: str
    file_path: str
    line: int
    column: int
    confidence: str
    reason: str


@dataclass
class CallRelationship:
    caller_symbol_id: str
    target_expression: str
    resolved_target_symbol_id: str | None
    file_path: str
    line: int
    column: int
    confidence: str
    reason: str


@dataclass
class ErrorPropagationEvidence:
    caller_symbol_id: str
    target_expression: str
    resolved_target_symbol_id: str | None
    file_path: str
    line: int
    column: int
    context: str
    protected_by_try_line: int | None
    caught_expressions: list[str]
    target_raise_lines: list[int]
    propagation: str
    confidence: str
    reason: str


@dataclass
class EntryPointCandidate:
    path: str
    score: int
    confidence: str
    reasons: list[str]


@dataclass
class LearningStep:
    position: int
    path: str
    reason: str


@dataclass
class ImportEdge:
    source_path: str
    source_module: str
    target_path: str
    target_module: str


@dataclass
class UnusedFileCandidate:
    path: str
    reason: str


@dataclass
class ProjectMetadata:
    name: str
    root: str


@dataclass
class GeneratorMetadata:
    name: str
    version: str
    phase: str


@dataclass
class ObservedFacts:
    files: list[FileAnalysis]
    symbols: list[SymbolDefinition]
    function_evidence: list[FunctionEvidence]


@dataclass
class InferredRelationships:
    import_edges: list[ImportEdge]
    call_relationships: list[CallRelationship]
    data_flows: list[DataFlowRelationship]
    error_propagation: list[ErrorPropagationEvidence]
    entry_points: list[EntryPointCandidate]
    learning_order: list[LearningStep]
    external_dependencies: list[str]
    unused_files: list[UnusedFileCandidate]


@dataclass
class ProjectAnalysis:
    schema_version: str
    project: ProjectMetadata
    generator: GeneratorMetadata
    summary: dict[str, Any]
    observed_facts: ObservedFacts
    inferred_relationships: InferredRelationships
    warnings: list[str]

    @property
    def root(self) -> str:
        return self.project.root

    @property
    def files(self) -> list[FileAnalysis]:
        return self.observed_facts.files

    @property
    def symbols(self) -> list[SymbolDefinition]:
        return self.observed_facts.symbols

    @property
    def function_evidence(self) -> list[FunctionEvidence]:
        return self.observed_facts.function_evidence

    @property
    def import_edges(self) -> list[ImportEdge]:
        return self.inferred_relationships.import_edges

    @property
    def call_relationships(self) -> list[CallRelationship]:
        return self.inferred_relationships.call_relationships

    @property
    def data_flows(self) -> list[DataFlowRelationship]:
        return self.inferred_relationships.data_flows

    @property
    def error_propagation(self) -> list[ErrorPropagationEvidence]:
        return self.inferred_relationships.error_propagation

    @property
    def entry_points(self) -> list[EntryPointCandidate]:
        return self.inferred_relationships.entry_points

    @property
    def learning_order(self) -> list[LearningStep]:
        return self.inferred_relationships.learning_order

    @property
    def external_dependencies(self) -> list[str]:
        return self.inferred_relationships.external_dependencies

    @property
    def unused_files(self) -> list[UnusedFileCandidate]:
        return self.inferred_relationships.unused_files

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic, explicitly grouped report structure."""

        return asdict(self)

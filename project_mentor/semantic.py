"""AST-only symbol extraction and conservative call resolution.

Project Mentor never imports the repository being scanned. This module uses
only syntax trees and deliberately leaves a call unresolved when more than one
reasonable runtime target remains.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from project_mentor.models import (
    CallInfo,
    CallRelationship,
    ClassInfo,
    DataFlowRelationship,
    ErrorPropagationEvidence,
    ExceptionPathEvidence,
    FileAnalysis,
    FunctionEvidence,
    FunctionInfo,
    ImportAlias,
    ImportInfo,
    MutationEvidence,
    OutputSiteEvidence,
    ParameterEvidence,
    RaiseEvidence,
    SymbolDefinition,
)


def safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except (AttributeError, ValueError):
        return node.__class__.__name__


def first_docstring_line(node: ast.AST) -> str | None:
    value = ast.get_docstring(node, clean=True)
    return value.splitlines()[0] if value else None


def is_main_guard(node: ast.If) -> bool:
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq) or len(test.comparators) != 1:
        return False
    left, right = test.left, test.comparators[0]
    return any(
        isinstance(name, ast.Name)
        and name.id == "__name__"
        and isinstance(value, ast.Constant)
        and value.value == "__main__"
        for name, value in ((left, right), (right, left))
    )


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    arguments = safe_unparse(node.args)
    result = f"({arguments})"
    if node.returns is not None:
        result += f" -> {safe_unparse(node.returns)}"
    return result


def _is_empty_package_marker(path: str, tree: ast.Module) -> bool:
    if Path(path).name != "__init__.py":
        return False
    meaningful = [
        item
        for item in tree.body
        if not (
            isinstance(item, ast.Pass)
            or (
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Constant)
                and isinstance(item.value.value, str)
            )
        )
    ]
    return not meaningful


def _parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    positional = [*node.args.posonlyargs, *node.args.args]
    names = [item.arg for item in positional]
    if node.args.vararg:
        names.append(node.args.vararg.arg)
    names.extend(item.arg for item in node.args.kwonlyargs)
    if node.args.kwarg:
        names.append(node.args.kwarg.arg)
    return names


def _parameter_evidence(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ParameterEvidence]:
    positional = [*node.args.posonlyargs, *node.args.args]
    positional_defaults: list[ast.expr | None] = [None] * (
        len(positional) - len(node.args.defaults)
    ) + list(node.args.defaults)
    result: list[ParameterEvidence] = []
    positional_only = len(node.args.posonlyargs)
    for index, (argument, default) in enumerate(
        zip(positional, positional_defaults, strict=True)
    ):
        result.append(
            ParameterEvidence(
                name=argument.arg,
                kind=(
                    "positional_only"
                    if index < positional_only
                    else "positional_or_keyword"
                ),
                annotation=(
                    safe_unparse(argument.annotation)
                    if argument.annotation is not None
                    else None
                ),
                default=safe_unparse(default) if default is not None else None,
                line=argument.lineno,
            )
        )
    if node.args.vararg is not None:
        argument = node.args.vararg
        result.append(
            ParameterEvidence(
                argument.arg,
                "var_positional",
                safe_unparse(argument.annotation)
                if argument.annotation is not None
                else None,
                None,
                argument.lineno,
            )
        )
    for argument, default in zip(
        node.args.kwonlyargs, node.args.kw_defaults, strict=True
    ):
        result.append(
            ParameterEvidence(
                argument.arg,
                "keyword_only",
                safe_unparse(argument.annotation)
                if argument.annotation is not None
                else None,
                safe_unparse(default) if default is not None else None,
                argument.lineno,
            )
        )
    if node.args.kwarg is not None:
        argument = node.args.kwarg
        result.append(
            ParameterEvidence(
                argument.arg,
                "var_keyword",
                safe_unparse(argument.annotation)
                if argument.annotation is not None
                else None,
                None,
                argument.lineno,
            )
        )
    return result


def _loaded_names(node: ast.AST) -> list[str]:
    """Return referenced names without treating them as proven runtime values."""

    return sorted(
        {
            item.id
            for item in ast.walk(node)
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
        }
    )


FUNCTION_SCOPE_KINDS = {
    "function",
    "async_function",
    "method",
    "async_method",
}

COMMON_MUTATOR_METHODS = {
    "add",
    "append",
    "clear",
    "difference_update",
    "discard",
    "extend",
    "insert",
    "intersection_update",
    "pop",
    "popitem",
    "remove",
    "reverse",
    "setdefault",
    "sort",
    "symmetric_difference_update",
    "update",
}


@dataclass
class ScopeFacts:
    scope_id: str
    parent_scope_id: str | None
    kind: str
    qualified_name: str
    parameter_names: set[str] = field(default_factory=set)
    first_parameter: str | None = None
    enclosing_class_id: str | None = None
    global_names: set[str] = field(default_factory=set)
    nonlocal_names: set[str] = field(default_factory=set)


@dataclass
class BindingEvent:
    scope_id: str
    name: str
    line: int
    kind: str
    value_func: ast.AST | None = None
    straight_line: bool = False


@dataclass
class RawCall:
    caller_symbol_id: str
    target_expression: str
    file_path: str
    line: int
    column: int
    func: ast.AST
    error_context: str = "unprotected"
    protected_by_try_line: int | None = None
    caught_expressions: list[str] = field(default_factory=list)


@dataclass
class SemanticFile:
    analysis: FileAnalysis
    tree: ast.Module | None
    symbols: list[SymbolDefinition] = field(default_factory=list)
    raw_calls: list[RawCall] = field(default_factory=list)
    scopes: dict[str, ScopeFacts] = field(default_factory=dict)
    bindings: list[BindingEvent] = field(default_factory=list)
    decorated_symbol_ids: set[str] = field(default_factory=set)
    function_evidence: list[FunctionEvidence] = field(default_factory=list)
    data_flows: list[DataFlowRelationship] = field(default_factory=list)


@dataclass
class _ScopeFrame:
    scope_id: str
    qualified_name: str
    kind: str
    enclosing_class_id: str | None


@dataclass
class _ErrorContext:
    kind: str
    try_line: int
    caught_expressions: list[str] = field(default_factory=list)


class EvidenceVisitor(ast.NodeVisitor):
    """Collect source facts while preserving Python definition-time scopes."""

    def __init__(self, module: str, file_path: str) -> None:
        self.module = module
        self.file_path = file_path
        self.module_label = module or "<root>"
        module_id = f"{self.module_label}:<module>"
        self.imports: list[ImportInfo] = []
        self.functions: list[FunctionInfo] = []
        self.classes: list[ClassInfo] = []
        self.calls: list[CallInfo] = []
        self.symbols: list[SymbolDefinition] = []
        self.raw_calls: list[RawCall] = []
        self.bindings: list[BindingEvent] = []
        self.function_evidence: list[FunctionEvidence] = []
        self.data_flows: list[DataFlowRelationship] = []
        self._function_evidence_by_id: dict[str, FunctionEvidence] = {}
        self.scopes: dict[str, ScopeFacts] = {
            module_id: ScopeFacts(module_id, None, "module", "<module>")
        }
        self.decorated_symbol_ids: set[str] = set()
        self.has_main_guard = False
        self._scope_stack = [_ScopeFrame(module_id, "", "module", None)]
        self._used_symbol_ids: set[str] = set()
        self._flow_depth = 0
        self._error_context_stack: list[_ErrorContext] = []

    @property
    def scope(self) -> _ScopeFrame:
        return self._scope_stack[-1]

    def _qualified_name(self, name: str) -> str:
        return ".".join(part for part in (self.scope.qualified_name, name) if part)

    def _new_symbol_id(self, qualified_name: str, line: int) -> str:
        base = f"{self.module_label}:{qualified_name}"
        if base not in self._used_symbol_ids:
            self._used_symbol_ids.add(base)
            return base
        duplicate = f"{base}@L{line}"
        counter = 2
        while duplicate in self._used_symbol_ids:
            duplicate = f"{base}@L{line}.{counter}"
            counter += 1
        self._used_symbol_ids.add(duplicate)
        return duplicate

    def _current_function_evidence(self) -> FunctionEvidence | None:
        if self.scope.kind not in FUNCTION_SCOPE_KINDS:
            return None
        return self._function_evidence_by_id.get(self.scope.scope_id)

    def _flow_confidence(self, *, inherently_uncertain: bool = False) -> str:
        return "uncertain" if inherently_uncertain or self._flow_depth else "high"

    def _flow_reason(self, *, inherently_uncertain: bool = False) -> str:
        if self._flow_depth:
            return (
                "The assignment is visible in the AST, but it occurs on a conditional "
                "or repeating control-flow path and may not execute. Referenced names "
                "are not proof of runtime values."
            )
        if inherently_uncertain:
            return (
                "The assignment is visible in the AST, but unpacking, calls, context "
                "management, iteration, or operator dispatch makes the value flow uncertain."
            )
        return (
            "A straightforward assignment directly relates this target to the source "
            "expression. Referenced names are syntax evidence, not inferred runtime values."
        )

    @staticmethod
    def _complex_flow_value(value: ast.AST) -> bool:
        return any(
            isinstance(
                item,
                (
                    ast.Await,
                    ast.Call,
                    ast.GeneratorExp,
                    ast.Lambda,
                    ast.ListComp,
                    ast.SetComp,
                    ast.DictComp,
                    ast.Yield,
                    ast.YieldFrom,
                ),
            )
            for item in ast.walk(value)
        )

    def _record_data_flow(
        self,
        target: ast.AST,
        value: ast.AST,
        relationship_kind: str,
        *,
        inherently_uncertain: bool = False,
    ) -> None:
        evidence = self._current_function_evidence()
        if evidence is None:
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._record_data_flow(
                    item,
                    value,
                    relationship_kind,
                    inherently_uncertain=True,
                )
            return
        if isinstance(target, ast.Starred):
            self._record_data_flow(
                target.value,
                value,
                relationship_kind,
                inherently_uncertain=True,
            )
            return
        if not isinstance(target, (ast.Name, ast.Attribute, ast.Subscript)):
            return
        uncertain = inherently_uncertain or self._complex_flow_value(value)
        self.data_flows.append(
            DataFlowRelationship(
                function_symbol_id=evidence.symbol_id,
                target_expression=safe_unparse(target),
                source_expression=safe_unparse(value),
                source_names=_loaded_names(value),
                relationship_kind=relationship_kind,
                file_path=self.file_path,
                line=getattr(target, "lineno", getattr(value, "lineno", 0)),
                column=getattr(target, "col_offset", 0),
                confidence=self._flow_confidence(inherently_uncertain=uncertain),
                reason=self._flow_reason(inherently_uncertain=uncertain),
            )
        )

    def _mutation_reason(self, direct_description: str) -> tuple[str, str]:
        if self._flow_depth:
            return (
                "uncertain",
                direct_description
                + " The write is on a conditional or repeating path, so execution is uncertain.",
            )
        return (
            "high",
            direct_description
            + " This records source syntax only; descriptors and runtime objects can change effects.",
        )

    def _record_mutation_target(
        self,
        target: ast.AST,
        mutation_kind: str,
        value: ast.AST | None,
        *,
        inherently_uncertain: bool = False,
    ) -> None:
        evidence = self._current_function_evidence()
        if evidence is None:
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._record_mutation_target(
                    item,
                    mutation_kind,
                    value,
                    inherently_uncertain=True,
                )
            return
        if isinstance(target, ast.Starred):
            self._record_mutation_target(
                target.value,
                mutation_kind,
                value,
                inherently_uncertain=True,
            )
            return

        description: str | None = None
        recorded_kind = mutation_kind
        if isinstance(target, ast.Attribute):
            description = "Assignment syntax directly writes an object attribute."
            recorded_kind = f"attribute_{mutation_kind}"
        elif isinstance(target, ast.Subscript):
            description = "Assignment syntax directly writes an indexed item."
            recorded_kind = f"subscript_{mutation_kind}"
        elif isinstance(target, ast.Name):
            scope = self.scopes[self.scope.scope_id]
            if target.id in scope.global_names:
                description = "Assignment targets a name declared global in this function."
                recorded_kind = f"global_{mutation_kind}"
            elif target.id in scope.nonlocal_names:
                description = "Assignment targets a name declared nonlocal in this function."
                recorded_kind = f"nonlocal_{mutation_kind}"
        if description is None:
            return
        confidence, reason = self._mutation_reason(description)
        if inherently_uncertain and confidence == "high":
            confidence = "uncertain"
            reason += " Iteration, unpacking, or context-manager behavior makes execution uncertain."
        evidence.mutations.append(
            MutationEvidence(
                target_expression=safe_unparse(target),
                mutation_kind=recorded_kind,
                value_expression=safe_unparse(value) if value is not None else None,
                line=getattr(target, "lineno", getattr(value, "lineno", 0)),
                column=getattr(target, "col_offset", 0),
                confidence=confidence,
                reason=reason,
            )
        )

    def _record_mutator_call(self, node: ast.Call) -> None:
        evidence = self._current_function_evidence()
        if evidence is None:
            return
        target: ast.AST | None = None
        kind: str | None = None
        value_expression: str | None = None
        if isinstance(node.func, ast.Attribute) and node.func.attr in COMMON_MUTATOR_METHODS:
            target = node.func.value
            kind = "possible_mutator_method_call"
            value_expression = safe_unparse(node)
        elif isinstance(node.func, ast.Name) and node.func.id in {"setattr", "delattr"}:
            if node.args:
                target = node.args[0]
                kind = f"possible_{node.func.id}_call"
                value_expression = safe_unparse(node)
        if target is None or kind is None:
            return
        evidence.mutations.append(
            MutationEvidence(
                target_expression=safe_unparse(target),
                mutation_kind=kind,
                value_expression=value_expression,
                line=node.lineno,
                column=node.col_offset,
                confidence="uncertain",
                reason=(
                    "The method or built-in name commonly mutates state, but AST-only "
                    "analysis cannot prove the receiver type, callable identity, or runtime effect."
                ),
            )
        )

    def _call_error_context(self) -> tuple[str, int | None, list[str]]:
        context = (
            self._error_context_stack[-1].kind
            if self._error_context_stack
            else "unprotected"
        )
        protected = next(
            (
                item
                for item in reversed(self._error_context_stack)
                if item.kind == "try_body" and item.caught_expressions
            ),
            None,
        )
        return (
            context,
            protected.try_line if protected is not None else None,
            list(protected.caught_expressions) if protected is not None else [],
        )

    def _record_binding(
        self,
        name: str,
        line: int,
        kind: str,
        *,
        value_func: ast.AST | None = None,
    ) -> None:
        self.bindings.append(
            BindingEvent(
                scope_id=self.scope.scope_id,
                name=name,
                line=line,
                kind=kind,
                value_func=value_func,
                straight_line=self._flow_depth == 0,
            )
        )

    def _record_target(
        self, target: ast.AST, line: int, value_func: ast.AST | None = None
    ) -> None:
        if isinstance(target, ast.Name):
            self._record_binding(
                target.id, line, "assignment", value_func=value_func
            )
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._record_target(item, line)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound_name = alias.asname or alias.name.split(".")[0]
            self.imports.append(
                ImportInfo(
                    module="",
                    names=[alias.name],
                    line=node.lineno,
                    aliases=[ImportAlias(alias.name, bound_name)],
                    scope_id=self.scope.scope_id,
                )
            )
            self._record_binding(bound_name, node.lineno, "import")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        aliases = [
            ImportAlias(alias.name, alias.asname or alias.name)
            for alias in node.names
        ]
        self.imports.append(
            ImportInfo(
                module=node.module or "",
                names=[alias.name for alias in node.names],
                line=node.lineno,
                level=node.level,
                aliases=aliases,
                scope_id=self.scope.scope_id,
            )
        )
        for alias in aliases:
            self._record_binding(alias.bound_name, node.lineno, "import")

    def _visit_definition_expressions(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in node.args.defaults:
            self.visit(default)
        for default in node.args.kw_defaults:
            if default is not None:
                self.visit(default)
        for argument in [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]:
            if argument.annotation is not None:
                self.visit(argument.annotation)
        if node.args.vararg and node.args.vararg.annotation is not None:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation is not None:
            self.visit(node.args.kwarg.annotation)
        if node.returns is not None:
            self.visit(node.returns)
        for type_parameter in getattr(node, "type_params", []):
            self.visit(type_parameter)

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool
    ) -> None:
        parent = self.scope
        qualified_name = self._qualified_name(node.name)
        symbol_id = self._new_symbol_id(qualified_name, node.lineno)
        kind = (
            "async_method"
            if is_async and parent.kind == "class"
            else "method"
            if parent.kind == "class"
            else "async_function"
            if is_async
            else "function"
        )
        self._record_binding(node.name, node.lineno, "definition")
        symbol = SymbolDefinition(
            symbol_id=symbol_id,
            kind=kind,
            name=node.name,
            qualified_name=qualified_name,
            module=self.module,
            file_path=self.file_path,
            line=node.lineno,
            end_line=getattr(node, "end_lineno", None),
            signature=_signature(node),
            docstring_first_line=first_docstring_line(node),
            parent_symbol_id=None if parent.kind == "module" else parent.scope_id,
        )
        self.symbols.append(symbol)
        if node.decorator_list:
            self.decorated_symbol_ids.add(symbol_id)
        self.functions.append(
            FunctionInfo(
                name=qualified_name,
                line=node.lineno,
                end_line=getattr(node, "end_lineno", None),
                is_async=is_async,
                decorators=[safe_unparse(item) for item in node.decorator_list],
                docstring=first_docstring_line(node),
            )
        )
        function_evidence = FunctionEvidence(
            symbol_id=symbol_id,
            file_path=self.file_path,
            parameters=_parameter_evidence(node),
        )
        self.function_evidence.append(function_evidence)
        self._function_evidence_by_id[symbol_id] = function_evidence

        self._visit_definition_expressions(node)
        parameters = _parameter_names(node)
        enclosing_class = parent.scope_id if parent.kind == "class" else None
        self.scopes[symbol_id] = ScopeFacts(
            scope_id=symbol_id,
            parent_scope_id=parent.scope_id,
            kind=kind,
            qualified_name=qualified_name,
            parameter_names=set(parameters),
            first_parameter=parameters[0] if parameters else None,
            enclosing_class_id=enclosing_class,
        )
        self._scope_stack.append(
            _ScopeFrame(symbol_id, qualified_name, kind, enclosing_class)
        )
        previous_depth = self._flow_depth
        previous_error_context = self._error_context_stack
        self._flow_depth = 0
        self._error_context_stack = []
        for item in node.body:
            self.visit(item)
        self._flow_depth = previous_depth
        self._error_context_stack = previous_error_context
        self._scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node, is_async=True)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        parent = self.scope
        qualified_name = self._qualified_name(node.name)
        symbol_id = self._new_symbol_id(qualified_name, node.lineno)
        self._record_binding(node.name, node.lineno, "definition")
        self.symbols.append(
            SymbolDefinition(
                symbol_id=symbol_id,
                kind="class",
                name=node.name,
                qualified_name=qualified_name,
                module=self.module,
                file_path=self.file_path,
                line=node.lineno,
                end_line=getattr(node, "end_lineno", None),
                signature=None,
                docstring_first_line=first_docstring_line(node),
                parent_symbol_id=None if parent.kind == "module" else parent.scope_id,
            )
        )
        if node.decorator_list:
            self.decorated_symbol_ids.add(symbol_id)
        self.classes.append(
            ClassInfo(
                name=qualified_name,
                line=node.lineno,
                end_line=getattr(node, "end_lineno", None),
                bases=[safe_unparse(base) for base in node.bases],
                methods=[
                    item.name
                    for item in node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                ],
                docstring=first_docstring_line(node),
            )
        )
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)
        for type_parameter in getattr(node, "type_params", []):
            self.visit(type_parameter)
        self.scopes[symbol_id] = ScopeFacts(
            symbol_id,
            parent.scope_id,
            "class",
            qualified_name,
            enclosing_class_id=symbol_id,
        )
        self._scope_stack.append(
            _ScopeFrame(symbol_id, qualified_name, "class", symbol_id)
        )
        previous_depth = self._flow_depth
        self._flow_depth = 0
        for item in node.body:
            self.visit(item)
        self._flow_depth = previous_depth
        self._scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        target = safe_unparse(node.func)
        error_context, protected_by_try_line, caught_expressions = (
            self._call_error_context()
        )
        caller_name = (
            "<module>"
            if self.scope.kind == "module"
            else self.scope.qualified_name
        )
        self.calls.append(
            CallInfo(caller_name, target, node.lineno, node.col_offset)
        )
        self.raw_calls.append(
            RawCall(
                caller_symbol_id=self.scope.scope_id,
                target_expression=target,
                file_path=self.file_path,
                line=node.lineno,
                column=node.col_offset,
                func=node.func,
                error_context=error_context,
                protected_by_try_line=protected_by_try_line,
                caught_expressions=caught_expressions,
            )
        )
        self._record_mutator_call(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        value_func = node.value.func if isinstance(node.value, ast.Call) else None
        for target in node.targets:
            self._record_target(target, node.lineno, value_func)
            self._record_data_flow(target, node.value, "assignment")
            self._record_mutation_target(target, "assignment", node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        value_func = (
            node.value.func
            if node.value is not None and isinstance(node.value, ast.Call)
            else None
        )
        self._record_target(node.target, node.lineno, value_func)
        if node.value is not None:
            self._record_data_flow(node.target, node.value, "annotated_assignment")
            self._record_mutation_target(
                node.target, "annotated_assignment", node.value
            )
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._record_target(node.target, node.lineno)
        self._record_data_flow(
            node.target,
            node.value,
            "augmented_assignment",
            inherently_uncertain=True,
        )
        self._record_mutation_target(
            node.target,
            "augmented_assignment",
            node.value,
            inherently_uncertain=True,
        )
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        value_func = node.value.func if isinstance(node.value, ast.Call) else None
        self._record_target(node.target, node.lineno, value_func)
        self._record_data_flow(node.target, node.value, "named_expression")
        self._record_mutation_target(node.target, "named_expression", node.value)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._record_target(node.target, node.lineno)
        self._record_data_flow(
            node.target,
            node.iter,
            "iteration_binding",
            inherently_uncertain=True,
        )
        self._record_mutation_target(
            node.target,
            "iteration_binding",
            node.iter,
            inherently_uncertain=True,
        )
        self._visit_dynamic_flow(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._record_target(node.target, node.lineno)
        self._record_data_flow(
            node.target,
            node.iter,
            "async_iteration_binding",
            inherently_uncertain=True,
        )
        self._record_mutation_target(
            node.target,
            "async_iteration_binding",
            node.iter,
            inherently_uncertain=True,
        )
        self._visit_dynamic_flow(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._record_target(item.optional_vars, node.lineno)
                self._record_data_flow(
                    item.optional_vars,
                    item.context_expr,
                    "context_manager_binding",
                    inherently_uncertain=True,
                )
                self._record_mutation_target(
                    item.optional_vars,
                    "context_manager_binding",
                    item.context_expr,
                    inherently_uncertain=True,
                )
        self._visit_dynamic_flow(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._record_target(item.optional_vars, node.lineno)
                self._record_data_flow(
                    item.optional_vars,
                    item.context_expr,
                    "async_context_manager_binding",
                    inherently_uncertain=True,
                )
                self._record_mutation_target(
                    item.optional_vars,
                    "async_context_manager_binding",
                    item.context_expr,
                    inherently_uncertain=True,
                )
        self._visit_dynamic_flow(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self._record_binding(node.name, node.lineno, "assignment")
        self._visit_dynamic_flow(node)

    def visit_Return(self, node: ast.Return) -> None:
        evidence = self._current_function_evidence()
        if evidence is not None:
            confidence = self._flow_confidence()
            evidence.output_sites.append(
                OutputSiteEvidence(
                    kind="return",
                    expression=safe_unparse(node.value)
                    if node.value is not None
                    else None,
                    line=node.lineno,
                    column=node.col_offset,
                    confidence=confidence,
                    reason=(
                        "A return site is directly present in the function body."
                        if confidence == "high"
                        else "The return site is present on a conditional or repeating path and may not execute."
                    ),
                )
            )
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield) -> None:
        evidence = self._current_function_evidence()
        if evidence is not None:
            confidence = self._flow_confidence()
            evidence.output_sites.append(
                OutputSiteEvidence(
                    kind="yield",
                    expression=safe_unparse(node.value)
                    if node.value is not None
                    else None,
                    line=node.lineno,
                    column=node.col_offset,
                    confidence=confidence,
                    reason=(
                        "A yield site is directly present in the function body."
                        if confidence == "high"
                        else "The yield site is present on a conditional or repeating path and may not execute."
                    ),
                )
            )
        self.generic_visit(node)

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        evidence = self._current_function_evidence()
        if evidence is not None:
            confidence = self._flow_confidence(inherently_uncertain=True)
            evidence.output_sites.append(
                OutputSiteEvidence(
                    kind="yield_from",
                    expression=safe_unparse(node.value),
                    line=node.lineno,
                    column=node.col_offset,
                    confidence=confidence,
                    reason=(
                        "A yield-from site is present, but the delegated iterator's "
                        "runtime outputs cannot be inferred from syntax alone."
                    ),
                )
            )
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        evidence = self._current_function_evidence()
        if evidence is not None:
            confidence = self._flow_confidence()
            evidence.raise_sites.append(
                RaiseEvidence(
                    exception_expression=(
                        safe_unparse(node.exc) if node.exc is not None else None
                    ),
                    cause_expression=(
                        safe_unparse(node.cause) if node.cause is not None else None
                    ),
                    line=node.lineno,
                    column=node.col_offset,
                    confidence=confidence,
                    reason=(
                        "A raise statement is directly present in the function body."
                        if confidence == "high"
                        else "The raise statement is present on a conditional, handler, or repeating path and may not execute."
                    ),
                )
            )
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            self._record_mutation_target(target, "deletion", None)
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.scopes[self.scope.scope_id].global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.scopes[self.scope.scope_id].nonlocal_names.update(node.names)

    def visit_If(self, node: ast.If) -> None:
        if is_main_guard(node):
            self.has_main_guard = True
        self.visit(node.test)
        self._flow_depth += 1
        for item in [*node.body, *node.orelse]:
            self.visit(item)
        self._flow_depth -= 1

    def visit_While(self, node: ast.While) -> None:
        self._visit_dynamic_flow(node)

    def _visit_try_statement(self, node: ast.Try | ast.TryStar) -> None:
        evidence = self._current_function_evidence()
        caught_expressions = [
            safe_unparse(handler.type) if handler.type is not None else "<bare except>"
            for handler in node.handlers
        ]
        if evidence is not None:
            surrounding_confidence = self._flow_confidence()
            body_line = node.body[0].lineno if node.body else node.lineno
            body_end = (
                getattr(node.body[-1], "end_lineno", None) if node.body else node.lineno
            )
            evidence.exception_paths.append(
                ExceptionPathEvidence(
                    path_kind="try_body",
                    try_line=node.lineno,
                    line=body_line,
                    end_line=body_end,
                    exception_expression=None,
                    bound_name=None,
                    confidence=surrounding_confidence,
                    reason=(
                        "The AST directly records this protected try-body path."
                        if surrounding_confidence == "high"
                        else "The protected try-body is nested on a conditional or repeating path and may not be entered."
                    ),
                )
            )
            for handler in node.handlers:
                evidence.exception_paths.append(
                    ExceptionPathEvidence(
                        path_kind="except_handler",
                        try_line=node.lineno,
                        line=handler.lineno,
                        end_line=getattr(handler, "end_lineno", None),
                        exception_expression=(
                            safe_unparse(handler.type)
                            if handler.type is not None
                            else None
                        ),
                        bound_name=handler.name,
                        confidence="uncertain",
                        reason=(
                            "The handler path is visible, but AST-only analysis cannot "
                            "prove which runtime exceptions reach it or whether it completes."
                        ),
                    )
                )
            if node.orelse:
                evidence.exception_paths.append(
                    ExceptionPathEvidence(
                        path_kind="try_else",
                        try_line=node.lineno,
                        line=node.orelse[0].lineno,
                        end_line=getattr(node.orelse[-1], "end_lineno", None),
                        exception_expression=None,
                        bound_name=None,
                        confidence="uncertain",
                        reason="The else path runs only if the try body completes without a handled exception.",
                    )
                )
            if node.finalbody:
                evidence.exception_paths.append(
                    ExceptionPathEvidence(
                        path_kind="finally",
                        try_line=node.lineno,
                        line=node.finalbody[0].lineno,
                        end_line=getattr(node.finalbody[-1], "end_lineno", None),
                        exception_expression=None,
                        bound_name=None,
                        confidence=surrounding_confidence,
                        reason=(
                            "A finally path is directly present and is entered when control "
                            "leaves an entered try statement, though entering the surrounding "
                            "path and its runtime effects remain unknown."
                        ),
                    )
                )

        self._flow_depth += 1
        self._error_context_stack.append(
            _ErrorContext("try_body", node.lineno, caught_expressions)
        )
        for item in node.body:
            self.visit(item)
        self._error_context_stack.pop()

        for handler in node.handlers:
            if handler.type is not None:
                self.visit(handler.type)
            if handler.name:
                self._record_binding(handler.name, handler.lineno, "assignment")
                if evidence is not None:
                    source = handler.type or ast.Constant(value="<raised exception>")
                    self._record_data_flow(
                        ast.Name(
                            id=handler.name,
                            ctx=ast.Store(),
                            lineno=handler.lineno,
                            col_offset=handler.col_offset,
                        ),
                        source,
                        "exception_binding",
                        inherently_uncertain=True,
                    )
            self._error_context_stack.append(
                _ErrorContext("except_handler", node.lineno)
            )
            for item in handler.body:
                self.visit(item)
            self._error_context_stack.pop()

        if node.orelse:
            self._error_context_stack.append(_ErrorContext("try_else", node.lineno))
            for item in node.orelse:
                self.visit(item)
            self._error_context_stack.pop()
        if node.finalbody:
            self._error_context_stack.append(_ErrorContext("finally", node.lineno))
            for item in node.finalbody:
                self.visit(item)
            self._error_context_stack.pop()
        self._flow_depth -= 1

    def visit_Try(self, node: ast.Try) -> None:
        self._visit_try_statement(node)

    def visit_TryStar(self, node: ast.TryStar) -> None:
        self._visit_try_statement(node)

    def visit_Match(self, node: ast.Match) -> None:
        self._visit_dynamic_flow(node)

    def _visit_dynamic_flow(self, node: ast.AST) -> None:
        self._flow_depth += 1
        self.generic_visit(node)
        self._flow_depth -= 1


def extract_file_evidence(
    module: str,
    file_path: str,
    source: str,
    tree: ast.Module,
) -> SemanticFile:
    visitor = EvidenceVisitor(module, file_path)
    visitor.visit(tree)
    analysis = FileAnalysis(
        path=file_path,
        module=module,
        line_count=len(source.splitlines()),
        imports=visitor.imports,
        functions=visitor.functions,
        classes=visitor.classes,
        calls=visitor.calls,
        has_main_guard=visitor.has_main_guard,
        is_empty_package_marker=_is_empty_package_marker(file_path, tree),
    )
    return SemanticFile(
        analysis=analysis,
        tree=tree,
        symbols=visitor.symbols,
        raw_calls=visitor.raw_calls,
        scopes=visitor.scopes,
        bindings=visitor.bindings,
        decorated_symbol_ids=visitor.decorated_symbol_ids,
        function_evidence=visitor.function_evidence,
        data_flows=visitor.data_flows,
    )


@dataclass
class _Resolution:
    symbol: SymbolDefinition | None
    confidence: str
    reason: str


class CallResolver:
    def __init__(self, files: list[SemanticFile]) -> None:
        self.files = files
        self.by_path = {item.analysis.path: item for item in files}
        self.symbols = [symbol for item in files for symbol in item.symbols]
        self.by_id = {symbol.symbol_id: symbol for symbol in self.symbols}
        self.module_names = {
            item.analysis.module for item in files if item.analysis.module
        }
        self.by_module_qname: dict[
            tuple[str, str], list[SymbolDefinition]
        ] = {}
        self.children: dict[tuple[str, str], list[SymbolDefinition]] = {}
        for symbol in self.symbols:
            self.by_module_qname.setdefault(
                (symbol.module, symbol.qualified_name), []
            ).append(symbol)
            parent = symbol.parent_symbol_id or f"{symbol.module or '<root>'}:<module>"
            self.children.setdefault((parent, symbol.name), []).append(symbol)
        self.decorated = {
            symbol_id
            for item in files
            for symbol_id in item.decorated_symbol_ids
        }

    def resolve_all(self) -> list[CallRelationship]:
        relationships: list[CallRelationship] = []
        for semantic_file in self.files:
            for raw_call in semantic_file.raw_calls:
                resolution = self._resolve_call(semantic_file, raw_call)
                resolution = self._account_for_decorator(resolution)
                relationships.append(
                    CallRelationship(
                        caller_symbol_id=raw_call.caller_symbol_id,
                        target_expression=raw_call.target_expression,
                        resolved_target_symbol_id=(
                            resolution.symbol.symbol_id
                            if resolution.symbol is not None
                            else None
                        ),
                        file_path=raw_call.file_path,
                        line=raw_call.line,
                        column=raw_call.column,
                        confidence=resolution.confidence,
                        reason=resolution.reason,
                    )
                )
        return sorted(
            relationships,
            key=lambda item: (
                item.file_path,
                item.line,
                item.column,
                item.caller_symbol_id,
                item.target_expression,
                item.resolved_target_symbol_id or "",
            ),
        )

    def _account_for_decorator(self, result: _Resolution) -> _Resolution:
        if (
            result.symbol is not None
            and result.confidence == "high"
            and result.symbol.symbol_id in self.decorated
        ):
            return _Resolution(
                result.symbol,
                "medium",
                result.reason
                + " The target has a decorator that may replace its runtime callable.",
            )
        return result

    def _resolve_call(
        self, semantic_file: SemanticFile, call: RawCall
    ) -> _Resolution:
        func = call.func
        if isinstance(func, ast.Name):
            return self._resolve_name(
                semantic_file, call.caller_symbol_id, func.id, call.line
            )
        if isinstance(func, ast.Attribute):
            return self._resolve_attribute(semantic_file, call, func)
        if isinstance(func, (ast.Lambda, ast.Call, ast.Subscript)):
            return _Resolution(
                None,
                "unresolved",
                "The callable is produced dynamically; its runtime target is not statically known.",
            )
        return _Resolution(
            None,
            "unresolved",
            f"The {func.__class__.__name__} call target is not a supported static form.",
        )

    def _scope_chain(
        self, semantic_file: SemanticFile, scope_id: str
    ) -> list[ScopeFacts]:
        chain: list[ScopeFacts] = []
        current = semantic_file.scopes.get(scope_id)
        seen: set[str] = set()
        while current is not None and current.scope_id not in seen:
            seen.add(current.scope_id)
            chain.append(current)
            current = (
                semantic_file.scopes.get(current.parent_scope_id)
                if current.parent_scope_id
                else None
            )
        return chain

    def _events(
        self, semantic_file: SemanticFile, scope_id: str, name: str
    ) -> list[BindingEvent]:
        return [
            item
            for item in semantic_file.bindings
            if item.scope_id == scope_id and item.name == name
        ]

    def _resolve_name(
        self,
        semantic_file: SemanticFile,
        caller_scope_id: str,
        name: str,
        line: int,
        *,
        reference_only: bool = False,
    ) -> _Resolution:
        chain = self._scope_chain(semantic_file, caller_scope_id)
        for scope in chain:
            if scope.kind == "class" and scope.scope_id != caller_scope_id:
                continue
            if name in scope.global_names or name in scope.nonlocal_names:
                return _Resolution(
                    None,
                    "unresolved",
                    f"'{name}' uses a global/nonlocal declaration that this conservative resolver does not follow.",
                )
            events = self._events(semantic_file, scope.scope_id, name)
            assignments = [item for item in events if item.kind == "assignment"]
            definition_events = [item for item in events if item.kind == "definition"]
            child_candidates = self.children.get((scope.scope_id, name), [])
            if len(child_candidates) == 1:
                definition = child_candidates[0]
                definition_event = next(
                    (
                        item
                        for item in definition_events
                        if item.line == definition.line
                    ),
                    None,
                )
                if assignments:
                    return _Resolution(
                        None,
                        "unresolved",
                        f"'{name}' has both a definition and another assignment in the visible scope.",
                    )
                if definition_event is not None and not definition_event.straight_line:
                    return _Resolution(
                        None,
                        "unresolved",
                        f"Definition '{name}' is conditional or occurs in dynamic control flow.",
                    )
                if scope.scope_id == caller_scope_id and definition.line >= line:
                    return _Resolution(
                        None,
                        "unresolved",
                        f"Definition '{name}' has not executed before this call in the same scope.",
                    )
                return _Resolution(
                    definition,
                    "high",
                    f"'{name}' uniquely matches a definition in the visible lexical scope.",
                )
            if len(child_candidates) > 1:
                return _Resolution(
                    None,
                    "unresolved",
                    f"Multiple visible definitions are named '{name}'.",
                )

            if name in scope.parameter_names or assignments:
                source = "parameter" if name in scope.parameter_names else "local assignment"
                return _Resolution(
                    None,
                    "unresolved",
                    f"'{name}' is a {source}; its runtime callable value is not known.",
                )

            imported = self._resolve_import_binding(
                semantic_file, scope.scope_id, name, line
            )
            if imported is not None:
                return imported

            if scope.kind == "class":
                break

        module = semantic_file.analysis.module
        candidates = self.by_module_qname.get((module, name), [])
        module_scope_id = f"{module or '<root>'}:<module>"
        module_assignments = [
            item
            for item in self._events(semantic_file, module_scope_id, name)
            if item.kind == "assignment"
        ]
        if module_assignments:
            return _Resolution(
                None,
                "unresolved",
                f"Module name '{name}' is assigned dynamically, so a definition match is unsafe.",
            )
        if len(candidates) == 1:
            label = "reference" if reference_only else "call"
            return _Resolution(
                candidates[0],
                "high",
                f"The {label} uniquely matches '{name}' in the same module.",
            )
        if len(candidates) > 1:
            return _Resolution(
                None,
                "unresolved",
                f"Multiple same-module definitions are named '{name}'.",
            )
        return _Resolution(
            None,
            "unresolved",
            f"No internal definition or supported import binding matches '{name}'.",
        )

    def _visible_imports(
        self, semantic_file: SemanticFile, scope_id: str
    ) -> list[ImportInfo]:
        return [
            item for item in semantic_file.analysis.imports if item.scope_id == scope_id
        ]

    def _resolve_import_binding(
        self,
        semantic_file: SemanticFile,
        scope_id: str,
        name: str,
        line: int,
    ) -> _Resolution | None:
        matches: list[tuple[ImportInfo, ImportAlias]] = []
        for imported in self._visible_imports(semantic_file, scope_id):
            if imported.line > line:
                continue
            for alias in imported.aliases:
                if alias.bound_name == name:
                    matches.append((imported, alias))
        if not matches:
            return None
        if len(matches) > 1:
            return _Resolution(
                None,
                "unresolved",
                f"More than one import binds '{name}' in this scope.",
            )
        imported, alias = matches[0]
        if imported.module or imported.level:
            candidates: list[SymbolDefinition] = []
            for module in imported.resolved_modules:
                candidates.extend(
                    self.by_module_qname.get((module, alias.imported_name), [])
                )
                submodule = f"{module}.{alias.imported_name}"
                if submodule in self.module_names:
                    return _Resolution(
                        None,
                        "unresolved",
                        f"'{name}' is an imported internal module, not a statically defined callable.",
                    )
                if module.endswith(f".{alias.imported_name}") or module == alias.imported_name:
                    return _Resolution(
                        None,
                        "unresolved",
                        f"'{name}' is an imported internal module, not a statically defined callable.",
                    )
            unique = {item.symbol_id: item for item in candidates}
            if len(unique) == 1:
                symbol = next(iter(unique.values()))
                return _Resolution(
                    symbol,
                    "high",
                    f"Import binding '{name}' explicitly names '{symbol.symbol_id}'.",
                )
            if len(unique) > 1:
                return _Resolution(
                    None,
                    "unresolved",
                    f"Import binding '{name}' matches multiple internal definitions.",
                )
        elif imported.resolved_modules:
            return _Resolution(
                None,
                "unresolved",
                f"'{name}' is an imported internal module, not a statically defined callable.",
            )
        return _Resolution(
            None,
            "unresolved",
            f"Import binding '{name}' does not identify an internal callable definition.",
        )

    @staticmethod
    def _attribute_parts(node: ast.AST) -> list[str] | None:
        parts: list[str] = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name):
            return None
        parts.append(current.id)
        return list(reversed(parts))

    def _resolve_attribute(
        self,
        semantic_file: SemanticFile,
        call: RawCall,
        attribute: ast.Attribute,
    ) -> _Resolution:
        if isinstance(attribute.value, ast.Call):
            constructor = self._resolve_reference(
                semantic_file,
                call.caller_symbol_id,
                attribute.value.func,
                call.line,
            )
            if constructor.symbol is not None and constructor.symbol.kind == "class":
                method = self._method(constructor.symbol, attribute.attr)
                if method is not None:
                    return _Resolution(
                        method,
                        "medium",
                        f"A direct '{constructor.symbol.name}(...)' result receives '.{attribute.attr}()', but runtime object dispatch may differ.",
                    )
            return _Resolution(
                None,
                "unresolved",
                "The method receiver is produced by a call whose runtime type is not safely known.",
            )

        parts = self._attribute_parts(attribute)
        if not parts:
            return _Resolution(
                None,
                "unresolved",
                "The attribute receiver is a dynamic expression rather than a stable name.",
            )

        scope = semantic_file.scopes.get(call.caller_symbol_id)
        if len(parts) == 2 and scope is not None:
            receiver, method_name = parts
            if (
                scope.enclosing_class_id
                and receiver == scope.first_parameter
                and receiver in {"self", "cls"}
            ):
                class_symbol = self.by_id.get(scope.enclosing_class_id)
                method = self._method(class_symbol, method_name) if class_symbol else None
                if method is not None:
                    return _Resolution(
                        method,
                        "medium",
                        f"'{receiver}' is the first parameter of a method on '{class_symbol.name}', but Python runtime dispatch can override '.{method_name}()'.",
                    )

            inferred = self._resolve_assigned_receiver(
                semantic_file,
                call.caller_symbol_id,
                receiver,
                method_name,
                call.line,
            )
            if inferred is not None:
                return inferred

        module_resolution = self._resolve_module_attribute(
            semantic_file, call.caller_symbol_id, parts, call.line
        )
        if module_resolution is not None:
            return module_resolution

        first = self._resolve_name(
            semantic_file,
            call.caller_symbol_id,
            parts[0],
            call.line,
            reference_only=True,
        )
        if first.symbol is not None and first.symbol.kind == "class" and len(parts) == 2:
            method = self._method(first.symbol, parts[1])
            if method is not None:
                return _Resolution(
                    method,
                    "high",
                    f"'{parts[0]}' resolves to class '{first.symbol.symbol_id}' and directly names its '{parts[1]}' method.",
                )
        return _Resolution(
            None,
            "unresolved",
            f"The receiver in '{'.'.join(parts)}' has no safely inferred internal type or module binding.",
        )

    def _resolve_reference(
        self,
        semantic_file: SemanticFile,
        caller_scope_id: str,
        node: ast.AST,
        line: int,
    ) -> _Resolution:
        if isinstance(node, ast.Name):
            return self._resolve_name(
                semantic_file,
                caller_scope_id,
                node.id,
                line,
                reference_only=True,
            )
        parts = self._attribute_parts(node)
        if parts:
            module_result = self._resolve_module_attribute(
                semantic_file, caller_scope_id, parts, line
            )
            if module_result is not None:
                return module_result
        return _Resolution(
            None,
            "unresolved",
            "The reference is not a supported static name or module-qualified symbol.",
        )

    def _module_bindings(
        self,
        semantic_file: SemanticFile,
        caller_scope_id: str,
        line: int,
    ) -> list[tuple[ImportInfo, ImportAlias]]:
        visible: list[tuple[ImportInfo, ImportAlias]] = []
        for scope in self._scope_chain(semantic_file, caller_scope_id):
            if scope.kind == "class" and scope.scope_id != caller_scope_id:
                continue
            for imported in self._visible_imports(semantic_file, scope.scope_id):
                if imported.line > line:
                    continue
                for alias in imported.aliases:
                    visible.append((imported, alias))
            if scope.kind == "class":
                break
        return visible

    def _resolve_module_attribute(
        self,
        semantic_file: SemanticFile,
        caller_scope_id: str,
        parts: list[str],
        line: int,
    ) -> _Resolution | None:
        candidates: list[tuple[str, int]] = []
        for imported, alias in self._module_bindings(
            semantic_file, caller_scope_id, line
        ):
            if imported.module or imported.level:
                if parts[0] != alias.bound_name:
                    continue
                for module in imported.resolved_modules:
                    submodule = f"{module}.{alias.imported_name}"
                    if submodule in self.module_names:
                        candidates.append((submodule, 1))
                    if module.endswith(f".{alias.imported_name}") or module == alias.imported_name:
                        candidates.append((module, 1))
            else:
                imported_parts = alias.imported_name.split(".")
                if alias.bound_name != imported_parts[0]:
                    if parts[0] == alias.bound_name:
                        candidates.extend(
                            (module, 1) for module in imported.resolved_modules
                        )
                elif parts[: len(imported_parts)] == imported_parts:
                    candidates.extend(
                        (module, len(imported_parts))
                        for module in imported.resolved_modules
                    )
        unique_candidates = sorted(set(candidates), key=lambda item: (-item[1], item[0]))
        resolutions: dict[str, SymbolDefinition] = {}
        for module, consumed in unique_candidates:
            remaining = parts[consumed:]
            if not remaining:
                continue
            direct = self.by_module_qname.get((module, ".".join(remaining)), [])
            for symbol in direct:
                resolutions[symbol.symbol_id] = symbol
            if len(remaining) == 2:
                classes = self.by_module_qname.get((module, remaining[0]), [])
                for class_symbol in classes:
                    if class_symbol.kind == "class":
                        method = self._method(class_symbol, remaining[1])
                        if method is not None:
                            resolutions[method.symbol_id] = method
        if len(resolutions) == 1:
            symbol = next(iter(resolutions.values()))
            return _Resolution(
                symbol,
                "high",
                f"An explicit internal module import uniquely qualifies '{symbol.symbol_id}'.",
            )
        if len(resolutions) > 1:
            return _Resolution(
                None,
                "unresolved",
                f"The module-qualified expression matches multiple internal symbols: '{'.'.join(parts)}'.",
            )
        return None

    def _method(
        self, class_symbol: SymbolDefinition | None, name: str
    ) -> SymbolDefinition | None:
        if class_symbol is None:
            return None
        candidates = self.children.get((class_symbol.symbol_id, name), [])
        return candidates[0] if len(candidates) == 1 else None

    def _resolve_assigned_receiver(
        self,
        semantic_file: SemanticFile,
        scope_id: str,
        receiver: str,
        method_name: str,
        line: int,
    ) -> _Resolution | None:
        assignments = sorted(
            (
                item
                for item in semantic_file.bindings
                if item.scope_id == scope_id
                and item.name == receiver
                and item.kind == "assignment"
                and item.line < line
            ),
            key=lambda item: item.line,
        )
        if not assignments:
            return None
        latest = assignments[-1]
        if latest.value_func is None or not latest.straight_line:
            return _Resolution(
                None,
                "unresolved",
                f"'{receiver}' is assigned, but the assignment does not provide a reliable constructor type.",
            )
        constructor = self._resolve_reference(
            semantic_file, scope_id, latest.value_func, latest.line
        )
        if constructor.symbol is None or constructor.symbol.kind != "class":
            return _Resolution(
                None,
                "unresolved",
                f"The latest assignment to '{receiver}' is not a resolved internal class constructor.",
            )
        method = self._method(constructor.symbol, method_name)
        if method is None:
            return _Resolution(
                None,
                "unresolved",
                f"Class '{constructor.symbol.name}' has no unique static method named '{method_name}'.",
            )
        return _Resolution(
            method,
            "medium",
            f"'{receiver}' is assigned from '{constructor.symbol.name}(...)' on line {latest.line}; runtime reassignment or dispatch could differ.",
        )


def resolve_calls(files: list[SemanticFile]) -> list[CallRelationship]:
    return CallResolver(files).resolve_all()


def infer_error_propagation(
    files: list[SemanticFile],
    relationships: list[CallRelationship],
) -> list[ErrorPropagationEvidence]:
    """Describe call error risk without claiming exception or runtime inference."""

    by_call = {
        (
            item.caller_symbol_id,
            item.file_path,
            item.line,
            item.column,
            item.target_expression,
        ): item
        for item in relationships
    }
    raise_lines_by_symbol = {
        item.symbol_id: sorted(site.line for site in item.raise_sites)
        for semantic_file in files
        for item in semantic_file.function_evidence
        if item.raise_sites
    }
    result: list[ErrorPropagationEvidence] = []
    for semantic_file in files:
        for raw_call in semantic_file.raw_calls:
            scope = semantic_file.scopes.get(raw_call.caller_symbol_id)
            if scope is None or scope.kind not in FUNCTION_SCOPE_KINDS:
                continue
            relationship = by_call.get(
                (
                    raw_call.caller_symbol_id,
                    raw_call.file_path,
                    raw_call.line,
                    raw_call.column,
                    raw_call.target_expression,
                )
            )
            resolved_target = (
                relationship.resolved_target_symbol_id
                if relationship is not None
                else None
            )
            target_raise_lines = list(
                raise_lines_by_symbol.get(resolved_target or "", [])
            )
            if raw_call.protected_by_try_line is not None:
                propagation = "may_be_handled_or_propagate"
                caught = ", ".join(raw_call.caught_expressions)
                reason = (
                    f"The call is inside try line {raw_call.protected_by_try_line}, "
                    f"with handler syntax for {caught}. Static syntax cannot prove the "
                    "raised exception type, handler match, or whether a handler re-raises."
                )
            else:
                propagation = "may_propagate"
                reason = (
                    "Any call can raise at runtime, and no lexically enclosing try body "
                    "with an except handler protects this call site. The AST does not "
                    "reveal actual exception behavior."
                )
            if target_raise_lines:
                line_list = ", ".join(str(line) for line in target_raise_lines)
                reason += (
                    f" The resolved internal target contains explicit raise syntax on "
                    f"line(s) {line_list}; whether those sites execute remains unknown."
                )
            result.append(
                ErrorPropagationEvidence(
                    caller_symbol_id=raw_call.caller_symbol_id,
                    target_expression=raw_call.target_expression,
                    resolved_target_symbol_id=resolved_target,
                    file_path=raw_call.file_path,
                    line=raw_call.line,
                    column=raw_call.column,
                    context=raw_call.error_context,
                    protected_by_try_line=raw_call.protected_by_try_line,
                    caught_expressions=list(raw_call.caught_expressions),
                    target_raise_lines=target_raise_lines,
                    propagation=propagation,
                    confidence="uncertain",
                    reason=reason,
                )
            )
    return sorted(
        result,
        key=lambda item: (
            item.file_path,
            item.line,
            item.column,
            item.caller_symbol_id,
            item.target_expression,
        ),
    )

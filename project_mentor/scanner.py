"""Deterministic, source-only Python repository analysis for Project Mentor."""

from __future__ import annotations

import ast
import heapq
import os
import sys
import tokenize
from pathlib import Path

from project_mentor import PHASE, SCHEMA_VERSION, __version__
from project_mentor.models import (
    EntryPointCandidate,
    FileAnalysis,
    GeneratorMetadata,
    ImportEdge,
    ImportInfo,
    InferredRelationships,
    LearningStep,
    ObservedFacts,
    ProjectAnalysis,
    ProjectMetadata,
    UnusedFileCandidate,
)
from project_mentor.semantic import (
    SemanticFile,
    extract_file_evidence,
    infer_error_propagation,
    resolve_calls,
)


IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "site-packages",
    "venv",
}

MAX_FILES = 2_000
MAX_FILE_SIZE_BYTES = 1_000_000

STATIC_ANALYSIS_WARNINGS = [
    (
        "Call resolution is conservative source evidence, not a runtime guarantee. "
        "Unresolved calls are expected in normal Python projects."
    ),
    (
        "Dynamic imports, monkey patching, decorators, dependency injection, "
        "descriptors, and runtime dispatch can change the callable that executes."
    ),
    (
        "Project Mentor does not import or execute scanned code and does not perform "
        "full type inference or inspect installed dependencies."
    ),
    (
        "Data-flow and mutation records are conservative AST evidence. Annotations "
        "are source text, not inferred types, and uncertain paths are labelled explicitly."
    ),
    (
        "A recorded call may raise, be handled, or complete normally at runtime. Error "
        "propagation evidence does not infer exception types or guarantee control flow."
    ),
]


def _module_name(relative_path: Path) -> str:
    without_suffix = relative_path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _read_source(path: Path) -> str:
    with tokenize.open(path) as handle:
        return handle.read()


def _analyse_file_with_semantics(root: Path, path: Path) -> SemanticFile:
    relative = path.relative_to(root)
    file_path = relative.as_posix()
    module = _module_name(relative)
    fallback = FileAnalysis(path=file_path, module=module)

    try:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            fallback.parse_error = (
                f"Skipped: file is larger than {MAX_FILE_SIZE_BYTES:,} bytes."
            )
            return SemanticFile(fallback, None)

        source = _read_source(path)
        fallback.line_count = len(source.splitlines())
        tree = ast.parse(source, filename=file_path)
        return extract_file_evidence(module, file_path, source, tree)
    except (OSError, SyntaxError, UnicodeError) as exc:
        if isinstance(exc, SyntaxError):
            location = f" on line {exc.lineno}" if exc.lineno else ""
            fallback.parse_error = f"Syntax error{location}: {exc.msg}"
        else:
            fallback.parse_error = f"Could not read file: {exc}"
        return SemanticFile(fallback, None)


def analyse_file(root: Path, path: Path) -> FileAnalysis:
    """Analyse one file without importing it (public Phase 1 compatibility API)."""

    return _analyse_file_with_semantics(root, path).analysis


def discover_python_files(root: Path) -> list[Path]:
    discovered: list[Path] = []

    for directory, child_directories, filenames in os.walk(root, followlinks=False):
        child_directories[:] = sorted(
            name
            for name in child_directories
            if name not in IGNORED_DIRECTORIES and not name.startswith(".")
        )
        directory_path = Path(directory)
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            candidate = directory_path / filename
            # Avoid reading a source-file symlink that may point outside the root.
            if candidate.is_symlink():
                continue
            discovered.append(candidate)
            if len(discovered) > MAX_FILES:
                raise ValueError(
                    f"This project contains more than {MAX_FILES:,} Python files. "
                    "Choose a smaller folder for this version."
                )

    return sorted(discovered, key=lambda item: item.relative_to(root).as_posix())


def _package_parts(file: FileAnalysis) -> list[str]:
    parts = file.module.split(".") if file.module else []
    if Path(file.path).name != "__init__.py" and parts:
        parts.pop()
    return parts


def _import_candidates(file: FileAnalysis, imported: ImportInfo) -> list[str]:
    package_parts = _package_parts(file)
    candidates: list[str] = []
    if imported.level:
        keep = max(0, len(package_parts) - (imported.level - 1))
        base_parts = package_parts[:keep]
        if imported.module:
            candidates.append(".".join([*base_parts, imported.module]))
        else:
            candidates.extend(
                ".".join([*base_parts, name]) for name in imported.names
            )
    elif imported.module:
        candidates.append(imported.module)
    else:
        candidates.extend(imported.names)
    return [candidate for candidate in candidates if candidate]


def _resolve_candidate(candidate: str, module_names: set[str]) -> str | None:
    if candidate in module_names:
        return candidate
    parts = candidate.split(".")
    for length in range(len(parts) - 1, 0, -1):
        parent = ".".join(parts[:length])
        if parent in module_names:
            return parent
    return None


def _classify_imports(
    files: list[FileAnalysis], module_names: set[str]
) -> tuple[dict[str, set[str]], set[str]]:
    dependencies: dict[str, set[str]] = {
        file.module: set() for file in files if file.module
    }
    external_dependencies: set[str] = set()

    for file in files:
        for imported in file.imports:
            candidates = _import_candidates(file, imported)
            resolved = {
                target
                for candidate in candidates
                if (target := _resolve_candidate(candidate, module_names)) is not None
            }
            resolved.discard(file.module)
            imported.resolved_modules = sorted(resolved)

            if resolved or imported.level:
                imported.classification = "internal"
                if file.module:
                    dependencies[file.module].update(resolved)
                continue

            top_levels = {candidate.split(".")[0] for candidate in candidates}
            if top_levels and top_levels.issubset(sys.stdlib_module_names):
                imported.classification = "standard_library"
            else:
                imported.classification = "external"
                external_dependencies.update(top_levels)

    return dependencies, external_dependencies


def _import_edges(
    files: list[FileAnalysis], dependencies: dict[str, set[str]]
) -> list[ImportEdge]:
    by_module = {file.module: file for file in files if file.module}
    edges: list[ImportEdge] = []
    for source_module in sorted(dependencies):
        source = by_module.get(source_module)
        if source is None:
            continue
        for target_module in sorted(dependencies[source_module]):
            target = by_module.get(target_module)
            if target is not None:
                edges.append(
                    ImportEdge(
                        source_path=source.path,
                        source_module=source_module,
                        target_path=target.path,
                        target_module=target_module,
                    )
                )
    return edges


def _entry_points(
    files: list[FileAnalysis], dependencies: dict[str, set[str]]
) -> list[EntryPointCandidate]:
    imported_modules = {
        target for targets in dependencies.values() for target in targets
    }
    candidates: list[EntryPointCandidate] = []
    filename_scores = {
        "main.py": (40, "Conventional main.py filename"),
        "app.py": (30, "Conventional application filename"),
        "run.py": (25, "Conventional runner filename"),
        "manage.py": (20, "Conventional management filename"),
        "cli.py": (20, "Conventional command-line entry filename"),
    }

    for file in files:
        if file.parse_error:
            continue
        path_parts = Path(file.path).parts
        basename = Path(file.path).name.lower()
        if (
            "tests" in path_parts
            or "test" in path_parts
            or basename.startswith("test_")
            or basename == "__init__.py"
        ):
            continue
        score = 0
        reasons: list[str] = []
        if file.has_main_guard:
            score += 100
            reasons.append("Contains an if __name__ == '__main__' guard")
        if basename in filename_scores:
            points, reason = filename_scores[basename]
            score += points
            reasons.append(reason)
        top_level_functions = {
            item.name for item in file.functions if "." not in item.name
        }
        if "main" in top_level_functions:
            score += 25
            reasons.append("Defines a top-level main() function")
        framework_calls = {
            call.target.split(".")[-1]
            for call in file.calls
            if call.caller == "<module>"
        }
        frameworks = sorted(
            framework_calls.intersection({"FastAPI", "Flask", "Typer"})
        )
        if frameworks:
            score += 60
            reasons.append(f"Creates a {frameworks[0]} application at module level")
        if score and file.module and file.module not in imported_modules:
            score += 5
            reasons.append("No other local module imports it")
        if score:
            confidence = "high" if score >= 80 else "medium" if score >= 30 else "low"
            candidates.append(
                EntryPointCandidate(file.path, score, confidence, reasons)
            )
    return sorted(candidates, key=lambda item: (-item.score, item.path))[:5]


def _is_test_file(file: FileAnalysis) -> bool:
    path = Path(file.path)
    return (
        path.name.startswith("test_")
        or path.name.endswith("_test.py")
        or "tests" in path.parts
        or "test" in path.parts
    )


def _learning_order(
    files: list[FileAnalysis],
    dependencies: dict[str, set[str]],
    entry_points: list[EntryPointCandidate],
) -> list[LearningStep]:
    """Topologically order modules, using learning value as the tie-breaker."""

    by_module = {file.module: file for file in files if file.module}
    imported_by_count = {module: 0 for module in by_module}
    dependents: dict[str, set[str]] = {module: set() for module in by_module}
    remaining_dependencies: dict[str, int] = {}
    for module in by_module:
        local_dependencies = {
            item for item in dependencies.get(module, set()) if item in by_module
        }
        remaining_dependencies[module] = len(local_dependencies)
        for dependency in local_dependencies:
            dependents[dependency].add(module)
            imported_by_count[dependency] += 1

    entry_paths = {candidate.path for candidate in entry_points[:1]}

    def priority(module: str) -> tuple[int, int, int, str]:
        file = by_module[module]
        category = 2 if file.is_empty_package_marker else 1 if _is_test_file(file) else 0
        entry_penalty = 1 if file.path in entry_paths else 0
        return category, entry_penalty, -imported_by_count[module], file.path

    ready = [
        (priority(module), module)
        for module, count in remaining_dependencies.items()
        if count == 0
    ]
    heapq.heapify(ready)
    ordered_modules: list[str] = []
    while ready:
        _, module = heapq.heappop(ready)
        ordered_modules.append(module)
        for dependent in sorted(dependents[module]):
            remaining_dependencies[dependent] -= 1
            if remaining_dependencies[dependent] == 0:
                heapq.heappush(ready, (priority(dependent), dependent))

    cycle_modules = sorted(
        set(by_module).difference(ordered_modules), key=priority
    )
    ordered_modules.extend(cycle_modules)
    cycle_set = set(cycle_modules)

    result: list[LearningStep] = []
    for position, module in enumerate(ordered_modules, start=1):
        file = by_module[module]
        local_dependencies = sorted(
            item for item in dependencies.get(module, set()) if item in by_module
        )
        reasons: list[str] = []
        if file.parse_error:
            reasons.append("Review its parse error before studying the code")
        elif file.is_empty_package_marker:
            reasons.append("Empty package marker with little code to learn")
        elif _is_test_file(file):
            reasons.append("Test file; study after the production behavior it checks")
        elif local_dependencies:
            dependency_paths = [by_module[item].path for item in local_dependencies]
            reasons.append("Study after " + ", ".join(dependency_paths))
        elif imported_by_count[module]:
            count = imported_by_count[module]
            reasons.append(f"Foundation module used by {count} other local module(s)")
        else:
            reasons.append("Independent production module with no detected local dependencies")
        if module in cycle_set:
            reasons.append("Part of an import cycle, so no perfect dependency order exists")
        if file.path in entry_paths:
            reasons.append("Likely entry point; its dependencies should make sense first")
        result.append(
            LearningStep(position, file.path, ". ".join(reasons) + ".")
        )
    return result


def _unused_files(
    files: list[FileAnalysis],
    dependencies: dict[str, set[str]],
    entry_points: list[EntryPointCandidate],
) -> list[UnusedFileCandidate]:
    imported_modules = {
        target for targets in dependencies.values() for target in targets
    }
    entry_paths = {candidate.path for candidate in entry_points}
    candidates: list[UnusedFileCandidate] = []
    for file in files:
        path = Path(file.path)
        if (
            not file.module
            or file.parse_error
            or file.path in entry_paths
            or file.module in imported_modules
            or path.name == "__init__.py"
            or _is_test_file(file)
        ):
            continue
        file.possibly_unused = True
        candidates.append(
            UnusedFileCandidate(
                path=file.path,
                reason=(
                    "No local file imports it and it was not identified as an entry point. "
                    "Dynamic imports and plugin loading can make this a false positive."
                ),
            )
        )
    return sorted(candidates, key=lambda item: item.path)


def scan_project(path: str | Path) -> ProjectAnalysis:
    root = Path(path).expanduser()
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            f"Project folder does not exist or cannot be opened: {path}"
        ) from exc
    if not root.is_dir():
        raise ValueError(f"The selected path is not a folder: {root}")

    python_paths = discover_python_files(root)
    semantic_files = [
        _analyse_file_with_semantics(root, item) for item in python_paths
    ]
    files = [item.analysis for item in semantic_files]
    module_names = {file.module for file in files if file.module}
    dependencies, external_dependencies = _classify_imports(files, module_names)
    entry_points = _entry_points(files, dependencies)
    learning_order = _learning_order(files, dependencies, entry_points)
    import_edges = _import_edges(files, dependencies)
    unused_files = _unused_files(files, dependencies, entry_points)
    call_relationships = resolve_calls(semantic_files)
    error_propagation = infer_error_propagation(
        semantic_files, call_relationships
    )
    symbols = sorted(
        (symbol for item in semantic_files for symbol in item.symbols),
        key=lambda item: (item.file_path, item.line, item.qualified_name, item.symbol_id),
    )
    function_evidence = sorted(
        (
            evidence
            for semantic_file in semantic_files
            for evidence in semantic_file.function_evidence
        ),
        key=lambda item: (item.file_path, item.symbol_id),
    )
    data_flows = sorted(
        (
            relationship
            for semantic_file in semantic_files
            for relationship in semantic_file.data_flows
        ),
        key=lambda item: (
            item.file_path,
            item.line,
            item.column,
            item.function_symbol_id,
            item.target_expression,
            item.source_expression,
        ),
    )

    parsed_files = [file for file in files if not file.parse_error]
    import_classifications = [
        imported.classification
        for file in parsed_files
        for imported in file.imports
    ]
    total_imports = sum(len(file.imports) for file in parsed_files)
    total_functions = sum(len(file.functions) for file in parsed_files)
    total_classes = sum(len(file.classes) for file in parsed_files)
    total_calls = sum(len(file.calls) for file in parsed_files)
    resolved = [
        item
        for item in call_relationships
        if item.resolved_target_symbol_id is not None
    ]
    output_sites = [
        site for item in function_evidence for site in item.output_sites
    ]
    mutations = [
        mutation for item in function_evidence for mutation in item.mutations
    ]
    raise_sites = [
        site for item in function_evidence for site in item.raise_sites
    ]
    exception_paths = [
        path for item in function_evidence for path in item.exception_paths
    ]
    summary = {
        "python_files": len(files),
        "parsed_files": len(parsed_files),
        "parse_errors": len(files) - len(parsed_files),
        "lines": sum(file.line_count for file in parsed_files),
        "imports": total_imports,
        "functions": total_functions,
        "classes": total_classes,
        "calls": total_calls,
        "symbols": len(symbols),
        "resolved_calls": len(resolved),
        "high_confidence_calls": sum(
            item.confidence == "high" for item in call_relationships
        ),
        "medium_confidence_calls": sum(
            item.confidence == "medium" for item in call_relationships
        ),
        "unresolved_calls": sum(
            item.confidence == "unresolved" for item in call_relationships
        ),
        "internal_imports": import_classifications.count("internal"),
        "external_imports": import_classifications.count("external"),
        "standard_library_imports": import_classifications.count("standard_library"),
        "possibly_unused": len(unused_files),
        "parameters": sum(
            len(item.parameters) for item in function_evidence
        ),
        "output_sites": len(output_sites),
        "data_flows": len(data_flows),
        "mutations": len(mutations),
        "raise_sites": len(raise_sites),
        "exception_paths": len(exception_paths),
        "calls_with_error_evidence": len(error_propagation),
        "description": (
            f"Found {len(files)} Python file(s), {len(symbols)} symbol(s), and "
            f"resolved {len(resolved)} of {total_calls} call(s); recorded "
            f"{len(data_flows)} data-flow relationship(s) and "
            f"{len(error_propagation)} call error-evidence record(s) conservatively."
        ),
    }

    return ProjectAnalysis(
        schema_version=SCHEMA_VERSION,
        project=ProjectMetadata(name=root.name, root=str(root)),
        generator=GeneratorMetadata(
            name="Project Mentor", version=__version__, phase=PHASE
        ),
        summary=summary,
        observed_facts=ObservedFacts(
            files=files,
            symbols=symbols,
            function_evidence=function_evidence,
        ),
        inferred_relationships=InferredRelationships(
            import_edges=import_edges,
            call_relationships=call_relationships,
            data_flows=data_flows,
            error_propagation=error_propagation,
            entry_points=entry_points,
            learning_order=learning_order,
            external_dependencies=sorted(external_dependencies),
            unused_files=unused_files,
        ),
        warnings=list(STATIC_ANALYSIS_WARNINGS),
    )

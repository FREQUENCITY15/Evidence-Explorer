from pathlib import Path
import tempfile
import unittest

from project_mentor.scanner import scan_project


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class DataFlowAndErrorEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def function_evidence(self, result, symbol_id: str):
        return next(
            item for item in result.function_evidence if item.symbol_id == symbol_id
        )

    def test_parameters_and_return_yield_sites_are_observed(self) -> None:
        write(
            self.root / "pipeline.py",
            '''def transform(first, /, second: int = 2, *items: str, flag=True, **options) -> int:
    total = first + second
    if flag:
        yield total
    return total
''',
        )

        result = scan_project(self.root)
        evidence = self.function_evidence(result, "pipeline:transform")

        self.assertEqual(
            [(item.name, item.kind) for item in evidence.parameters],
            [
                ("first", "positional_only"),
                ("second", "positional_or_keyword"),
                ("items", "var_positional"),
                ("flag", "keyword_only"),
                ("options", "var_keyword"),
            ],
        )
        self.assertEqual(evidence.parameters[1].annotation, "int")
        self.assertEqual(evidence.parameters[1].default, "2")
        self.assertEqual(evidence.parameters[3].default, "True")
        self.assertEqual(
            [(item.kind, item.expression) for item in evidence.output_sites],
            [("yield", "total"), ("return", "total")],
        )
        self.assertEqual(evidence.output_sites[0].confidence, "uncertain")
        self.assertEqual(evidence.output_sites[1].confidence, "high")

    def test_straightforward_and_uncertain_data_flows_are_separated(self) -> None:
        write(
            self.root / "flow.py",
            '''def arrange(source, pair, flag):
    direct = source
    left, right = pair
    if flag:
        direct = normalize(source)
    return direct
''',
        )

        result = scan_project(self.root)
        flows = [
            item for item in result.data_flows
            if item.function_symbol_id == "flow:arrange"
        ]

        direct = next(
            item
            for item in flows
            if item.target_expression == "direct" and item.line == 2
        )
        conditional = next(item for item in flows if item.line == 5)
        unpacked = [item for item in flows if item.line == 3]
        self.assertEqual(direct.source_names, ["source"])
        self.assertEqual(direct.confidence, "high")
        self.assertEqual(conditional.confidence, "uncertain")
        self.assertEqual(
            [(item.target_expression, item.confidence) for item in unpacked],
            [("left", "uncertain"), ("right", "uncertain")],
        )
        self.assertTrue(all(item.reason for item in flows))

    def test_state_mutations_include_direct_writes_and_cautious_method_names(self) -> None:
        write(
            self.root / "state.py",
            '''counter = 0

class Store:
    def update(self, value, key, flag):
        global counter
        self.value = value
        self.items.append(value)
        self.mapping[key] += 1
        counter = value
        if flag:
            self.value = None
''',
        )

        result = scan_project(self.root)
        evidence = self.function_evidence(result, "state:Store.update")
        mutations = evidence.mutations

        attribute = next(item for item in mutations if item.line == 6)
        method = next(item for item in mutations if item.line == 7)
        indexed = next(item for item in mutations if item.line == 8)
        global_write = next(item for item in mutations if item.line == 9)
        conditional = next(item for item in mutations if item.line == 11)
        self.assertEqual(attribute.mutation_kind, "attribute_assignment")
        self.assertEqual(attribute.confidence, "high")
        self.assertEqual(method.mutation_kind, "possible_mutator_method_call")
        self.assertEqual(method.confidence, "uncertain")
        self.assertEqual(indexed.mutation_kind, "subscript_augmented_assignment")
        self.assertEqual(indexed.confidence, "uncertain")
        self.assertEqual(global_write.mutation_kind, "global_assignment")
        self.assertEqual(conditional.confidence, "uncertain")

    def test_raise_try_paths_and_call_error_context_are_reported(self) -> None:
        write(
            self.root / "errors.py",
            '''def risky():
    raise ValueError("bad")

def run():
    try:
        risky()
    except ValueError as exc:
        log(exc)
    else:
        finish()
    finally:
        cleanup()
    outside()
''',
        )

        result = scan_project(self.root)
        risky = self.function_evidence(result, "errors:risky")
        run = self.function_evidence(result, "errors:run")

        self.assertEqual(risky.raise_sites[0].exception_expression, "ValueError('bad')")
        self.assertEqual(
            [item.path_kind for item in run.exception_paths],
            ["try_body", "except_handler", "try_else", "finally"],
        )
        calls = {
            item.target_expression: item
            for item in result.error_propagation
            if item.caller_symbol_id == "errors:run"
        }
        self.assertEqual(calls["risky"].protected_by_try_line, 5)
        self.assertEqual(calls["risky"].caught_expressions, ["ValueError"])
        self.assertEqual(calls["risky"].target_raise_lines, [2])
        self.assertEqual(
            calls["risky"].propagation, "may_be_handled_or_propagate"
        )
        self.assertEqual(calls["log"].context, "except_handler")
        self.assertEqual(calls["cleanup"].context, "finally")
        self.assertEqual(calls["outside"].propagation, "may_propagate")
        self.assertTrue(all(item.confidence == "uncertain" for item in calls.values()))

    def test_scanning_never_executes_import_or_module_code(self) -> None:
        marker = self.root / "executed.txt"
        write(
            self.root / "dangerous.py",
            f'''from pathlib import Path
Path({str(marker)!r}).write_text("executed")

def safe(value):
    return value
''',
        )

        result = scan_project(self.root)

        self.assertEqual(result.summary["parsed_files"], 1)
        self.assertFalse(marker.exists())

    def test_browser_trace_includes_phase_1_3_evidence_sections(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        index = (project_root / "project_mentor" / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        app = (project_root / "project_mentor" / "static" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("Phase 6", index)
        self.assertIn("Function evidence trace", index)
        for heading in (
            "Inputs (parameters)",
            "Outputs (return and yield sites)",
            "Detected state mutations",
            "Error paths and propagation",
            "Straightforward assignment and data flow",
        ):
            self.assertIn(heading, app)


if __name__ == "__main__":
    unittest.main()

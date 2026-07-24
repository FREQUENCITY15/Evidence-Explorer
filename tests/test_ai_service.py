import json
from pathlib import Path
import tempfile
import unittest

from project_mentor.ai_service import (
    AIErrorCode,
    GroundedAIService,
    select_default_model,
)
from project_mentor.config import Settings
from project_mentor.context_builder import EvidenceContextBuilder, make_evidence_item
from project_mentor.ollama_client import (
    OllamaChatResponse,
    OllamaError,
    OllamaErrorCode,
    OllamaModel,
    OllamaResult,
)
from project_mentor.scanner import scan_project
from project_mentor.teach_service import TeachLessonService


class FakeOllamaClient:
    def __init__(
        self,
        *,
        models: list[OllamaModel] | None = None,
        listing_error: OllamaError | None = None,
        malformed_answer: bool = False,
        chat_contents: list[str] | None = None,
    ) -> None:
        self.models = [OllamaModel("test-model:latest")] if models is None else models
        self.listing_error = listing_error
        self.malformed_answer = malformed_answer
        self.chat_contents = chat_contents
        self.chat_calls = 0
        self.messages = None
        self.response_format = None

    async def list_models(self):
        if self.listing_error:
            return OllamaResult(error=self.listing_error)
        return OllamaResult(value=self.models)

    async def chat(self, *, model, messages, response_format=None):
        self.messages = messages
        self.response_format = response_format
        self.chat_calls += 1
        if self.chat_contents is not None:
            content = self.chat_contents[min(self.chat_calls - 1, len(self.chat_contents) - 1)]
        elif self.malformed_answer:
            content = "not-json"
        else:
            evidence_id = messages[1]["content"].split('"evidence_id":"', 1)[1].split('"', 1)[0]
            content = json.dumps(
                {
                    "answer": "The selected evidence defines a function.",
                    "citations": [evidence_id],
                    "evidence_insufficient": False,
                }
            )
        return OllamaResult(
            value=OllamaChatResponse(
                model=model,
                content=content,
                prompt_eval_count=20,
                eval_count=10,
                total_duration_ns=1_000,
            )
        )


class GroundedAIServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        (root / "app.py").write_text(
            "def run(value: str) -> str:\n    return value.strip()\n",
            encoding="utf-8",
        )
        self.analysis = scan_project(root)
        self.settings = Settings.from_env({})

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def service(self, client) -> GroundedAIService:
        return GroundedAIService(
            self.settings, client, EvidenceContextBuilder(12_000)
        )

    async def test_map_explanation_uses_shared_grounded_service(self) -> None:
        client = FakeOllamaClient()
        result = await self.service(client).explain(
            self.analysis,
            model="test-model:latest",
            question="Explain run.",
            selected_symbol_id="app:run",
            workflow="map",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.response.requested_model, "test-model:latest")
        self.assertEqual(len(result.response.answer.citations), 1)
        self.assertIn("source of truth", client.messages[0]["content"])
        self.assertEqual(client.response_format["type"], "object")
        response_dict = result.response.to_dict()
        self.assertIn("observed_facts", response_dict["deterministic_evidence"])
        self.assertIn(
            "local_model_interpretation", response_dict
        )

    async def test_unavailable_ollama_does_not_damage_scan_result(self) -> None:
        before = self.analysis.to_dict()
        client = FakeOllamaClient(
            listing_error=OllamaError(
                OllamaErrorCode.UNAVAILABLE, "Project Mentor could not connect to Ollama."
            )
        )
        result = await self.service(client).explain(
            self.analysis,
            model="test-model:latest",
            question="Explain run.",
            selected_symbol_id="app:run",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, AIErrorCode.OLLAMA)
        self.assertEqual(self.analysis.to_dict(), before)
        self.assertEqual(self.analysis.summary["python_files"], 1)

    async def test_no_models_and_uninstalled_selection_fail_gracefully(self) -> None:
        no_models = await self.service(FakeOllamaClient(models=[])).explain(
            self.analysis,
            model="test-model:latest",
            question="Explain run.",
            selected_symbol_id="app:run",
        )
        wrong_model = await self.service(FakeOllamaClient()).explain(
            self.analysis,
            model="missing-model",
            question="Explain run.",
            selected_symbol_id="app:run",
        )
        self.assertEqual(no_models.error.code, AIErrorCode.NO_MODELS)
        self.assertEqual(wrong_model.error.code, AIErrorCode.MODEL_NOT_INSTALLED)

    async def test_malformed_model_json_is_not_displayed_as_grounded(self) -> None:
        client = FakeOllamaClient(malformed_answer=True)
        result = await self.service(client).explain(
            self.analysis,
            model="test-model:latest",
            question="Explain run.",
            selected_symbol_id="app:run",
        )
        self.assertEqual(result.error.code, AIErrorCode.INVALID_MODEL_RESPONSE)
        self.assertEqual(client.chat_calls, 2)

    async def test_malformed_first_response_gets_one_valid_retry(self) -> None:
        client = FakeOllamaClient(chat_contents=[
            "not-json",
            json.dumps({"answer": "Recovered.", "citations": [], "evidence_insufficient": True}),
        ])
        result = await self.service(client).explain(
            self.analysis, model="test-model:latest", question="Explain run.", selected_symbol_id="app:run"
        )
        self.assertTrue(result.ok)
        self.assertEqual(client.chat_calls, 2)

    async def test_scan_evidence_is_unchanged_after_two_malformed_responses(self) -> None:
        before = self.analysis.to_dict()
        client = FakeOllamaClient(chat_contents=["not-json", "still-not-json"])
        result = await self.service(client).explain(
            self.analysis, model="test-model:latest", question="Explain run.", selected_symbol_id="app:run"
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, AIErrorCode.INVALID_MODEL_RESPONSE)
        self.assertEqual(client.chat_calls, 2)
        self.assertEqual(self.analysis.to_dict(), before)

    async def test_failure_logs_contain_metadata_but_not_content(self) -> None:
        client = FakeOllamaClient(chat_contents=["not-json", "still-not-json"])
        with self.assertLogs("project_mentor.ai_service", level="WARNING") as captured:
            await self.service(client).explain(
                self.analysis,
                model="test-model:latest",
                question="SECRET USER QUESTION",
                selected_symbol_id="app:run",
            )
        joined = "\n".join(captured.output)
        self.assertIn("failure_category=malformed_json", joined)
        self.assertNotIn("SECRET USER QUESTION", joined)
        self.assertNotIn("still-not-json", joined)

    async def test_teach_explanation_uses_only_lesson_allow_list(self) -> None:
        lesson_item = make_evidence_item(
            "observed_fact",
            "teach_fact",
            "Only this deterministic lesson fact is allowed.",
            file_path="app.py",
            line_start=1,
            line_end=2,
            symbol_id="app:run",
        )
        client = FakeOllamaClient()
        result = await self.service(client).explain(
            self.analysis,
            model="test-model:latest",
            question="Teach this lesson.",
            selected_symbol_id="app:run",
            workflow="teach",
            evidence_items=(lesson_item,),
        )

        self.assertTrue(result.ok)
        supplied = client.messages[1]["content"]
        self.assertIn(lesson_item.evidence_id, supplied)
        self.assertIn("Only this deterministic lesson fact is allowed.", supplied)
        self.assertNotIn("bounded_source_snippet", supplied)
        self.assertIn("Teach only from supplied evidence", client.messages[0]["content"])
        self.assertEqual(result.response.answer.citations[0].evidence_id, lesson_item.evidence_id)

    async def test_local_model_cannot_change_deterministic_quiz_answers(self) -> None:
        teach = TeachLessonService()
        before = teach.build(self.analysis, "app:run")
        answer_key_before = tuple(
            item.correct_option_id for item in before.lesson.quiz
        )
        client = FakeOllamaClient(
            chat_contents=[
                json.dumps(
                    {
                        "answer": "I would prefer different quiz answers.",
                        "citations": [before.evidence_items[0].evidence_id],
                        "evidence_insufficient": False,
                    }
                )
            ]
        )
        result = await self.service(client).explain(
            self.analysis,
            model="test-model:latest",
            question="Explain the lesson.",
            selected_symbol_id="app:run",
            workflow="teach",
            evidence_items=before.evidence_items,
        )
        after = teach.build(self.analysis, "app:run")
        answer_key_after = tuple(item.correct_option_id for item in after.lesson.quiz)

        self.assertTrue(result.ok)
        self.assertEqual(answer_key_before, answer_key_after)
        self.assertNotIn("quiz", result.response.to_dict())

    async def test_teach_model_receives_only_small_prioritised_lesson_allow_list(self) -> None:
        teach = TeachLessonService()
        bundle = teach.build(self.analysis, "app:run")
        client = FakeOllamaClient()
        result = await self.service(client).explain(
            self.analysis,
            model="test-model:latest",
            question="Explain the lesson.",
            selected_symbol_id="app:run",
            workflow="teach",
            evidence_items=bundle.evidence_items,
        )

        self.assertTrue(result.ok)
        self.assertLessEqual(len(bundle.evidence_items), 12)
        self.assertEqual(
            result.response.context.candidate_count, len(bundle.evidence_items)
        )
        self.assertEqual(
            {item.evidence_id for item in result.response.context.evidence_items},
            {item.evidence_id for item in bundle.evidence_items},
        )

    def test_default_model_is_selected_only_from_installed_names(self) -> None:
        models = [OllamaModel("alpha"), OllamaModel("gpt-oss:20b")]
        self.assertEqual(select_default_model(models, ""), "gpt-oss:20b")
        self.assertEqual(select_default_model(models, "alpha"), "alpha")
        self.assertEqual(select_default_model([OllamaModel("alpha")], "gpt-oss:20b"), "alpha")
        self.assertIsNone(select_default_model([], "gpt-oss:20b"))


if __name__ == "__main__":
    unittest.main()

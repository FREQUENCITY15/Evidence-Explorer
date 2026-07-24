"""Shared grounded local-AI service for Project Mentor workflows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Any

from project_mentor.config import Settings
from project_mentor.context_builder import (
    ContextBuildError,
    EvidenceContextBuilder,
    EvidenceItem,
    GroundedContext,
)
from project_mentor.grounding import (
    GroundingValidationError,
    ValidatedGroundedAnswer,
    validate_grounded_answer,
)
from project_mentor.models import ProjectAnalysis
from project_mentor.ollama_client import OllamaClient, OllamaError, OllamaModel


LOGGER = logging.getLogger(__name__)

GROUNDED_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
        "evidence_insufficient": {"type": "boolean"},
    },
    "required": ["answer", "citations", "evidence_insufficient"],
    "additionalProperties": False,
}


class AIErrorCode(str, Enum):
    OLLAMA = "ollama_error"
    NO_MODELS = "no_models"
    MODEL_NOT_INSTALLED = "model_not_installed"
    INVALID_EVIDENCE = "invalid_evidence"
    INVALID_MODEL_RESPONSE = "invalid_model_response"


@dataclass(frozen=True)
class AIServiceError:
    code: AIErrorCode
    message: str
    ollama_error: OllamaError | None = None


@dataclass(frozen=True)
class AIServiceResult:
    response: "GroundedAIResponse | None" = None
    error: AIServiceError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class GroundedAIResponse:
    workflow: str
    requested_model: str
    returned_model: str
    answer: ValidatedGroundedAnswer
    context: GroundedContext
    duration_ms: float
    prompt_eval_count: int | None
    eval_count: int | None

    @staticmethod
    def _evidence_metadata(item: EvidenceItem) -> dict[str, Any]:
        return {
            "evidence_id": item.evidence_id,
            "category": item.category,
            "kind": item.kind,
            "file_path": item.file_path,
            "line_start": item.line_start,
            "line_end": item.line_end,
            "location": item.location,
            "symbol_id": item.symbol_id,
        }

    def to_dict(self) -> dict[str, Any]:
        observed = [
            self._evidence_metadata(item)
            for item in self.context.evidence_items
            if item.category == "observed_fact"
        ]
        inferred = [
            self._evidence_metadata(item)
            for item in self.context.evidence_items
            if item.category == "project_mentor_inference"
        ]
        return {
            "workflow": self.workflow,
            "model": {
                "requested": self.requested_model,
                "returned": self.returned_model,
            },
            "deterministic_evidence": {
                "observed_facts": observed,
                "project_mentor_inferences": inferred,
            },
            "local_model_interpretation": {
                "answer": self.answer.answer,
                "citations": [
                    self._evidence_metadata(item) for item in self.answer.citations
                ],
                "rejected_citation_ids": list(self.answer.rejected_citation_ids),
                "evidence_insufficient": self.answer.evidence_insufficient,
                "grounding_warning": self.answer.grounding_warning,
            },
            "context": {
                "approximate_chars": self.context.approximate_chars,
                "evidence_chars": len(self.context.evidence_text),
                "candidate_evidence_count": self.context.candidate_count,
                "included_evidence_count": len(self.context.evidence_items),
                "omitted_evidence_count": self.context.omitted_count,
                "truncated": self.context.truncated,
                "truncation_notice": self.context.truncation_notice,
            },
            "request": {
                "duration_ms": round(self.duration_ms, 1),
                "prompt_eval_count": self.prompt_eval_count,
                "eval_count": self.eval_count,
            },
        }


def select_default_model(models: list[OllamaModel], configured: str) -> str | None:
    names = [item.name for item in models]
    if configured and configured in names:
        return configured
    if "gpt-oss:20b" in names:
        return "gpt-oss:20b"
    return names[0] if names else None


class GroundedAIService:
    def __init__(
        self,
        settings: Settings,
        client: OllamaClient,
        context_builder: EvidenceContextBuilder,
    ) -> None:
        self.settings = settings
        self.client = client
        self.context_builder = context_builder

    async def explain(
        self,
        analysis: ProjectAnalysis,
        *,
        model: str,
        question: str,
        selected_symbol_id: str | None,
        workflow: str = "map",
        evidence_items: tuple[EvidenceItem, ...] | None = None,
    ) -> AIServiceResult:
        started = perf_counter()
        models_result = await self.client.list_models()
        if not models_result.ok:
            return AIServiceResult(
                error=AIServiceError(
                    AIErrorCode.OLLAMA,
                    models_result.error.message,
                    models_result.error,
                )
            )
        installed = models_result.value or []
        if not installed:
            return AIServiceResult(
                error=AIServiceError(
                    AIErrorCode.NO_MODELS,
                    "Ollama is connected, but no local model is installed.",
                )
            )
        installed_names = {item.name for item in installed}
        if model not in installed_names:
            return AIServiceResult(
                error=AIServiceError(
                    AIErrorCode.MODEL_NOT_INSTALLED,
                    "The selected model is not in Ollama's installed-model list.",
                )
            )
        try:
            if evidence_items is None:
                context = self.context_builder.build(
                    analysis,
                    question=question,
                    selected_symbol_id=selected_symbol_id,
                    workflow=workflow,
                )
            else:
                context = self.context_builder.build_from_evidence(
                    question=question,
                    workflow=workflow,
                    evidence_items=evidence_items,
                )
        except (ContextBuildError, OSError) as exc:
            return AIServiceResult(
                error=AIServiceError(AIErrorCode.INVALID_EVIDENCE, str(exc))
            )
        LOGGER.info(
            "Grounded context built: chars=%s evidence=%s truncated=%s omitted=%s",
            context.approximate_chars,
            len(context.evidence_items),
            context.truncated,
            context.omitted_count,
        )
        chat_messages = [
            {"role": "system", "content": context.system_message},
            {"role": "user", "content": context.user_message},
        ]
        chat_result = await self.client.chat(
            model=model,
            messages=chat_messages,
            response_format=GROUNDED_RESPONSE_SCHEMA,
        )
        if not chat_result.ok:
            return AIServiceResult(
                error=AIServiceError(
                    AIErrorCode.OLLAMA,
                    chat_result.error.message,
                    chat_result.error,
                )
            )
        chat = chat_result.value
        try:
            answer = validate_grounded_answer(
                chat.content, context.evidence_by_id
            )
        except GroundingValidationError as exc:
            LOGGER.warning(
                "Ollama generation failure: model=%s duration_ms=%.0f response_chars=%s completion_reason=%s failure_category=malformed_json retry=1",
                model, (perf_counter() - started) * 1000, len(chat.content), chat.done_reason,
            )
            retry_messages = [
                *chat_messages,
                {"role": "user", "content": "Your previous output was invalid. Return exactly one concise JSON object with only answer, citations, and evidence_insufficient. Do not add markdown or commentary."},
            ]
            retry_result = await self.client.chat(
                model=model,
                messages=retry_messages,
                response_format=GROUNDED_RESPONSE_SCHEMA,
            )
            if not retry_result.ok:
                return AIServiceResult(error=AIServiceError(AIErrorCode.OLLAMA, retry_result.error.message, retry_result.error))
            retry_chat = retry_result.value
            try:
                answer = validate_grounded_answer(retry_chat.content, context.evidence_by_id)
                chat = retry_chat
            except GroundingValidationError as retry_exc:
                LOGGER.warning(
                    "Ollama generation failure: model=%s duration_ms=%.0f response_chars=%s completion_reason=%s failure_category=malformed_json retry=exhausted",
                    model, (perf_counter() - started) * 1000, len(retry_chat.content), retry_chat.done_reason,
                )
                return AIServiceResult(error=AIServiceError(AIErrorCode.INVALID_MODEL_RESPONSE, str(retry_exc)))
        return AIServiceResult(
            response=GroundedAIResponse(
                workflow=workflow,
                requested_model=model,
                returned_model=chat.model,
                answer=answer,
                context=context,
                duration_ms=(perf_counter() - started) * 1000,
                prompt_eval_count=chat.prompt_eval_count,
                eval_count=chat.eval_count,
            )
        )

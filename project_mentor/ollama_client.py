"""Small async client for the local Ollama HTTP API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Any, Generic, TypeVar

import httpx

from project_mentor.config import Settings


LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


class OllamaErrorCode(str, Enum):
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    MODEL_NOT_FOUND = "model_not_found"
    MALFORMED_RESPONSE = "malformed_response"
    INVALID_REQUEST = "invalid_request"
    OUTPUT_LIMIT = "output_limit"


@dataclass(frozen=True)
class OllamaError:
    code: OllamaErrorCode
    message: str
    status_code: int | None = None


@dataclass(frozen=True)
class OllamaResult(Generic[T]):
    value: T | None = None
    error: OllamaError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class OllamaModel:
    name: str
    size: int | None = None
    parameter_size: str | None = None
    quantization_level: str | None = None


@dataclass(frozen=True)
class OllamaChatResponse:
    model: str
    content: str
    prompt_eval_count: int | None
    eval_count: int | None
    total_duration_ns: int | None
    done: bool | None = None
    done_reason: str | None = None


@dataclass(frozen=True)
class OllamaStatus:
    connected: bool
    models: tuple[OllamaModel, ...]


class OllamaClient:
    """Call only the fixed Ollama origin supplied by application settings."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._transport = transport

    def _timeout(self, read_seconds: float) -> httpx.Timeout:
        return httpx.Timeout(
            timeout=read_seconds,
            connect=self.settings.ollama_connect_timeout_seconds,
        )

    async def _request_json(
        self,
        method: str,
        api_path: str,
        *,
        payload: dict[str, Any] | None = None,
        read_timeout: float,
    ) -> OllamaResult[dict[str, Any]]:
        started = perf_counter()
        LOGGER.info("Ollama connection attempt: %s %s", method, api_path)
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.ollama_base_url,
                timeout=self._timeout(read_timeout),
                transport=self._transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = await client.request(method, api_path, json=payload)
        except httpx.TimeoutException:
            LOGGER.warning(
                "Ollama request timed out after %.0f ms", (perf_counter() - started) * 1000
            )
            return OllamaResult(
                error=OllamaError(
                    OllamaErrorCode.TIMEOUT,
                    "Ollama did not respond before the configured timeout.",
                )
            )
        except (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError):
            LOGGER.warning(
                "Ollama is unavailable after %.0f ms", (perf_counter() - started) * 1000
            )
            return OllamaResult(
                error=OllamaError(
                    OllamaErrorCode.UNAVAILABLE,
                    "Project Mentor could not connect to Ollama.",
                )
            )
        except httpx.RequestError:
            LOGGER.exception("Unexpected Ollama request failure")
            return OllamaResult(
                error=OllamaError(
                    OllamaErrorCode.UNAVAILABLE,
                    "The Ollama request could not be completed.",
                )
            )

        duration_ms = (perf_counter() - started) * 1000
        if not 200 <= response.status_code < 300:
            message = "Ollama returned an HTTP error."
            try:
                error_body = response.json()
                if isinstance(error_body, dict) and isinstance(
                    error_body.get("error"), str
                ):
                    message = error_body["error"]
            except ValueError:
                pass
            code = (
                OllamaErrorCode.MODEL_NOT_FOUND
                if response.status_code == 404
                else OllamaErrorCode.HTTP_ERROR
            )
            LOGGER.warning(
                "Ollama HTTP failure: status=%s duration_ms=%.0f",
                response.status_code,
                duration_ms,
            )
            return OllamaResult(
                error=OllamaError(code, message, status_code=response.status_code)
            )
        try:
            body = response.json()
        except ValueError:
            LOGGER.warning("Ollama returned malformed JSON in %.0f ms", duration_ms)
            return OllamaResult(
                error=OllamaError(
                    OllamaErrorCode.MALFORMED_RESPONSE,
                    "Ollama returned a response that was not valid JSON.",
                )
            )
        if not isinstance(body, dict):
            return OllamaResult(
                error=OllamaError(
                    OllamaErrorCode.MALFORMED_RESPONSE,
                    "Ollama returned an unexpected JSON response shape.",
                )
            )
        LOGGER.info("Ollama request completed in %.0f ms", duration_ms)
        return OllamaResult(value=body)

    async def list_models(self) -> OllamaResult[list[OllamaModel]]:
        response = await self._request_json(
            "GET",
            "/api/tags",
            read_timeout=max(5.0, self.settings.ollama_connect_timeout_seconds),
        )
        if not response.ok:
            return OllamaResult(error=response.error)
        raw_models = response.value.get("models") if response.value else None
        if not isinstance(raw_models, list):
            return OllamaResult(
                error=OllamaError(
                    OllamaErrorCode.MALFORMED_RESPONSE,
                    "Ollama's model list did not contain a models array.",
                )
            )
        models: list[OllamaModel] = []
        for raw in raw_models:
            if not isinstance(raw, dict):
                return OllamaResult(
                    error=OllamaError(
                        OllamaErrorCode.MALFORMED_RESPONSE,
                        "Ollama's model list contained an invalid entry.",
                    )
                )
            name = raw.get("name") or raw.get("model")
            if not isinstance(name, str) or not name.strip():
                return OllamaResult(
                    error=OllamaError(
                        OllamaErrorCode.MALFORMED_RESPONSE,
                        "Ollama's model list contained an entry without a name.",
                    )
                )
            details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
            models.append(
                OllamaModel(
                    name=name,
                    size=raw.get("size") if isinstance(raw.get("size"), int) else None,
                    parameter_size=(
                        details.get("parameter_size")
                        if isinstance(details.get("parameter_size"), str)
                        else None
                    ),
                    quantization_level=(
                        details.get("quantization_level")
                        if isinstance(details.get("quantization_level"), str)
                        else None
                    ),
                )
            )
        return OllamaResult(value=sorted(models, key=lambda item: item.name.casefold()))

    async def status(self) -> OllamaResult[OllamaStatus]:
        """Check reachability and return the installed models in one request."""

        models = await self.list_models()
        if not models.ok:
            return OllamaResult(error=models.error)
        return OllamaResult(
            value=OllamaStatus(connected=True, models=tuple(models.value or []))
        )

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | str | None = None,
    ) -> OllamaResult[OllamaChatResponse]:
        if not model.strip() or not messages:
            return OllamaResult(
                error=OllamaError(
                    OllamaErrorCode.INVALID_REQUEST,
                    "A model and at least one message are required.",
                )
            )
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0, "num_predict": self.settings.ollama_max_output_tokens},
        }
        if response_format is not None:
            payload["format"] = response_format
        LOGGER.info("Ollama generation requested with model=%s", model)
        response = await self._request_json(
            "POST",
            "/api/chat",
            payload=payload,
            read_timeout=self.settings.ollama_generation_timeout_seconds,
        )
        if not response.ok:
            return OllamaResult(error=response.error)
        body = response.value or {}
        done_reason = body.get("done_reason") if isinstance(body.get("done_reason"), str) else None
        if done_reason in {"length", "max_tokens", "limit"}:
            LOGGER.warning(
                "Ollama generation failure: model=%s completion_reason=%s failure_category=output_limit",
                model,
                done_reason,
            )
            return OllamaResult(
                error=OllamaError(
                    OllamaErrorCode.OUTPUT_LIMIT,
                    "Ollama stopped at the configured output limit before returning a complete answer.",
                )
            )
        message = body.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        returned_model = body.get("model")
        if not isinstance(content, str) or not isinstance(returned_model, str):
            return OllamaResult(
                error=OllamaError(
                    OllamaErrorCode.MALFORMED_RESPONSE,
                    "Ollama's chat response did not contain model message text.",
                )
            )
        return OllamaResult(
            value=OllamaChatResponse(
                model=returned_model,
                content=content,
                prompt_eval_count=(
                    body.get("prompt_eval_count")
                    if isinstance(body.get("prompt_eval_count"), int)
                    else None
                ),
                eval_count=(
                    body.get("eval_count")
                    if isinstance(body.get("eval_count"), int)
                    else None
                ),
                total_duration_ns=(
                    body.get("total_duration")
                    if isinstance(body.get("total_duration"), int)
                    else None
                ),
                done=body.get("done") if isinstance(body.get("done"), bool) else None,
                done_reason=done_reason,
            )
        )

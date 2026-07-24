import json
import unittest

import httpx

from project_mentor.config import Settings
from project_mentor.ollama_client import OllamaClient, OllamaErrorCode


def client_with(handler) -> OllamaClient:
    return OllamaClient(Settings.from_env({}), transport=httpx.MockTransport(handler))


class OllamaClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_listing_and_no_models(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/api/tags")
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "zeta:latest",
                            "size": 100,
                            "details": {
                                "parameter_size": "7B",
                                "quantization_level": "Q4_K_M",
                            },
                        },
                        {"model": "alpha:latest"},
                    ]
                },
            )

        result = await client_with(handler).list_models()
        self.assertTrue(result.ok)
        self.assertEqual([item.name for item in result.value], ["alpha:latest", "zeta:latest"])
        self.assertEqual(result.value[1].parameter_size, "7B")

        empty = await client_with(
            lambda request: httpx.Response(200, json={"models": []})
        ).list_models()
        self.assertTrue(empty.ok)
        self.assertEqual(empty.value, [])

    async def test_status_uses_the_testable_model_endpoint(self) -> None:
        status = await client_with(
            lambda request: httpx.Response(
                200, json={"models": [{"name": "alpha:latest"}]}
            )
        ).status()
        self.assertTrue(status.ok)
        self.assertTrue(status.value.connected)
        self.assertEqual(status.value.models[0].name, "alpha:latest")

    async def test_valid_non_streaming_chat_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertEqual(request.url.path, "/api/chat")
            self.assertFalse(payload["stream"])
            self.assertEqual(payload["model"], "alpha:latest")
            self.assertEqual(payload["options"]["temperature"], 0)
            self.assertEqual(payload["options"]["num_predict"], 2_048)
            self.assertEqual(payload["format"], "json")
            return httpx.Response(
                200,
                json={
                    "model": "alpha:latest",
                    "message": {"role": "assistant", "content": '{"answer":"ok"}'},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 12,
                    "eval_count": 5,
                },
            )

        result = await client_with(handler).chat(
            model="alpha:latest",
            messages=[{"role": "user", "content": "hello"}],
            response_format="json",
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.value.content, '{"answer":"ok"}')
        self.assertEqual(result.value.prompt_eval_count, 12)
        self.assertTrue(result.value.done)
        self.assertEqual(result.value.done_reason, "stop")

    async def test_output_limit_is_typed(self) -> None:
        result = await client_with(
            lambda request: httpx.Response(
                200,
                json={"model": "alpha", "message": {"content": "{"}, "done": True, "done_reason": "length"},
            )
        ).chat(model="alpha", messages=[{"role": "user", "content": "hello"}])
        self.assertEqual(result.error.code, OllamaErrorCode.OUTPUT_LIMIT)

    async def test_unavailable_and_timeout_are_typed(self) -> None:
        def unavailable(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("offline", request=request)

        def timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow", request=request)

        offline_result = await client_with(unavailable).list_models()
        timeout_result = await client_with(timeout).list_models()
        self.assertEqual(offline_result.error.code, OllamaErrorCode.UNAVAILABLE)
        self.assertEqual(timeout_result.error.code, OllamaErrorCode.TIMEOUT)

    async def test_malformed_json_and_shape_are_rejected(self) -> None:
        malformed = await client_with(
            lambda request: httpx.Response(
                200, content=b"not-json", headers={"content-type": "application/json"}
            )
        ).list_models()
        wrong_shape = await client_with(
            lambda request: httpx.Response(200, json={"models": "not-a-list"})
        ).list_models()
        self.assertEqual(malformed.error.code, OllamaErrorCode.MALFORMED_RESPONSE)
        self.assertEqual(wrong_shape.error.code, OllamaErrorCode.MALFORMED_RESPONSE)

    async def test_http_model_error_is_typed(self) -> None:
        result = await client_with(
            lambda request: httpx.Response(404, json={"error": "model not found"})
        ).chat(
            model="missing",
            messages=[{"role": "user", "content": "hello"}],
        )
        self.assertEqual(result.error.code, OllamaErrorCode.MODEL_NOT_FOUND)
        self.assertEqual(result.error.status_code, 404)

    async def test_malformed_chat_response_is_rejected(self) -> None:
        result = await client_with(
            lambda request: httpx.Response(200, json={"model": "alpha", "message": {}})
        ).chat(
            model="alpha",
            messages=[{"role": "user", "content": "hello"}],
        )
        self.assertEqual(result.error.code, OllamaErrorCode.MALFORMED_RESPONSE)


if __name__ == "__main__":
    unittest.main()

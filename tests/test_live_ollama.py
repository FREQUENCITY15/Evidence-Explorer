import asyncio
import json
import os
import unittest

from project_mentor.ai_service import select_default_model
from project_mentor.config import Settings
from project_mentor.ollama_client import OllamaClient


LIVE_ENABLED = os.environ.get("PROJECT_MENTOR_RUN_LIVE_OLLAMA_TEST") == "1"


@unittest.skipUnless(
    LIVE_ENABLED,
    "Set PROJECT_MENTOR_RUN_LIVE_OLLAMA_TEST=1 to use a real local Ollama server.",
)
class LiveOllamaSmokeTest(unittest.TestCase):
    def test_live_model_listing_and_generation(self) -> None:
        async def run() -> None:
            settings = Settings.from_env()
            client = OllamaClient(settings)
            listed = await client.list_models()
            self.assertTrue(listed.ok, listed.error)
            model = select_default_model(
                listed.value or [], settings.ollama_default_model
            )
            self.assertIsNotNone(model, "Ollama has no installed local model.")
            print(f"Live Ollama selected model: {model}", flush=True)
            response = await client.chat(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "Return a short JSON object and do not use tools.",
                    },
                    {"role": "user", "content": "Reply with {\"status\":\"ok\"}."},
                ],
                response_format={
                    "type": "object",
                    "properties": {"status": {"type": "string"}},
                    "required": ["status"],
                },
            )
            self.assertTrue(response.ok, response.error)
            decoded = json.loads(response.value.content)
            self.assertIsInstance(decoded, dict)
            self.assertEqual(decoded.get("status"), "ok")
            self.assertTrue(response.value.done is None or response.value.done)
            self.assertNotEqual(response.value.done_reason, "length")

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

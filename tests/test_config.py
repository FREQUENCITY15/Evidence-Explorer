import unittest

from project_mentor.config import ConfigurationError, Settings


class ConfigurationTests(unittest.TestCase):
    def test_defaults_are_loopback_and_bounded(self) -> None:
        settings = Settings.from_env({})

        self.assertEqual(settings.ollama_base_url, "http://127.0.0.1:11434")
        self.assertTrue(settings.ollama_is_loopback)
        self.assertEqual(settings.ollama_default_model, "")
        self.assertEqual(settings.max_evidence_chars, 6_000)
        self.assertEqual(settings.ollama_max_output_tokens, 2_048)

    def test_environment_overrides_are_parsed(self) -> None:
        settings = Settings.from_env(
            {
                "PROJECT_MENTOR_OLLAMA_BASE_URL": "http://localhost:11435/",
                "PROJECT_MENTOR_OLLAMA_DEFAULT_MODEL": "local-model:latest",
                "PROJECT_MENTOR_OLLAMA_CONNECT_TIMEOUT_SECONDS": "3.5",
                "PROJECT_MENTOR_OLLAMA_GENERATION_TIMEOUT_SECONDS": "90",
                "PROJECT_MENTOR_MAX_EVIDENCE_CHARS": "12000",
                "PROJECT_MENTOR_OLLAMA_MAX_OUTPUT_TOKENS": "700",
            }
        )

        self.assertEqual(settings.ollama_base_url, "http://localhost:11435")
        self.assertEqual(settings.ollama_default_model, "local-model:latest")
        self.assertEqual(settings.ollama_connect_timeout_seconds, 3.5)
        self.assertEqual(settings.ollama_generation_timeout_seconds, 90.0)
        self.assertEqual(settings.max_evidence_chars, 12_000)
        self.assertEqual(settings.ollama_max_output_tokens, 700)

    def test_bounded_settings_reject_values_outside_ranges(self) -> None:
        for name, value in (
            ("PROJECT_MENTOR_MAX_EVIDENCE_CHARS", "1999"),
            ("PROJECT_MENTOR_MAX_EVIDENCE_CHARS", "200001"),
            ("PROJECT_MENTOR_OLLAMA_MAX_OUTPUT_TOKENS", "63"),
            ("PROJECT_MENTOR_OLLAMA_MAX_OUTPUT_TOKENS", "4097"),
        ):
            with self.subTest(name=name, value=value):
                with self.assertRaises(ConfigurationError):
                    Settings.from_env({name: value})

    def test_remote_endpoint_is_allowed_but_identified(self) -> None:
        settings = Settings.from_env(
            {"PROJECT_MENTOR_OLLAMA_BASE_URL": "https://ollama.example.test:443"}
        )
        self.assertFalse(settings.ollama_is_loopback)

    def test_endpoint_cannot_include_credentials_or_api_path(self) -> None:
        unsafe = (
            "http://user:password@127.0.0.1:11434",
            "http://127.0.0.1:11434/api/tags",
            "file:///tmp/ollama",
        )
        for value in unsafe:
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError):
                    Settings.from_env({"PROJECT_MENTOR_OLLAMA_BASE_URL": value})

    def test_invalid_numeric_setting_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings.from_env(
                {"PROJECT_MENTOR_OLLAMA_CONNECT_TIMEOUT_SECONDS": "never"}
            )


if __name__ == "__main__":
    unittest.main()

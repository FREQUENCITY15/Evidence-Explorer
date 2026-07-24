"""Environment-based configuration for Project Mentor's optional local AI."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from os import environ
from typing import Mapping
from urllib.parse import urlsplit


ENV_PREFIX = "PROJECT_MENTOR_"


class ConfigurationError(ValueError):
    """Raised when a Project Mentor environment setting is unsafe or invalid."""


def _positive_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number.") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")
    return value


def _bounded_int(
    env: Mapping[str, str], name: str, default: int, minimum: int, maximum: int
) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a whole number.") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(
            f"{name} must be between {minimum:,} and {maximum:,}."
        )
    return value


def normalize_ollama_base_url(value: str) -> str:
    """Validate an Ollama origin and return it without a trailing slash.

    Only the configured server origin is accepted. API paths, credentials,
    queries, and fragments are rejected so routes cannot become an arbitrary
    HTTP proxy.
    """

    candidate = value.strip().rstrip("/")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ConfigurationError(
            "PROJECT_MENTOR_OLLAMA_BASE_URL must start with http:// or https://."
        )
    if not parsed.hostname or parsed.username or parsed.password:
        raise ConfigurationError(
            "PROJECT_MENTOR_OLLAMA_BASE_URL must be a server origin without credentials."
        )
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ConfigurationError(
            "PROJECT_MENTOR_OLLAMA_BASE_URL must not contain a path, query, or fragment."
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise ConfigurationError(
            "PROJECT_MENTOR_OLLAMA_BASE_URL contains an invalid port."
        ) from exc
    if port is not None and not 1 <= port <= 65_535:
        raise ConfigurationError(
            "PROJECT_MENTOR_OLLAMA_BASE_URL contains an invalid port."
        )
    return candidate


def is_loopback_url(value: str) -> bool:
    hostname = (urlsplit(value).hostname or "").lower()
    if hostname == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_default_model: str = ""
    ollama_connect_timeout_seconds: float = 2.0
    ollama_generation_timeout_seconds: float = 300.0
    max_evidence_chars: int = 6_000
    ollama_max_output_tokens: int = 2_048

    @property
    def ollama_is_loopback(self) -> bool:
        return is_loopback_url(self.ollama_base_url)

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> "Settings":
        source = environ if values is None else values
        base_url = normalize_ollama_base_url(
            source.get(
                f"{ENV_PREFIX}OLLAMA_BASE_URL", "http://127.0.0.1:11434"
            )
        )
        default_model = source.get(f"{ENV_PREFIX}OLLAMA_DEFAULT_MODEL", "").strip()
        if len(default_model) > 300 or any(ord(char) < 32 for char in default_model):
            raise ConfigurationError(
                "PROJECT_MENTOR_OLLAMA_DEFAULT_MODEL is not a valid model name."
            )
        return cls(
            ollama_base_url=base_url,
            ollama_default_model=default_model,
            ollama_connect_timeout_seconds=_positive_float(
                source,
                f"{ENV_PREFIX}OLLAMA_CONNECT_TIMEOUT_SECONDS",
                2.0,
            ),
            ollama_generation_timeout_seconds=_positive_float(
                source,
                f"{ENV_PREFIX}OLLAMA_GENERATION_TIMEOUT_SECONDS",
                300.0,
            ),
            max_evidence_chars=_bounded_int(
                source,
                f"{ENV_PREFIX}MAX_EVIDENCE_CHARS",
                6_000,
                2_000,
                200_000,
            ),
            ollama_max_output_tokens=_bounded_int(
                source,
                f"{ENV_PREFIX}OLLAMA_MAX_OUTPUT_TOKENS",
                2_048,
                64,
                4_096,
            ),
        )

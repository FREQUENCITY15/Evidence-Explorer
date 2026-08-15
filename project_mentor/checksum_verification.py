"""Bounded, ephemeral checksum verification for supplied raw artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from typing import Any, Mapping


MAX_RAW_ARTIFACT_BYTES = 10_000_000


class ArtifactTooLarge(ValueError):
    """Raised when a supplied raw artifact exceeds the verification limit."""


@dataclass(frozen=True)
class ChecksumVerificationResult:
    status: str
    algorithm: str
    expected: str
    actual: str
    byte_count: int

    @property
    def verified(self) -> bool:
        return self.status == "verified"


def declared_main_jsonl_checksum(record: Mapping[str, Any]) -> str:
    """Return the structurally validated declared SHA-256 checksum."""
    checksums = record.get("checksums")
    expected = checksums.get("main_jsonl") if isinstance(checksums, Mapping) else None
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("Record does not declare a checksums.main_jsonl SHA-256 value")
    return expected.casefold()


class ChecksumVerifier:
    """Incrementally hash artifact bytes without retaining their content."""

    def __init__(
        self,
        expected: str,
        *,
        max_bytes: int = MAX_RAW_ARTIFACT_BYTES,
    ) -> None:
        self._expected = expected.casefold()
        self._max_bytes = max_bytes
        self._byte_count = 0
        self._digest = hashlib.sha256()

    def update(self, chunk: bytes) -> None:
        if not isinstance(chunk, bytes):
            raise TypeError("Checksum chunks must be bytes")
        next_count = self._byte_count + len(chunk)
        if next_count > self._max_bytes:
            raise ArtifactTooLarge(
                f"Raw artifact exceeds the {self._max_bytes}-byte verification limit"
            )
        self._digest.update(chunk)
        self._byte_count = next_count

    def finish(self) -> ChecksumVerificationResult:
        actual = self._digest.hexdigest()
        status = (
            "verified"
            if hmac.compare_digest(actual, self._expected)
            else "mismatch"
        )
        return ChecksumVerificationResult(
            status=status,
            algorithm="sha256",
            expected=self._expected,
            actual=actual,
            byte_count=self._byte_count,
        )

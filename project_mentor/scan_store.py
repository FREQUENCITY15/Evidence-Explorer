"""Small bounded in-memory store for trusted scan results used by AI requests."""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from project_mentor.models import ProjectAnalysis


@dataclass(frozen=True)
class _StoredScan:
    analysis: ProjectAnalysis
    created_at: float


class ScanStore:
    def __init__(self, max_entries: int = 8, ttl_seconds: float = 3_600.0) -> None:
        if max_entries < 1 or ttl_seconds <= 0:
            raise ValueError("Scan store limits must be positive.")
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, _StoredScan] = OrderedDict()
        self._lock = threading.Lock()

    def _remove_expired(self, now: float) -> None:
        expired = [
            key
            for key, stored in self._items.items()
            if now - stored.created_at > self.ttl_seconds
        ]
        for key in expired:
            self._items.pop(key, None)

    def put(self, analysis: ProjectAnalysis) -> str:
        scan_id = secrets.token_urlsafe(24)
        with self._lock:
            self._remove_expired(time.monotonic())
            self._items[scan_id] = _StoredScan(analysis, time.monotonic())
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)
        return scan_id

    def get(self, scan_id: str) -> ProjectAnalysis | None:
        with self._lock:
            self._remove_expired(time.monotonic())
            stored = self._items.get(scan_id)
            if stored is None:
                return None
            self._items.move_to_end(scan_id)
            return stored.analysis

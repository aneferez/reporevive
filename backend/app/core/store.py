"""In-memory analysis store with a pluggable interface.

The MVP keeps analyses in process memory. The ``AnalysisStore`` interface is
intentionally small so a Supabase/Postgres-backed implementation can be added
later without touching the API layer (PRD section 10).
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from .records import AnalysisRecord


class AnalysisStore:
    """Thread-safe, size-bounded registry of analyses."""

    def __init__(self, max_items: int = 100) -> None:
        self._items: "OrderedDict[str, AnalysisRecord]" = OrderedDict()
        self._lock = threading.Lock()
        self._max_items = max_items

    def create(self, record: AnalysisRecord) -> AnalysisRecord:
        with self._lock:
            self._items[record.analysis_id] = record
            self._items.move_to_end(record.analysis_id)
            self._evict_if_needed()
        return record

    def get(self, analysis_id: str) -> AnalysisRecord | None:
        with self._lock:
            return self._items.get(analysis_id)

    def delete(self, analysis_id: str) -> bool:
        with self._lock:
            return self._items.pop(analysis_id, None) is not None

    def exists(self, analysis_id: str) -> bool:
        with self._lock:
            return analysis_id in self._items

    def count(self) -> int:
        with self._lock:
            return len(self._items)

    def _evict_if_needed(self) -> None:
        # Caller holds the lock. Drop oldest records beyond the cap.
        while len(self._items) > self._max_items:
            self._items.popitem(last=False)


# Process-wide singleton, wired through FastAPI dependencies.
_store: AnalysisStore | None = None


def get_store() -> AnalysisStore:
    global _store
    if _store is None:
        from ..config import get_settings

        _store = AnalysisStore(max_items=get_settings().max_stored_analyses)
    return _store


def reset_store() -> None:
    """Drop the process-wide store. Used by tests for isolation."""

    global _store
    _store = None

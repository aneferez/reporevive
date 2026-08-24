"""In-memory analysis store with a pluggable interface.

The MVP keeps analyses in process memory. The ``AnalysisStore`` interface is
intentionally small so a Supabase/Postgres-backed implementation can be added
later without touching the API layer (PRD section 10).

Retention: a count cap (LRU eviction) and an optional time-based TTL. When a
record leaves the store for any reason, an ``on_remove`` callback fires so
external resources (e.g. pgvector rows) can be cleaned up. Callbacks run outside
the lock so a slow cleanup never blocks the store.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Callable
from datetime import timedelta

from .records import AnalysisRecord, utcnow

logger = logging.getLogger("reporevive.store")


class AnalysisStore:
    def __init__(
        self,
        max_items: int = 100,
        ttl_seconds: int = 0,
        on_remove: Callable[[AnalysisRecord], None] | None = None,
    ) -> None:
        self._items: "OrderedDict[str, AnalysisRecord]" = OrderedDict()
        self._lock = threading.Lock()
        self._max_items = max_items
        self._ttl_seconds = ttl_seconds
        self.on_remove = on_remove

    def create(self, record: AnalysisRecord) -> AnalysisRecord:
        removed: list[AnalysisRecord] = []
        with self._lock:
            self._items[record.analysis_id] = record
            self._items.move_to_end(record.analysis_id)
            removed.extend(self._collect_expired_locked())
            removed.extend(self._collect_overflow_locked())
        for r in removed:
            self._fire_on_remove(r)
        return record

    def get(self, analysis_id: str) -> AnalysisRecord | None:
        with self._lock:
            return self._items.get(analysis_id)

    def delete(self, analysis_id: str) -> bool:
        with self._lock:
            record = self._items.pop(analysis_id, None)
        if record is not None:
            self._fire_on_remove(record)
        return record is not None

    def exists(self, analysis_id: str) -> bool:
        with self._lock:
            return analysis_id in self._items

    def count(self) -> int:
        with self._lock:
            return len(self._items)

    def purge_expired(self) -> int:
        """Remove records past the TTL. Returns the number removed."""

        with self._lock:
            removed = self._collect_expired_locked()
        for r in removed:
            self._fire_on_remove(r)
        return len(removed)

    # --- internals (callers hold the lock) --------------------------------
    def _collect_overflow_locked(self) -> list[AnalysisRecord]:
        removed: list[AnalysisRecord] = []
        while len(self._items) > self._max_items:
            _, record = self._items.popitem(last=False)
            removed.append(record)
        return removed

    def _collect_expired_locked(self) -> list[AnalysisRecord]:
        if self._ttl_seconds <= 0:
            return []
        cutoff = utcnow() - timedelta(seconds=self._ttl_seconds)
        removed: list[AnalysisRecord] = []
        for analysis_id, record in list(self._items.items()):
            if record.created_at < cutoff:
                del self._items[analysis_id]
                removed.append(record)
        return removed

    def _fire_on_remove(self, record: AnalysisRecord) -> None:
        if self.on_remove is None:
            return
        try:
            self.on_remove(record)
        except Exception as exc:  # noqa: BLE001 - cleanup must never raise to callers
            logger.warning("on_remove callback failed for %s: %s", record.analysis_id, exc)


def _default_on_remove(record: AnalysisRecord) -> None:
    """Clean up a departing record's external resources (best-effort).

    Duck-typed so the store stays decoupled from the retrieval layer: if the
    record's retriever exposes ``cleanup()`` (e.g. pgvector), call it.
    """

    index = getattr(record, "retrieval_index", None)
    cleanup = getattr(index, "cleanup", None)
    if callable(cleanup):
        cleanup()


# Process-wide singleton, wired through FastAPI dependencies.
_store: AnalysisStore | None = None


def get_store() -> AnalysisStore:
    global _store
    if _store is None:
        from ..config import get_settings

        settings = get_settings()
        _store = AnalysisStore(
            max_items=settings.max_stored_analyses,
            ttl_seconds=settings.analysis_ttl_seconds,
            on_remove=_default_on_remove,
        )
    return _store


def reset_store() -> None:
    """Drop the process-wide store. Used by tests for isolation."""

    global _store
    _store = None

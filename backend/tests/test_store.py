from __future__ import annotations

from datetime import timedelta

from app.core.records import AnalysisRecord, utcnow
from app.core.store import AnalysisStore, _default_on_remove
from app.models.enums import SourceType
from app.models.schemas import RepositoryInfo


def _rec(aid: str, index=None) -> AnalysisRecord:
    r = AnalysisRecord(
        analysis_id=aid,
        repository=RepositoryInfo(name=aid, source_type=SourceType.zip),
        source_type=SourceType.zip,
    )
    if index is not None:
        r.retrieval_index = index
    return r


class _CleanupIndex:
    def __init__(self) -> None:
        self.cleaned = 0

    def cleanup(self) -> None:
        self.cleaned += 1


def test_on_remove_fires_on_delete():
    removed: list[str] = []
    store = AnalysisStore(on_remove=lambda r: removed.append(r.analysis_id))
    store.create(_rec("a"))
    assert store.delete("a") is True
    assert removed == ["a"]


def test_on_remove_fires_on_overflow_eviction():
    removed: list[str] = []
    store = AnalysisStore(max_items=2, on_remove=lambda r: removed.append(r.analysis_id))
    store.create(_rec("a"))
    store.create(_rec("b"))
    store.create(_rec("c"))
    assert removed == ["a"]  # oldest evicted
    assert store.exists("a") is False


def test_ttl_purge_removes_expired_and_cleans():
    removed: list[str] = []
    store = AnalysisStore(ttl_seconds=60, on_remove=lambda r: removed.append(r.analysis_id))
    rec = _rec("fresh")
    store.create(rec)
    # Age it past the TTL, then sweep.
    rec.created_at = utcnow() - timedelta(seconds=120)
    assert store.purge_expired() == 1
    assert removed == ["fresh"]
    assert store.exists("fresh") is False


def test_default_on_remove_calls_retriever_cleanup():
    idx = _CleanupIndex()
    store = AnalysisStore(on_remove=_default_on_remove)
    store.create(_rec("a", index=idx))
    store.delete("a")
    assert idx.cleaned == 1


def test_cleanup_failure_does_not_propagate():
    class _Boom:
        def cleanup(self):
            raise RuntimeError("db down")

    store = AnalysisStore(on_remove=_default_on_remove)
    store.create(_rec("a", index=_Boom()))
    # Must not raise even though cleanup blows up.
    assert store.delete("a") is True

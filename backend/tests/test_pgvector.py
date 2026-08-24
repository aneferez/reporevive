"""Unit tests for the pgvector retriever using a faked psycopg connection.

These verify the SQL flow, task types, and factory routing without a live
database. Running against a real Postgres+pgvector is a separate integration
step (requires DATABASE_URL).
"""

from __future__ import annotations

import pytest

# Skip cleanly if the optional pgvector extras aren't installed (base test env).
psycopg = pytest.importorskip("psycopg")
_pgvector_psycopg = pytest.importorskip("pgvector.psycopg")

from app.config import Settings
from app.retrieval.embeddings import DOCUMENT_TASK, QUERY_TASK
from app.retrieval.factory import build_retriever
from app.retrieval.pgvector import PgVectorRetriever

from .helpers import make_files


class RecordingEmbedder:
    def __init__(self) -> None:
        self.task_types: list[str | None] = []

    def available(self) -> bool:
        return True

    def embed(self, texts, *, task_type=None):
        self.task_types.append(task_type)
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeCursor:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._conn.executed.append(("cursor", sql, params))


class _FakeConn:
    def __init__(self, select_rows):
        self.executed: list = []
        self.committed = False
        self._select_rows = select_rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.executed.append(("conn", sql, params))
        rows = self._select_rows if sql.strip().upper().startswith("SELECT") else []
        return _FakeResult(rows)

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed = True


@pytest.fixture()
def fake_db(monkeypatch):
    rows = [("backend/main.py", 1, 5, "from fastapi import FastAPI", 0.91)]
    conns: list[_FakeConn] = []

    def fake_connect(dsn):
        conn = _FakeConn(rows)
        conns.append(conn)
        return conn

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    monkeypatch.setattr(_pgvector_psycopg, "register_vector", lambda conn: None)
    return conns


def _settings(**over):
    return Settings(retrieval_mode="pgvector", **over)


def test_build_requires_database_url():
    with pytest.raises(RuntimeError):
        PgVectorRetriever.build(make_files({"a.py": "x = 1\n"}), RecordingEmbedder(), _settings())


def test_empty_repo_skips_the_database(monkeypatch):
    called = []
    monkeypatch.setattr(psycopg, "connect", lambda dsn: called.append(dsn))
    retr = PgVectorRetriever.build([], RecordingEmbedder(), _settings(database_url="postgresql://x/db"))
    assert retr.size == 0
    assert retr.search("anything") == []
    assert called == []  # DB never touched


def test_build_and_search_flow(fake_db):
    emb = RecordingEmbedder()
    files = make_files({"backend/main.py": "from fastapi import FastAPI\napp = FastAPI()\n"})
    retr = PgVectorRetriever.build(files, emb, _settings(database_url="postgresql://x/db"))

    assert retr.size == 1
    build_conn = fake_db[0]
    assert any("CREATE TABLE" in sql for _, sql, _ in build_conn.executed)
    assert any(kind == "cursor" and "INSERT" in sql for kind, sql, _ in build_conn.executed)
    assert build_conn.committed is True
    assert DOCUMENT_TASK in emb.task_types  # documents embedded as documents

    hits = retr.search("what backend framework is used")
    assert len(hits) == 1
    assert hits[0].file == "backend/main.py"
    assert hits[0].score == 0.91
    assert QUERY_TASK in emb.task_types  # query embedded as a query
    search_conn = fake_db[1]
    assert any("SELECT" in sql and "<=>" in sql for _, sql, _ in search_conn.executed)


def test_factory_routes_to_pgvector(fake_db):
    retr = build_retriever(
        make_files({"a.py": "x = 1\n"}),
        _settings(database_url="postgresql://x/db"),
        embedder=RecordingEmbedder(),
    )
    assert isinstance(retr, PgVectorRetriever)


def test_factory_falls_back_to_lexical_when_db_missing():
    # pgvector requested but no DATABASE_URL -> build raises -> lexical fallback.
    from app.retrieval.lexical import LexicalIndex

    retr = build_retriever(
        make_files({"a.py": "x = 1\n"}),
        _settings(),  # no database_url
        embedder=RecordingEmbedder(),
    )
    assert isinstance(retr, LexicalIndex)

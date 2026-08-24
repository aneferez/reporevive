"""Postgres + pgvector retriever (experimental).

Persists chunk embeddings in a pgvector table and queries by cosine distance,
behind the same ``search`` interface as the other retrievers.

Status: this path is implemented but NOT exercised by the MVP test suite, which
runs without a database. It requires ``DATABASE_URL`` pointing at a Postgres with
the ``vector`` extension, plus the optional dependencies::

    pip install "psycopg[binary]" pgvector

Enable via ``RETRIEVAL_MODE=pgvector``. If any dependency or the database is
unavailable, the factory falls back to lexical retrieval.
"""

from __future__ import annotations

import logging
import uuid

from ..config import Settings
from ..core.records import RepoFile
from .base import SearchHit
from .embeddings import Embedder, _chunk_files
from .lexical import _tokenize

logger = logging.getLogger("reporevive.retrieval")


class PgVectorRetriever:
    def __init__(self, dsn: str, namespace: str, embedder: Embedder, dim: int) -> None:
        self._dsn = dsn
        self._namespace = namespace
        self._embedder = embedder
        self._dim = dim
        self._count = 0

    @classmethod
    def build(
        cls,
        files: list[RepoFile],
        embedder: Embedder,
        settings: Settings,
        *,
        chunk_lines: int = 40,
        overlap: int = 10,
    ) -> "PgVectorRetriever":
        if not settings.database_url:
            raise RuntimeError("RETRIEVAL_MODE=pgvector requires DATABASE_URL")

        import psycopg
        from pgvector.psycopg import register_vector

        chunks = list(_chunk_files(files, chunk_lines, overlap))
        namespace = uuid.uuid4().hex
        vectors = embedder.embed([c[3] for c in chunks]) if chunks else []
        dim = len(vectors[0]) if vectors else 0

        with psycopg.connect(settings.database_url) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            register_vector(conn)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reporevive_chunks ("
                "  id bigserial PRIMARY KEY,"
                "  namespace text NOT NULL,"
                "  file text NOT NULL,"
                "  start_line int NOT NULL,"
                "  end_line int NOT NULL,"
                "  content text NOT NULL,"
                f"  embedding vector({dim or 768})"
                ")"
            )
            with conn.cursor() as cur:
                for (path, start, end, text), vec in zip(chunks, vectors):
                    cur.execute(
                        "INSERT INTO reporevive_chunks "
                        "(namespace, file, start_line, end_line, content, embedding) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (namespace, path, start, end, text, vec),
                    )
            conn.commit()

        retriever = cls(settings.database_url, namespace, embedder, dim)
        retriever._count = len(chunks)
        return retriever

    @property
    def size(self) -> int:
        return self._count

    def search(self, query: str, *, k: int = 5) -> list[SearchHit]:
        if self._count == 0 or not _tokenize(query):
            return []
        import psycopg
        from pgvector.psycopg import register_vector

        q_vec = self._embedder.embed([query])[0]
        with psycopg.connect(self._dsn) as conn:
            register_vector(conn)
            rows = conn.execute(
                "SELECT file, start_line, end_line, content, "
                "1 - (embedding <=> %s) AS score "
                "FROM reporevive_chunks WHERE namespace = %s "
                "ORDER BY embedding <=> %s LIMIT %s",
                (q_vec, self._namespace, q_vec, k),
            ).fetchall()

        return [
            SearchHit(file=r[0], start_line=r[1], end_line=r[2], text=r[3], score=float(r[4]))
            for r in rows
        ]

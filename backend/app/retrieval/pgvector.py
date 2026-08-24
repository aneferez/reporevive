"""Postgres + pgvector retriever (opt-in via RETRIEVAL_MODE=pgvector).

Persists chunk embeddings in a pgvector table and queries by cosine distance,
behind the same ``search`` interface as the other retrievers.

Requires ``DATABASE_URL`` pointing at a Postgres with the ``vector`` extension,
plus the optional dependencies::

    pip install "psycopg[binary]" pgvector

If any dependency or the database is unavailable, ``build_retriever`` catches the
error and falls back to lexical retrieval, so this path never breaks analysis.

Production notes (single-instance MVP scope):
- Rows are namespaced per analysis; deleting an analysis does not currently purge
  its rows. For a long-running deployment, add a cleanup on deletion and an
  approximate vector index (HNSW/IVFFlat) on ``embedding`` for large corpora.
- The table's vector dimension is fixed on first creation from the configured
  embedding model; changing ``EMBEDDING_MODEL`` to one with a different dimension
  requires a fresh table.
"""

from __future__ import annotations

import logging
import uuid

from ..config import Settings
from ..core.records import RepoFile
from .base import SearchHit
from .embeddings import DOCUMENT_TASK, QUERY_TASK, Embedder, _chunk_files
from .lexical import _tokenize

logger = logging.getLogger("reporevive.retrieval")

_TABLE = "reporevive_chunks"


class PgVectorRetriever:
    def __init__(self, dsn: str, namespace: str, embedder: Embedder, count: int) -> None:
        self._dsn = dsn
        self._namespace = namespace
        self._embedder = embedder
        self._count = count

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

        namespace = uuid.uuid4().hex
        chunks = list(_chunk_files(files, chunk_lines, overlap))
        if not chunks:
            # Nothing to index; don't touch the database.
            return cls(settings.database_url, namespace, embedder, 0)

        import psycopg
        from pgvector.psycopg import register_vector

        vectors = embedder.embed([c[3] for c in chunks], task_type=DOCUMENT_TASK)
        dim = len(vectors[0])

        with psycopg.connect(settings.database_url) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            register_vector(conn)
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {_TABLE} ("
                "  id bigserial PRIMARY KEY,"
                "  namespace text NOT NULL,"
                "  file text NOT NULL,"
                "  start_line int NOT NULL,"
                "  end_line int NOT NULL,"
                "  content text NOT NULL,"
                f"  embedding vector({dim})"
                ")"
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {_TABLE}_namespace_idx ON {_TABLE} (namespace)"
            )
            with conn.cursor() as cur:
                for (path, start, end, text), vec in zip(chunks, vectors):
                    cur.execute(
                        f"INSERT INTO {_TABLE} "
                        "(namespace, file, start_line, end_line, content, embedding) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (namespace, path, start, end, text, vec),
                    )
            conn.commit()

        return cls(settings.database_url, namespace, embedder, len(chunks))

    @property
    def size(self) -> int:
        return self._count

    def search(self, query: str, *, k: int = 5) -> list[SearchHit]:
        if self._count == 0 or not _tokenize(query):
            return []
        import psycopg
        from pgvector.psycopg import register_vector

        q_vec = self._embedder.embed([query], task_type=QUERY_TASK)[0]
        with psycopg.connect(self._dsn) as conn:
            register_vector(conn)
            rows = conn.execute(
                f"SELECT file, start_line, end_line, content, "
                "1 - (embedding <=> %s) AS score "
                f"FROM {_TABLE} WHERE namespace = %s "
                "ORDER BY embedding <=> %s LIMIT %s",
                (q_vec, self._namespace, q_vec, k),
            ).fetchall()

        return [
            SearchHit(file=r[0], start_line=r[1], end_line=r[2], text=r[3], score=float(r[4]))
            for r in rows
        ]

    def cleanup(self) -> None:
        """Delete this analysis's rows from the shared table (retention)."""

        if self._count == 0:
            return
        import psycopg

        with psycopg.connect(self._dsn) as conn:
            conn.execute(f"DELETE FROM {_TABLE} WHERE namespace = %s", (self._namespace,))
            conn.commit()

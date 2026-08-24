"""Embeddings-based retrieval (optional).

An in-memory cosine-similarity index over the same line-window chunks used by the
lexical index, behind the shared ``search`` interface. It accepts any embedder
callable, so it is fully testable with a deterministic fake and uses Gemini
embeddings in production when a key is configured.

Persisting vectors to Postgres/pgvector is provided separately in
``retrieval.pgvector`` and selected via ``RETRIEVAL_MODE``.
"""

from __future__ import annotations

import logging
import math
from typing import Protocol

from ..config import Settings
from ..core.records import RepoFile
from .base import SearchHit
from .lexical import _tokenize  # reuse chunking-independent helper

logger = logging.getLogger("reporevive.retrieval")


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _chunk_files(files: list[RepoFile], chunk_lines: int, overlap: int):
    step = max(1, chunk_lines - overlap)
    for f in files:
        lines = f.content.splitlines()
        if not lines:
            continue
        start = 0
        while start < len(lines):
            window = lines[start : start + chunk_lines]
            text = "\n".join(window)
            if text.strip():
                yield f.path, start + 1, start + len(window), text
            if start + chunk_lines >= len(lines):
                break
            start += step


class EmbeddingIndex:
    def __init__(self) -> None:
        self._meta: list[tuple[str, int, int, str]] = []  # (file, start, end, text)
        self._vectors: list[list[float]] = []
        self._norms: list[float] = []
        self._embedder: Embedder | None = None

    @classmethod
    def build(
        cls,
        files: list[RepoFile],
        embedder: Embedder,
        *,
        chunk_lines: int = 40,
        overlap: int = 10,
    ) -> "EmbeddingIndex":
        index = cls()
        index._embedder = embedder
        chunks = list(_chunk_files(files, chunk_lines, overlap))
        if not chunks:
            return index
        texts = [c[3] for c in chunks]
        vectors = embedder.embed(texts)
        for (path, start, end, text), vec in zip(chunks, vectors):
            index._meta.append((path, start, end, text))
            index._vectors.append(vec)
            index._norms.append(_norm(vec))
        return index

    @property
    def size(self) -> int:
        return len(self._vectors)

    def search(self, query: str, *, k: int = 5) -> list[SearchHit]:
        if not self._vectors or self._embedder is None:
            return []
        if not _tokenize(query):
            return []
        q_vec = self._embedder.embed([query])[0]
        q_norm = _norm(q_vec)
        if q_norm == 0:
            return []

        scored: list[SearchHit] = []
        for (path, start, end, text), vec, norm in zip(self._meta, self._vectors, self._norms):
            if norm == 0:
                continue
            sim = _dot(q_vec, vec) / (q_norm * norm)
            if sim > 0:
                scored.append(SearchHit(file=path, start_line=start, end_line=end, text=text, score=sim))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]


class GeminiEmbedder:
    """Embedder backed by the Gemini embeddings API. Optional and lazy."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def available(self) -> bool:
        if not self.settings.ai_enabled:
            return False
        try:
            import google.genai  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        from google import genai

        client = genai.Client(api_key=self.settings.gemini_api_key)
        result = client.models.embed_content(
            model=self.settings.embedding_model,
            contents=texts,
        )
        # SDK returns an object with `.embeddings`, each having `.values`.
        return [list(e.values) for e in result.embeddings]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))

"""Retriever selection.

Chooses a retriever based on ``RETRIEVAL_MODE``, always degrading safely to the
lexical index when embeddings/pgvector are requested but unavailable. This keeps
the deterministic, offline path working with no configuration.
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..core.records import RepoFile
from .base import Retriever
from .embeddings import EmbeddingIndex, GeminiEmbedder
from .lexical import LexicalIndex

logger = logging.getLogger("reporevive.retrieval")


def build_retriever(
    files: list[RepoFile], settings: Settings, *, embedder=None
) -> Retriever:
    mode = (settings.retrieval_mode or "lexical").lower()

    if mode in ("embeddings", "pgvector", "auto"):
        emb = embedder or GeminiEmbedder(settings)
        available = getattr(emb, "available", lambda: True)()
        if available:
            try:
                if mode == "pgvector":
                    from .pgvector import PgVectorRetriever

                    return PgVectorRetriever.build(files, emb, settings)
                return EmbeddingIndex.build(files, emb)
            except Exception as exc:  # noqa: BLE001 - never fail analysis on retrieval
                logger.warning("Embeddings retrieval failed; using lexical. %s", exc)
        elif mode in ("embeddings", "pgvector"):
            logger.info("Embeddings requested but unavailable; using lexical retrieval.")

    return LexicalIndex.build(files)

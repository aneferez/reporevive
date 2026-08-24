"""Shared retrieval types and interface.

Both the lexical index and the embeddings index expose the same ``search``
method returning ``SearchHit`` objects, so chat and grounding are agnostic to
which retriever is in use (PRD section 10: lexical first, embeddings/pgvector
when available).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class SearchHit:
    file: str
    start_line: int
    end_line: int
    text: str
    score: float

    def excerpt(self, max_lines: int = 3, max_chars: int = 240) -> str:
        lines = [ln for ln in self.text.splitlines() if ln.strip()]
        snippet = "\n".join(lines[:max_lines])
        return snippet[:max_chars]


@runtime_checkable
class Retriever(Protocol):
    @property
    def size(self) -> int: ...

    def search(self, query: str, *, k: int = 5) -> list[SearchHit]: ...

"""Lexical retrieval over repository files (PRD section 10).

A small, dependency-free BM25 index over line-window chunks. Each chunk keeps
its file path and line range so chat answers can cite exact locations. Embeddings
/ pgvector can replace this later behind the same ``search`` interface.

All indexed text is already redacted by intake, so no secrets are stored here.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from ..core.records import RepoFile
from .base import SearchHit  # re-exported for backward compatibility

__all__ = ["LexicalIndex", "SearchHit", "Chunk"]

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        if len(raw) < 2:
            continue
        tokens.append(raw)
        # Split snake_case parts too, for better identifier matching.
        if "_" in raw:
            tokens.extend(p for p in raw.split("_") if len(p) >= 2)
    return tokens


@dataclass
class Chunk:
    file: str
    start_line: int
    end_line: int
    text: str
    tokens: list[str]
    length: int


class LexicalIndex:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks: list[Chunk] = []
        self.doc_freq: dict[str, int] = {}
        self.avg_len: float = 0.0

    @classmethod
    def build(
        cls, files: list[RepoFile], *, chunk_lines: int = 40, overlap: int = 10
    ) -> "LexicalIndex":
        index = cls()
        step = max(1, chunk_lines - overlap)
        for f in files:
            lines = f.content.splitlines()
            if not lines:
                continue
            start = 0
            while start < len(lines):
                window = lines[start : start + chunk_lines]
                text = "\n".join(window)
                tokens = _tokenize(text)
                if tokens:
                    index.chunks.append(
                        Chunk(
                            file=f.path,
                            start_line=start + 1,
                            end_line=start + len(window),
                            text=text,
                            tokens=tokens,
                            length=len(tokens),
                        )
                    )
                if start + chunk_lines >= len(lines):
                    break
                start += step
        index._finalize()
        return index

    def _finalize(self) -> None:
        df: dict[str, int] = {}
        total_len = 0
        for chunk in self.chunks:
            total_len += chunk.length
            for term in set(chunk.tokens):
                df[term] = df.get(term, 0) + 1
        self.doc_freq = df
        self.avg_len = (total_len / len(self.chunks)) if self.chunks else 0.0

    @property
    def size(self) -> int:
        return len(self.chunks)

    def search(self, query: str, *, k: int = 5) -> list[SearchHit]:
        if not self.chunks:
            return []
        q_terms = [t for t in set(_tokenize(query)) if t in self.doc_freq]
        if not q_terms:
            return []

        n = len(self.chunks)
        idf = {
            t: math.log(1 + (n - self.doc_freq[t] + 0.5) / (self.doc_freq[t] + 0.5))
            for t in q_terms
        }

        scored: list[SearchHit] = []
        for chunk in self.chunks:
            tf: dict[str, int] = {}
            for term in chunk.tokens:
                if term in idf:
                    tf[term] = tf.get(term, 0) + 1
            if not tf:
                continue
            score = 0.0
            denom_norm = self.k1 * (
                1 - self.b + self.b * (chunk.length / (self.avg_len or 1))
            )
            for term, freq in tf.items():
                score += idf[term] * (freq * (self.k1 + 1)) / (freq + denom_norm)
            if score > 0:
                scored.append(
                    SearchHit(
                        file=chunk.file,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        text=chunk.text,
                        score=score,
                    )
                )

        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]

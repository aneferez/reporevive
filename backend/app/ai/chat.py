"""Repository-grounded chat (FR-11).

Flow:
1. Retrieve relevant chunks via the lexical index.
2. If nothing relevant is found -> ``insufficient_evidence`` (never guess).
3. If a Gemini key is configured -> a grounded, cited answer (provider failures
   surface as structured errors).
4. Otherwise -> a deterministic extractive answer built from the retrieved
   snippets, still fully cited.
"""

from __future__ import annotations

from http import HTTPStatus

from ..api.errors import AppError
from ..config import get_settings
from ..core.records import AnalysisRecord
from ..models.schemas import ChatResponse, Citation
from ..retrieval.lexical import LexicalIndex, SearchHit
from .grounding import build_context_block
from .provider import AIProviderError, get_provider

_SYSTEM = (
    "You are a precise code-analysis assistant. Answer ONLY using the provided "
    "repository excerpts. Cite files inline like [path:line]. If the excerpts do "
    "not contain enough information, say so explicitly. Never invent files, "
    "functions, or behavior that is not in the excerpts."
)


def answer_question(record: AnalysisRecord, question: str) -> ChatResponse:
    index = _get_index(record)
    hits = index.search(question, k=5) if index else []
    hits = [h for h in hits if h.score > 0]

    if not hits:
        return ChatResponse(
            answer=(
                "There isn't enough evidence in the inspected repository to answer "
                "that. Try asking about files, configuration, or findings that were "
                "detected."
            ),
            citations=[],
            confidence=0.0,
            insufficient_evidence=True,
        )

    citations = _citations(hits)
    settings = get_settings()
    provider = get_provider(settings)

    if provider.available():
        context = build_context_block(hits)
        prompt = f"Repository excerpts:\n\n{context}\n\nQuestion: {question}\n\nAnswer:"
        try:
            answer = provider.generate(system=_SYSTEM, prompt=prompt)
        except AIProviderError as exc:
            raise AppError(exc.code, exc.message, status_code=exc.status_code) from exc
        insufficient = "not enough" in answer.lower() or "insufficient" in answer.lower()
        return ChatResponse(
            answer=answer,
            citations=citations,
            confidence=0.85 if not insufficient else 0.4,
            insufficient_evidence=insufficient,
        )

    # Deterministic extractive fallback (no AI key configured).
    return _extractive_answer(question, hits, citations)


def _extractive_answer(
    question: str, hits: list[SearchHit], citations: list[Citation]
) -> ChatResponse:
    files = ", ".join(dict.fromkeys(h.file for h in hits))
    answer = (
        "AI narration is not configured, so here are the most relevant repository "
        f"excerpts for your question. The strongest matches are in: {files}. "
        "See the citations for exact locations."
    )
    return ChatResponse(
        answer=answer,
        citations=citations,
        confidence=0.45,
        insufficient_evidence=False,
    )


def _citations(hits: list[SearchHit]) -> list[Citation]:
    return [
        Citation(file=h.file, line=h.start_line, excerpt=h.excerpt())
        for h in hits[:4]
    ]


def _get_index(record: AnalysisRecord) -> LexicalIndex | None:
    index = getattr(record, "retrieval_index", None)
    if index is not None:
        return index
    # Lazily build if the pipeline hasn't (defensive; normally built in phase 4).
    if record.files:
        index = LexicalIndex.build(record.files)
        record.retrieval_index = index
        return index
    return None

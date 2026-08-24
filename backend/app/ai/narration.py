"""Optional AI narration of the analysis overview.

Enriches the deterministic overview with a grounded natural-language summary when
a Gemini key is configured. Failures never break the analysis — the deterministic
overview remains the source of truth.
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..core.records import AnalysisRecord
from .grounding import build_repo_summary
from .provider import AIProviderError, get_provider

logger = logging.getLogger("reporevive.ai")

_SYSTEM = (
    "You are summarizing a static code analysis for a developer. Use ONLY the "
    "provided facts. Write 3-5 sentences of flowing prose. Do NOT use markdown, "
    "headings, bullet points, or sentence labels; do not number or annotate the "
    "sentences. Do not claim anything is confirmed unless the facts say so. "
    "Output only the summary text."
)


def generate_overview(record: AnalysisRecord, settings: Settings) -> str | None:
    provider = get_provider(settings)
    if not provider.available():
        return None

    summary = build_repo_summary(record)
    prompt = (
        "Analysis facts:\n"
        f"{summary}\n\n"
        f"Deterministic overview:\n{record.overview}\n\n"
        "Write a short, grounded overview for the developer."
    )
    try:
        # Reasoning models spend part of the budget on internal thinking, so give
        # enough room for the visible summary to complete.
        return provider.generate(system=_SYSTEM, prompt=prompt, max_output_tokens=1200)
    except AIProviderError as exc:
        # Non-fatal: keep the deterministic overview.
        logger.info("AI overview narration skipped: %s", exc.code)
        return None

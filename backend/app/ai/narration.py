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
    "provided facts. Be concise (3-5 sentences), specific, and do not claim "
    "anything is confirmed unless the facts say so. No markdown headings."
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
        return provider.generate(system=_SYSTEM, prompt=prompt, max_output_tokens=400)
    except AIProviderError as exc:
        # Non-fatal: keep the deterministic overview.
        logger.info("AI overview narration skipped: %s", exc.code)
        return None

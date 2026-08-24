"""Prompt-grounding helpers.

Builds context blocks from retrieved snippets and analysis results. Applies a
defensive second redaction pass before any text leaves for the AI provider, so
suspected secrets are never transmitted even if a new pattern slipped through.
"""

from __future__ import annotations

from ..core.records import AnalysisRecord
from ..retrieval.lexical import SearchHit
from ..security.redaction import redact_text


def build_context_block(
    hits: list[SearchHit], *, max_chars: int = 4000, max_files: int = 100
) -> str:
    """Assemble the retrieved context, enforcing hard caps on total characters
    and the number of distinct files that reach the AI provider.
    """

    parts: list[str] = []
    used = 0
    files_seen: set[str] = set()
    for hit in hits:
        # Enforce the distinct-file cap.
        if hit.file not in files_seen and len(files_seen) >= max_files:
            continue
        safe, _ = redact_text(hit.excerpt(max_lines=8, max_chars=600))
        block = f"[{hit.file}:{hit.start_line}]\n{safe}"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
        files_seen.add(hit.file)
    return "\n\n".join(parts)


def build_repo_summary(record: AnalysisRecord, *, max_findings: int = 8) -> str:
    stack = record.stack
    lines: list[str] = []
    if stack.frontend:
        lines.append(f"Frontend: {', '.join(stack.frontend)}")
    if stack.backend:
        lines.append(f"Backend: {', '.join(stack.backend)}")
    if stack.database:
        lines.append(f"Database: {', '.join(stack.database)}")
    if stack.testing:
        lines.append(f"Testing: {', '.join(stack.testing)}")
    lines.append(f"Files inspected: {record.files_analyzed}")

    if record.findings:
        lines.append("Top findings:")
        for f in record.findings[:max_findings]:
            loc = f" ({f.file})" if f.file else ""
            lines.append(f"- [{f.severity.value}] {f.title}{loc}")
    return "\n".join(lines)

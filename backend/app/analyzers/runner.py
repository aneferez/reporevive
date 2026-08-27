"""Finalization helpers shared by the pipeline: id assignment, ordering,
readiness, and a deterministic overview.
"""

from __future__ import annotations

from ..models.enums import ReadinessLabel, Severity
from ..models.schemas import Finding, StackInfo
from .base import SEVERITY_ORDER


def finalize_findings(findings: list[Finding]) -> list[Finding]:
    """Sort by severity (then confidence) and assign stable sequential ids."""

    ordered = sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER[f.severity], -f.confidence),
    )
    for index, finding in enumerate(ordered, start=1):
        finding.id = f"finding_{index:03d}"
    return ordered


def compute_readiness(findings: list[Finding]) -> str:
    severities = {f.severity for f in findings}
    if Severity.critical in severities:
        return ReadinessLabel.not_ready.value
    if Severity.high in severities or Severity.medium in severities:
        return ReadinessLabel.needs_attention.value
    return ReadinessLabel.ready.value


def build_overview(
    files_analyzed: int, stack: StackInfo, findings: list[Finding], truncated: bool
) -> str:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        if f.severity.value in counts:
            counts[f.severity.value] += 1

    parts: list[str] = [f"Inspected {files_analyzed} source file(s)."]

    stack_bits: list[str] = []
    if stack.frontend:
        stack_bits.append(f"{', '.join(stack.frontend[:3])} frontend")
    if stack.backend:
        stack_bits.append(f"{', '.join(stack.backend[:3])} backend")
    if stack.database:
        stack_bits.append(f"{', '.join(stack.database[:2])} storage")
    if stack_bits:
        parts.append("Detected " + "; ".join(stack_bits) + ".")
    else:
        parts.append("No supported frontend or backend framework was confidently detected.")

    total = len(findings)
    if total == 0:
        parts.append("No findings were raised by the deterministic analyzers.")
    else:
        parts.append(
            f"Found {total} finding(s): "
            f"{counts['critical']} critical, {counts['high']} high, "
            f"{counts['medium']} medium, {counts['low']} low."
        )
        top = findings[0]
        parts.append(f"Most severe: {top.title}.")

    if truncated:
        parts.append("Note: the file limit was reached, so analysis was truncated.")

    return " ".join(parts)


def default_limitations() -> list[str]:
    return [
        "Repository contents are inspected, not executed.",
        "Findings are advisory and may include false positives or missed issues.",
        "Only supported languages and configuration formats are analyzed.",
        "Readiness is a heuristic label, not a formal security assessment.",
    ]

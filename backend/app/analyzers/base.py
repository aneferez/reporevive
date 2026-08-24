"""Shared analyzer types and helpers."""

from __future__ import annotations

from ..models.enums import Category, Severity, VerificationStatus
from ..models.schemas import Finding

SEVERITY_ORDER = {
    Severity.critical: 0,
    Severity.high: 1,
    Severity.medium: 2,
    Severity.low: 3,
    Severity.info: 4,
}


def make_finding(
    *,
    severity: Severity,
    category: Category,
    title: str,
    description: str,
    recommendation: str,
    file: str | None = None,
    line: int | None = None,
    evidence: str | None = None,
    confidence: float = 0.7,
    verification_status: VerificationStatus = VerificationStatus.evidence_backed,
) -> Finding:
    """Construct a Finding with a placeholder id (assigned later by the runner)."""

    return Finding(
        id="",
        severity=severity,
        category=category.value,
        title=title,
        description=description,
        file=file,
        line=line,
        evidence=evidence,
        confidence=round(confidence, 2),
        recommendation=recommendation,
        verification_status=verification_status,
    )

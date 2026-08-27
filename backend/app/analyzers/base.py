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

# Path segments and filename shapes that indicate test / fixture / sample / mock
# / example code. Findings from these paths are almost always about intentional
# test data (fake secrets, demo API calls) rather than the real application, so
# analyzers treat them as low-signal to keep the report trustworthy.
_FIXTURE_DIRS = frozenset({
    "test", "tests", "__tests__", "__mocks__", "testdata", "fixtures", "fixture",
    "evaluation", "evaluations", "samples", "sample", "examples", "example",
    "mocks", "e2e", "stories", "demo", "demos",
})


def is_fixture_path(path: str | None) -> bool:
    """True when a path looks like test / fixture / sample / mock / example code."""
    if not path:
        return False
    norm = path.replace("\\", "/").lower()
    segments = norm.split("/")
    if any(seg in _FIXTURE_DIRS for seg in segments):
        return True
    name = segments[-1]
    if name.startswith(("test_", "conftest", "mock")) or "mockdata" in name:
        return True
    return name.endswith((
        "_test.py", ".test.ts", ".test.tsx", ".test.js", ".test.jsx",
        ".spec.ts", ".spec.tsx", ".spec.js",
        ".stories.ts", ".stories.tsx",
        ".example", ".sample", ".template",
    ))


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

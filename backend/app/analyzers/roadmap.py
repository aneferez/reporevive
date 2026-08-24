"""Prioritized recovery roadmap (FR-10).

Groups findings into recovery-oriented buckets (blockers, security, config,
deployment, tests/docs, optional) and emits one task per non-empty bucket, in
priority order, linking back to the findings and files that motivated it.
"""

from __future__ import annotations

from ..models.enums import Complexity, Priority, Severity
from ..models.schemas import Finding, RoadmapItem

# Ordered buckets: (task_key, title, categories, description, complexity).
_BUCKETS = [
    (
        "blockers",
        "Resolve API contract mismatches",
        {"api_mismatch"},
        "Align frontend calls with backend routes so core features work end to end.",
        Complexity.medium,
    ),
    (
        "dependencies",
        "Fix dependency/configuration defects",
        {"dependency"},
        "Repair broken manifests so the project can install and build.",
        Complexity.low,
    ),
    (
        "security",
        "Remove and rotate exposed secrets",
        {"secret"},
        "Purge suspected credentials from the repo and rotate them; load secrets "
        "from the environment.",
        Complexity.low,
    ),
    (
        "configuration",
        "Complete environment configuration",
        {"configuration"},
        "Document required environment variables and remove hardcoded URLs.",
        Complexity.low,
    ),
    (
        "deployment",
        "Add deployment readiness",
        {"deployment"},
        "Provide deployment configuration so the project can be shipped reliably.",
        Complexity.medium,
    ),
    (
        "quality",
        "Improve tests and documentation",
        {"testing", "documentation"},
        "Add automated tests and setup documentation to make the project maintainable.",
        Complexity.medium,
    ),
]

_SEVERITY_TO_PRIORITY = {
    Severity.critical: Priority.high,
    Severity.high: Priority.high,
    Severity.medium: Priority.medium,
    Severity.low: Priority.low,
    Severity.info: Priority.low,
}


def build_roadmap(findings: list[Finding]) -> list[RoadmapItem]:
    items: list[RoadmapItem] = []
    counter = 1

    for key, title, categories, description, complexity in _BUCKETS:
        matched = [f for f in findings if f.category in categories]
        if not matched:
            continue

        top_severity = min((f.severity for f in matched), key=_severity_rank)
        priority = _SEVERITY_TO_PRIORITY[top_severity]
        related_files = _dedupe([f.file for f in matched if f.file])

        items.append(
            RoadmapItem(
                id=f"task_{counter:03d}",
                priority=priority,
                title=title,
                description=f"{description} ({len(matched)} related finding(s)).",
                related_finding_ids=[f.id for f in matched],
                related_files=related_files[:8],
                estimated_complexity=complexity,
            )
        )
        counter += 1

    # High-priority tasks first.
    items.sort(key=lambda i: _priority_rank(i.priority))
    return items


def _severity_rank(sev: Severity) -> int:
    order = {
        Severity.critical: 0,
        Severity.high: 1,
        Severity.medium: 2,
        Severity.low: 3,
        Severity.info: 4,
    }
    return order[sev]


def _priority_rank(priority: Priority) -> int:
    return {Priority.high: 0, Priority.medium: 1, Priority.low: 2}[priority]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out

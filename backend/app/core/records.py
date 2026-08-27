"""Internal analysis state.

These structures are the backend's private working state. They are never sent
to the client directly; response models in ``models.schemas`` are built from
them. This keeps retrieval context, raw timings, and other internals out of the
public contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..models.enums import AnalysisStatus, SourceType, Stage
from ..models.schemas import (
    AnalysisSummary,
    ArchitectureResponse,
    Finding,
    RepositoryInfo,
    RoadmapItem,
    StackInfo,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RepoFile:
    """A single inspected text file, already redacted for storage/retrieval."""

    path: str  # normalized, forward-slash, repo-relative
    content: str  # redacted text content
    size_bytes: int
    language: str | None = None

    @property
    def lines(self) -> list[str]:
        return self.content.splitlines()


@dataclass
class AnalysisRecord:
    analysis_id: str
    repository: RepositoryInfo
    source_type: SourceType
    status: AnalysisStatus = AnalysisStatus.queued
    stage: Stage = Stage.queued
    progress: int = 0

    created_at: datetime = field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # SHA-256 of the per-analysis owner token (plaintext token is returned once
    # at creation and never stored). Used for ownership isolation.
    owner_token_hash: str | None = None

    # Failure info (redaction-safe, user-presentable).
    error_code: str | None = None
    error_message: str | None = None

    # Raw intake inputs consumed by the pipeline, then cleared to free memory.
    # For ZIP uploads: the validated archive bytes. For GitHub: the repo ref.
    archive_bytes: bytes | None = None
    archive_filename: str | None = None
    github_owner: str | None = None
    github_repo: str | None = None

    # Inspected, redacted files that back retrieval and evidence.
    files: list[RepoFile] = field(default_factory=list)
    files_analyzed: int = 0

    # Secret-pattern hits captured during redaction (masked), consumed by the
    # phase-3 secret analyzer. Typed as Any to avoid an import cycle.
    secret_hits: list = field(default_factory=list)

    # Lexical retrieval index backing grounded chat. Built in the AI stage.
    # Typed loosely to avoid importing retrieval here.
    retrieval_index: object | None = None

    # Deterministic + AI results.
    stack: StackInfo = field(default_factory=StackInfo)
    findings: list[Finding] = field(default_factory=list)
    architecture: ArchitectureResponse = field(default_factory=ArchitectureResponse)
    roadmap: list[RoadmapItem] = field(default_factory=list)
    overview: str = ""
    readiness_label: str = "unknown"
    limitations: list[str] = field(default_factory=list)

    # Notes for observability (never contains secrets or full file bodies).
    notes: list[str] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        start = self.started_at or self.created_at
        end = self.completed_at or utcnow()
        return max(0, int((end - start).total_seconds() * 1000))

    def summary(self) -> AnalysisSummary:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in self.findings:
            key = finding.severity.value
            if key in counts:
                counts[key] += 1
        from ..models.schemas import FindingsBySeverity

        return AnalysisSummary(
            files_analyzed=self.files_analyzed,
            analysis_duration_ms=self.duration_ms,
            findings_by_severity=FindingsBySeverity(**counts),
            readiness_label=self.readiness_label,
        )

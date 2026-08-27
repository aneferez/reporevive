"""Pydantic request/response models mirroring the frozen API contract.

Every response shape here corresponds to an endpoint in PRD section 11. Fields
marked optional are additive and safe for the frontend to ignore; existing
required fields and names must not change without a coordinated contract update.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .enums import (
    AnalysisStatus,
    Complexity,
    Priority,
    Severity,
    SourceType,
    VerificationStatus,
)

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class RepositoryInfo(BaseModel):
    name: str
    source_type: SourceType
    url: str | None = None


class StackInfo(BaseModel):
    frontend: list[str] = Field(default_factory=list)
    backend: list[str] = Field(default_factory=list)
    database: list[str] = Field(default_factory=list)
    testing: list[str] = Field(default_factory=list)


class FindingsBySeverity(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class AnalysisSummary(BaseModel):
    files_analyzed: int = 0
    analysis_duration_ms: int = 0
    findings_by_severity: FindingsBySeverity = Field(default_factory=FindingsBySeverity)
    readiness_label: str = "unknown"


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    repository_url: str


class AnalysisStartResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    repository: RepositoryInfo
    # Secret owner token, returned once at creation. Store it and send it back as
    # the X-Owner-Token header to access this analysis when enforcement is on.
    owner_token: str | None = None


# ---------------------------------------------------------------------------
# Status / summary
# ---------------------------------------------------------------------------


class AnalysisErrorInfo(BaseModel):
    code: str
    message: str


class AnalysisSummaryResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    stage: str
    repository: RepositoryInfo
    stack: StackInfo | None = None
    summary: AnalysisSummary | None = None
    created_at: datetime
    completed_at: datetime | None = None
    # Additive optional fields (safe to ignore) to support the progress screen.
    progress: int | None = None
    error: AnalysisErrorInfo | None = None


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


class Finding(BaseModel):
    id: str
    severity: Severity
    category: str
    title: str
    description: str
    file: str | None = None
    line: int | None = None
    evidence: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    recommendation: str
    verification_status: VerificationStatus


class FindingsResponse(BaseModel):
    items: list[Finding]
    total: int


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------


class ArchitectureComponent(BaseModel):
    id: str
    type: str
    label: str
    evidence_files: list[str] = Field(default_factory=list)


class ArchitectureConnection(BaseModel):
    source: str
    target: str
    label: str | None = None
    evidence_files: list[str] = Field(default_factory=list)


class ArchitectureResponse(BaseModel):
    components: list[ArchitectureComponent] = Field(default_factory=list)
    connections: list[ArchitectureConnection] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Roadmap
# ---------------------------------------------------------------------------


class RoadmapItem(BaseModel):
    id: str
    priority: Priority
    title: str
    description: str
    related_finding_ids: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    estimated_complexity: Complexity


class RoadmapResponse(BaseModel):
    items: list[RoadmapItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class Citation(BaseModel):
    file: str
    line: int | None = None
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    insufficient_evidence: bool = False


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class ReportResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    repository: RepositoryInfo
    overview: str
    readiness_label: str
    stack: StackInfo
    summary: AnalysisSummary
    architecture: ArchitectureResponse
    findings: FindingsResponse
    roadmap: RoadmapResponse
    limitations: list[str] = Field(default_factory=list)
    generated_at: datetime


# ---------------------------------------------------------------------------
# Deletion / health / errors
# ---------------------------------------------------------------------------


class DeleteResponse(BaseModel):
    analysis_id: str
    deleted: bool


class HealthResponse(BaseModel):
    status: str = "ok"
    app_env: str
    version: str
    ai_enabled: bool
    time: datetime


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail

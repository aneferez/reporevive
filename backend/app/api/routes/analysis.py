"""Analysis result endpoints.

GET    /api/analysis/{analysis_id}
GET    /api/analysis/{analysis_id}/architecture
GET    /api/analysis/{analysis_id}/findings
GET    /api/analysis/{analysis_id}/roadmap
POST   /api/analysis/{analysis_id}/chat
GET    /api/analysis/{analysis_id}/report
DELETE /api/analysis/{analysis_id}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...core.records import AnalysisRecord, utcnow
from ...core.store import AnalysisStore
from ...models.enums import AnalysisStatus
from ...models.schemas import (
    AnalysisErrorInfo,
    AnalysisSummaryResponse,
    ArchitectureResponse,
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    FindingsResponse,
    ReportResponse,
    RoadmapResponse,
)
from ..deps import get_record_or_404, require_completed, store_dep

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/{analysis_id}", response_model=AnalysisSummaryResponse)
def get_analysis(record: AnalysisRecord = Depends(get_record_or_404)) -> AnalysisSummaryResponse:
    completed = record.status == AnalysisStatus.completed
    error = None
    if record.status == AnalysisStatus.failed and record.error_code:
        error = AnalysisErrorInfo(
            code=record.error_code,
            message=record.error_message or "Analysis failed.",
        )
    return AnalysisSummaryResponse(
        analysis_id=record.analysis_id,
        status=record.status,
        stage=record.stage.value,
        repository=record.repository,
        stack=record.stack if completed else None,
        summary=record.summary() if completed else None,
        created_at=record.created_at,
        completed_at=record.completed_at,
        progress=record.progress,
        error=error,
    )


@router.get("/{analysis_id}/architecture", response_model=ArchitectureResponse)
def get_architecture(record: AnalysisRecord = Depends(get_record_or_404)) -> ArchitectureResponse:
    require_completed(record)
    return record.architecture


@router.get("/{analysis_id}/findings", response_model=FindingsResponse)
def get_findings(record: AnalysisRecord = Depends(get_record_or_404)) -> FindingsResponse:
    require_completed(record)
    return FindingsResponse(items=record.findings, total=len(record.findings))


@router.get("/{analysis_id}/roadmap", response_model=RoadmapResponse)
def get_roadmap(record: AnalysisRecord = Depends(get_record_or_404)) -> RoadmapResponse:
    require_completed(record)
    return RoadmapResponse(items=record.roadmap)


@router.post("/{analysis_id}/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    record: AnalysisRecord = Depends(get_record_or_404),
) -> ChatResponse:
    require_completed(record)
    # Phase 4 replaces this with retrieval-grounded, cited answers. Until then,
    # respond honestly rather than fabricating: no context has been indexed yet.
    from ...ai.chat import answer_question

    return answer_question(record, payload.question)


@router.get("/{analysis_id}/report", response_model=ReportResponse)
def get_report(record: AnalysisRecord = Depends(get_record_or_404)) -> ReportResponse:
    require_completed(record)
    return ReportResponse(
        analysis_id=record.analysis_id,
        status=record.status,
        repository=record.repository,
        overview=record.overview,
        readiness_label=record.readiness_label,
        stack=record.stack,
        summary=record.summary(),
        architecture=record.architecture,
        findings=FindingsResponse(items=record.findings, total=len(record.findings)),
        roadmap=RoadmapResponse(items=record.roadmap),
        limitations=record.limitations or _default_limitations(),
        generated_at=utcnow(),
    )


@router.delete("/{analysis_id}", response_model=DeleteResponse)
def delete_analysis(
    analysis_id: str, store: AnalysisStore = Depends(store_dep)
) -> DeleteResponse:
    # Idempotent: return 200 whether or not it existed, but report the result.
    deleted = store.delete(analysis_id)
    if not deleted:
        # Surface a clear 404 so the client knows nothing was there.
        get_record_or_404(analysis_id, store)
    return DeleteResponse(analysis_id=analysis_id, deleted=deleted)


def _default_limitations() -> list[str]:
    return [
        "Repository contents are inspected, not executed.",
        "Findings are advisory and may include false positives or missed issues.",
        "Only supported languages and configuration formats are analyzed.",
        "Health and readiness labels are heuristics, not a formal security audit.",
    ]

"""Repository intake endpoints.

POST /api/repositories/analyze  -> start public GitHub analysis
POST /api/repositories/upload   -> start ZIP archive analysis
"""

from __future__ import annotations

import uuid
from http import HTTPStatus

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from ...config import get_settings
from ...core.pipeline import run_analysis
from ...core.records import AnalysisRecord
from ...core.store import AnalysisStore
from ...intake.github import parse_github_url
from ...models.enums import AnalysisStatus, SourceType
from ...models.schemas import AnalysisStartResponse, AnalyzeRequest, RepositoryInfo
from ...security.ownership import hash_owner_token, new_owner_token
from ..deps import store_dep
from ..errors import AppError, ErrorCode
from ..ratelimit import rate_limit

router = APIRouter(prefix="/api/repositories", tags=["intake"])

_start_limit = rate_limit("analysis_start")


def _new_analysis_id() -> str:
    return f"analysis_{uuid.uuid4().hex[:12]}"


@router.post(
    "/analyze",
    response_model=AnalysisStartResponse,
    status_code=HTTPStatus.ACCEPTED,
    dependencies=[Depends(_start_limit)],
)
def analyze_repository(
    payload: AnalyzeRequest,
    background: BackgroundTasks,
    store: AnalysisStore = Depends(store_dep),
) -> AnalysisStartResponse:
    ref = parse_github_url(payload.repository_url)

    repository = RepositoryInfo(
        name=ref.repo,
        source_type=SourceType.github,
        url=ref.canonical_url,
    )
    owner_token = new_owner_token()
    record = AnalysisRecord(
        analysis_id=_new_analysis_id(),
        repository=repository,
        source_type=SourceType.github,
        github_owner=ref.owner,
        github_repo=ref.repo,
        owner_token_hash=hash_owner_token(owner_token),
    )
    store.create(record)
    background.add_task(run_analysis, store, record.analysis_id)

    return AnalysisStartResponse(
        analysis_id=record.analysis_id,
        status=AnalysisStatus.queued,
        repository=repository,
        owner_token=owner_token,
    )


@router.post(
    "/upload",
    response_model=AnalysisStartResponse,
    status_code=HTTPStatus.ACCEPTED,
    dependencies=[Depends(_start_limit)],
)
async def upload_repository(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    store: AnalysisStore = Depends(store_dep),
) -> AnalysisStartResponse:
    settings = get_settings()

    filename = file.filename or "upload.zip"
    if not filename.lower().endswith(".zip"):
        raise AppError(
            ErrorCode.INVALID_ARCHIVE,
            "Only .zip source archives are supported.",
        )

    # Read with a hard cap so an oversized upload can't exhaust memory: read one
    # byte past the limit to detect overflow, then reject.
    limit = settings.max_archive_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise AppError(
            ErrorCode.ARCHIVE_TOO_LARGE,
            f"Archive exceeds the maximum of {limit} bytes.",
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        )
    if not data:
        raise AppError(ErrorCode.INVALID_ARCHIVE, "The uploaded archive is empty.")

    name = filename[:-4] if filename.lower().endswith(".zip") else filename
    repository = RepositoryInfo(name=name, source_type=SourceType.zip, url=None)
    owner_token = new_owner_token()
    record = AnalysisRecord(
        analysis_id=_new_analysis_id(),
        repository=repository,
        source_type=SourceType.zip,
        archive_bytes=data,
        archive_filename=filename,
        owner_token_hash=hash_owner_token(owner_token),
    )
    store.create(record)
    background.add_task(run_analysis, store, record.analysis_id)

    return AnalysisStartResponse(
        analysis_id=record.analysis_id,
        status=AnalysisStatus.queued,
        repository=repository,
        owner_token=owner_token,
    )

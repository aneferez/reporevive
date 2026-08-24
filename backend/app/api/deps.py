"""Shared FastAPI dependencies and small helpers for the route handlers."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import Depends, Request

from ..config import get_settings
from ..core.records import AnalysisRecord
from ..core.store import AnalysisStore, get_store
from ..models.enums import AnalysisStatus
from ..security.ownership import OWNER_TOKEN_HEADER, verify_owner_token
from .errors import AppError, ErrorCode


def store_dep() -> AnalysisStore:
    return get_store()


def get_record_or_404(
    analysis_id: str, store: AnalysisStore = Depends(store_dep)
) -> AnalysisRecord:
    record = store.get(analysis_id)
    if record is None:
        raise AppError(
            ErrorCode.ANALYSIS_NOT_FOUND,
            f"No analysis found with id '{analysis_id}'.",
            status_code=HTTPStatus.NOT_FOUND,
        )
    return record


def _verify_ownership(record: AnalysisRecord, request: Request) -> None:
    """Enforce the owner token when enabled and the analysis has one."""

    if not get_settings().require_owner_token:
        return
    if not record.owner_token_hash:
        return  # created without a token (e.g. before enforcement was enabled)
    provided = request.headers.get(OWNER_TOKEN_HEADER, "")
    if not verify_owner_token(provided, record.owner_token_hash):
        raise AppError(
            ErrorCode.OWNER_TOKEN_INVALID,
            "A valid X-Owner-Token header is required for this analysis.",
            status_code=HTTPStatus.FORBIDDEN,
        )


def get_owned_record(
    analysis_id: str,
    request: Request,
    store: AnalysisStore = Depends(store_dep),
) -> AnalysisRecord:
    """Fetch an analysis and enforce ownership (404 if missing, 403 if not owned)."""

    record = get_record_or_404(analysis_id, store)
    _verify_ownership(record, request)
    return record


def require_completed(record: AnalysisRecord) -> AnalysisRecord:
    """Guard result endpoints so they return a clear error until data exists."""

    if record.status == AnalysisStatus.failed:
        raise AppError(
            record.error_code or ErrorCode.INTERNAL_ERROR,
            record.error_message or "Analysis failed.",
            status_code=HTTPStatus.CONFLICT,
        )
    if record.status != AnalysisStatus.completed:
        raise AppError(
            ErrorCode.ANALYSIS_NOT_READY,
            "Analysis is still in progress. Poll the status endpoint.",
            status_code=HTTPStatus.CONFLICT,
        )
    return record

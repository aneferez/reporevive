"""Shared FastAPI dependencies and small helpers for the route handlers."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import Depends

from ..core.records import AnalysisRecord
from ..core.store import AnalysisStore, get_store
from ..models.enums import AnalysisStatus
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

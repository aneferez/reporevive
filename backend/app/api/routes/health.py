"""Health endpoint (GET /health)."""

from __future__ import annotations

from fastapi import APIRouter

from ... import __version__
from ...config import get_settings
from ...core.records import utcnow
from ...models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_env=settings.app_env,
        version=__version__,
        ai_enabled=settings.ai_enabled,
        time=utcnow(),
    )

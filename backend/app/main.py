"""FastAPI application entrypoint.

Wires configuration, CORS, request context, structured error handling, and the
route modules that implement the shared API contract (PRD section 11).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.errors import register_exception_handlers
from .api.middleware import RequestContextMiddleware
from .api.routes import analysis, health, repositories
from .config import get_settings
from .logging_config import configure_logging

DESCRIPTION = (
    "RepoRevive backend — AI-assisted repository analysis and recovery. "
    "Inspects public GitHub repositories and uploaded ZIP archives, produces "
    "evidence-backed findings and a prioritized recovery roadmap, and answers "
    "repository-grounded questions. Repository code is never executed."
)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging("DEBUG" if settings.app_env == "development" else "INFO")

    app = FastAPI(
        title="RepoRevive API",
        version=__version__,
        description=DESCRIPTION,
    )

    # CORS: only the configured frontend origin(s) may call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(repositories.router)
    app.include_router(analysis.router)

    return app


app = create_app()

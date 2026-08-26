"""Application configuration.

All tunable limits and secrets are read from environment variables so a
portfolio-sized deployment can stay inside free-tier quotas without code
changes. Real secrets must never be committed; see ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Runtime -----------------------------------------------------------
    app_env: str = "development"
    port: int = 8000
    # Comma-separated list of allowed browser origins for CORS.
    frontend_origin: str = "http://localhost:5173"

    # --- AI provider (Gemini) ---------------------------------------------
    # Optional: when unset the backend runs in deterministic-only mode and the
    # AI layer degrades gracefully instead of failing.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    embedding_model: str = "gemini-embedding-001"
    ai_request_timeout_s: float = 30.0

    # Retrieval backend: lexical (default) | embeddings | pgvector | auto.
    # embeddings/pgvector require a configured AI key; they fall back to lexical
    # when the embedder is unavailable.
    retrieval_mode: str = "lexical"

    # --- GitHub intake ----------------------------------------------------
    # Optional, public-repos only. Purely raises the unauthenticated rate limit
    # (60 -> 5000 req/hr). Never used to access private repositories.
    github_token: str | None = None
    github_request_timeout_s: float = 30.0

    # --- Optional persistence ---------------------------------------------
    database_url: str | None = None

    # --- Safety limits (PRD section 7) ------------------------------------
    max_archive_bytes: int = 10 * 1024 * 1024  # 10 MB compressed
    max_archive_entries: int = 10_000  # ZIP/TAR metadata entries
    max_extracted_bytes: int = 50 * 1024 * 1024  # 50 MB extracted
    max_analyzed_files: int = 1000
    max_file_bytes: int = 256 * 1024  # 256 KB per text file
    max_ai_files: int = 100  # distinct files whose content may reach the AI
    max_ai_context_chars: int = 8000  # hard cap on retrieved context per AI call

    # --- Retention --------------------------------------------------------
    # Oldest analyses beyond this count are evicted from the in-memory store.
    max_stored_analyses: int = 100
    # Time-based retention: analyses older than this are purged (with their
    # pgvector rows). 0 disables time-based expiry (count cap still applies).
    analysis_ttl_seconds: int = 0

    # --- Rate limiting ----------------------------------------------------
    # In-process, per-client fixed-window limits on the expensive POST
    # endpoints. Status polling (GETs) is never limited. For multi-instance
    # deploys a shared backend (e.g. Redis) would be needed.
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_analysis_start_max: int = 10  # analyze + upload, per window
    rate_limit_chat_max: int = 30  # chat questions, per window
    # Require the X-Owner-Token header on analysis-scoped endpoints. Off by
    # default for backward compatibility; enable once the frontend stores the
    # owner_token returned on creation and sends it back.
    require_owner_token: bool = False

    # Number of trusted reverse-proxy hops in front of the app. 0 = ignore
    # X-Forwarded-For and use the socket peer (prevents client IP spoofing when
    # not behind a proxy). Set to 1 on platforms like Render.
    trusted_proxy_hops: int = 0

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

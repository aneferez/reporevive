"""In-process, per-client rate limiting for expensive POST endpoints.

A dependency-free fixed-window counter keyed by client IP + category. Applied
only to the abuse-prone mutating endpoints (analyze/upload/chat); status polling
GETs are intentionally never limited so the frontend can poll freely.

For a multi-instance deployment this would need a shared store (e.g. Redis);
that is out of scope for the single-instance MVP.
"""

from __future__ import annotations

import threading
import time
from http import HTTPStatus

from fastapi import Request

from ..config import Settings, get_settings
from .errors import AppError, ErrorCode

_MAX_BUCKETS = 4096  # cap memory; purge expired entries when exceeded


class RateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_s: int) -> tuple[bool, int]:
        """Register a request. Returns ``(allowed, retry_after_seconds)``."""

        now = time.monotonic()
        with self._lock:
            if len(self._buckets) > _MAX_BUCKETS:
                self._purge(now, window_s)
            start, count = self._buckets.get(key, (now, 0))
            if now - start >= window_s:
                start, count = now, 0
            count += 1
            self._buckets[key] = (start, count)
            if count > limit:
                retry = int(window_s - (now - start)) + 1
                return False, max(retry, 1)
            return True, 0

    def _purge(self, now: float, window_s: int) -> None:
        expired = [k for k, (start, _) in self._buckets.items() if now - start >= window_s]
        for k in expired:
            del self._buckets[k]


_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter


def reset_limiter() -> None:
    """Drop all rate-limit state. Used by tests for isolation."""

    global _limiter
    _limiter = None


def client_ip(request: Request) -> str:
    # Honor the first hop of X-Forwarded-For when behind a proxy (Render, etc.).
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _limits_for(category: str, settings: Settings) -> tuple[int, int]:
    window = settings.rate_limit_window_seconds
    if category == "chat":
        return settings.rate_limit_chat_max, window
    return settings.rate_limit_analysis_start_max, window


def rate_limit(category: str):
    """FastAPI dependency factory enforcing a per-client limit for a category."""

    def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        limit, window = _limits_for(category, settings)
        key = f"{category}:{client_ip(request)}"
        allowed, retry_after = get_limiter().hit(key, limit, window)
        if not allowed:
            raise AppError(
                ErrorCode.RATE_LIMITED,
                f"Too many requests. Please retry in {retry_after} second(s).",
                status_code=HTTPStatus.TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
            )

    return dependency

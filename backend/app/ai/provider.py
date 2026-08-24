"""Configurable Gemini provider (server-side key).

The provider is optional: if no key is configured or the SDK is not installed,
``available()`` is False and callers fall back to deterministic behavior. When a
call is attempted and fails, a structured ``AIProviderError`` is raised so the
API layer can return a recoverable error (PRD: AI failures -> structured errors).

The model id is read from configuration, never hardcoded (PRD section 10).
"""

from __future__ import annotations

import logging
from http import HTTPStatus

from ..api.errors import ErrorCode
from ..config import Settings

logger = logging.getLogger("reporevive.ai")


class AIProviderError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class GeminiProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def available(self) -> bool:
        if not self.settings.ai_enabled:
            return False
        try:
            import google.genai  # noqa: F401
        except Exception:  # noqa: BLE001 - SDK not installed is a normal state
            return False
        return True

    def generate(self, *, system: str, prompt: str, max_output_tokens: int = 1024) -> str:
        try:
            from google import genai
            from google.genai import types
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(
                ErrorCode.AI_PROVIDER_UNAVAILABLE,
                "The AI provider SDK is not available.",
                HTTPStatus.SERVICE_UNAVAILABLE,
            ) from exc

        try:
            client = genai.Client(api_key=self.settings.gemini_api_key)
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_output_tokens,
                    temperature=0.2,
                ),
            )
            text = getattr(response, "text", None)
            if not text:
                raise AIProviderError(
                    ErrorCode.AI_PROVIDER_UNAVAILABLE,
                    "The AI provider returned an empty response.",
                    HTTPStatus.BAD_GATEWAY,
                )
            return text.strip()
        except AIProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            code, status = _classify_error(exc)
            logger.warning("Gemini call failed: %s", exc)
            raise AIProviderError(code, "The AI provider request failed.", status) from exc


def _classify_error(exc: Exception) -> tuple[str, int]:
    text = str(exc).lower()
    if "quota" in text or "429" in text or "rate" in text or "resource_exhausted" in text:
        return ErrorCode.AI_QUOTA_EXCEEDED, HTTPStatus.TOO_MANY_REQUESTS
    return ErrorCode.AI_PROVIDER_UNAVAILABLE, HTTPStatus.SERVICE_UNAVAILABLE


def get_provider(settings: Settings) -> GeminiProvider:
    return GeminiProvider(settings)

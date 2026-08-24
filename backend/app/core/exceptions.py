"""Internal exceptions shared across core and intake without import cycles."""

from __future__ import annotations


class PipelineError(Exception):
    """A recoverable, user-presentable failure raised inside analysis.

    Carries a structured error ``code`` (one of ``api.errors.ErrorCode``) and a
    safe, redaction-free ``message`` suitable for returning to the client.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

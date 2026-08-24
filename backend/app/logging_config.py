"""Logging setup.

Structured-ish console logging with a request-id field. The app must never log
raw secrets or full sensitive file contents (PRD section 14); redaction happens
before values reach any log call, and analyzers log counts, not payloads.
"""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g. under uvicorn reload); don't duplicate.
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s :: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level.upper())

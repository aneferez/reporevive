"""Shared intake result type."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.records import RepoFile
from ..security.redaction import SecretHit


@dataclass
class IntakeResult:
    files: list[RepoFile] = field(default_factory=list)
    secret_hits: list[SecretHit] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    truncated: bool = False

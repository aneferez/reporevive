"""Enumerations shared across the API contract.

Values are part of the shared contract with the frontend. Do not rename
existing values without coordinating a contract change (PRD section 11).
"""

from __future__ import annotations

from enum import Enum


class AnalysisStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class Stage(str, Enum):
    """Human-facing progress stages surfaced on the analysis progress screen."""

    queued = "queued"
    validating = "validating"
    intake = "intake"
    inspecting = "inspecting_files"
    stack = "stack_detection"
    config = "config_checks"
    api = "api_analysis"
    secrets = "secret_checks"
    ai = "ai_analysis"
    report = "report_preparation"
    complete = "complete"
    failed = "failed"


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class Category(str, Enum):
    stack = "stack"
    configuration = "configuration"
    api_mismatch = "api_mismatch"
    secret = "secret"
    testing = "testing"
    documentation = "documentation"
    dependency = "dependency"
    deployment = "deployment"
    architecture = "architecture"


class VerificationStatus(str, Enum):
    """Whether a finding is directly supported by file evidence or inferred."""

    evidence_backed = "evidence_backed"
    inferred = "inferred"
    unknown = "unknown"


class SourceType(str, Enum):
    github = "github"
    zip = "zip"


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Complexity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ReadinessLabel(str, Enum):
    ready = "ready"
    needs_attention = "needs_attention"
    not_ready = "not_ready"
    unknown = "unknown"

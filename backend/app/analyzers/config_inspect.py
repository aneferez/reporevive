"""Configuration inspection (FR-05).

Detects environment-variable references, missing environment templates,
undocumented variables, and hardcoded local base URLs. All findings cite the
concrete file (and line where meaningful).
"""

from __future__ import annotations

import re

from ..models.enums import Category, Severity, VerificationStatus
from ..models.schemas import Finding
from .base import is_fixture_path, make_finding
from .context import AnalysisContext

# Env-var reference patterns per ecosystem.
_ENV_PATTERNS = [
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"process\.env\[['\"]([A-Z][A-Z0-9_]*)['\"]\]"),
    re.compile(r"import\.meta\.env\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"os\.environ\.get\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]"),
    re.compile(r"os\.getenv\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]"),
    re.compile(r"os\.environ\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]\s*\]"),
]

# Variables provided by the platform/runtime; not expected in a template.
_WELL_KNOWN = {
    "NODE_ENV", "PATH", "HOME", "PWD", "CI", "PORT", "HOSTNAME", "USER",
    "TZ", "LANG", "PYTHONPATH", "VIRTUAL_ENV",
}

_ENV_TEMPLATE_NAMES = (".env.example", ".env.sample", ".env.template", ".env.dist")

_LOCALHOST_RE = re.compile(r"https?://(?:localhost|127\.0\.0\.1)(?::\d+)?")
# A localhost URL alongside an env-var read is a dev fallback default, not a
# hardcoded URL (e.g. `import.meta.env.VITE_API_BASE_URL ?? "http://localhost"`).
_ENV_REF_HINT = re.compile(r"import\.meta\.env|process\.env|os\.getenv|os\.environ")


def inspect_configuration(ctx: AnalysisContext) -> list[Finding]:
    findings: list[Finding] = []

    referenced: dict[str, tuple[str, int]] = {}
    for pattern in _ENV_PATTERNS:
        for f in ctx.files:
            # Env-var reads inside test/fixture/sample code describe the fixture,
            # not this project's real configuration surface.
            if is_fixture_path(f.path):
                continue
            for line_no, line in enumerate(f.content.splitlines(), start=1):
                for match in pattern.finditer(line):
                    name = match.group(1)
                    referenced.setdefault(name, (f.path, line_no))

    documented = _documented_env_keys(ctx)
    template_exists = any(ctx.has_name(n) for n in _ENV_TEMPLATE_NAMES)

    meaningful = {k: v for k, v in referenced.items() if k not in _WELL_KNOWN}

    if meaningful and not template_exists:
        sample = ", ".join(sorted(meaningful)[:8])
        first_file = next(iter(meaningful.values()))[0]
        findings.append(
            make_finding(
                severity=Severity.high,
                category=Category.configuration,
                title="Missing environment template (.env.example)",
                description=(
                    f"{len(meaningful)} environment variable(s) are referenced in "
                    "code but there is no .env.example (or equivalent) documenting "
                    "them, so a new developer cannot know what to configure."
                ),
                recommendation="Add a .env.example listing every required variable "
                "with placeholder values.",
                file=first_file,
                evidence=f"Referenced without a template: {sample}",
                confidence=0.85,
                verification_status=VerificationStatus.evidence_backed,
            )
        )
    elif template_exists and meaningful:
        missing = sorted(k for k in meaningful if k not in documented)
        if missing:
            sample = ", ".join(missing[:8])
            file_path, line = meaningful[missing[0]]
            findings.append(
                make_finding(
                    severity=Severity.medium,
                    category=Category.configuration,
                    title="Environment variables missing from .env.example",
                    description=(
                        f"{len(missing)} variable(s) are referenced in code but not "
                        "documented in the environment template."
                    ),
                    recommendation="Add the missing variables to .env.example so the "
                    "configuration surface is complete.",
                    file=file_path,
                    line=line,
                    evidence=f"Undocumented: {sample}",
                    confidence=0.8,
                    verification_status=VerificationStatus.evidence_backed,
                )
            )

    findings.extend(_hardcoded_url_findings(ctx))
    return findings


def _documented_env_keys(ctx: AnalysisContext) -> set[str]:
    keys: set[str] = set()
    for name in _ENV_TEMPLATE_NAMES:
        for f in ctx.find_by_name(name):
            for line in f.content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key = line.split("=", 1)[0].strip()
                    if re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                        keys.add(key)
    return keys


def _hardcoded_url_findings(ctx: AnalysisContext) -> list[Finding]:
    findings: list[Finding] = []
    hits = []
    for f in ctx.files:
        base = ctx.basename(f.path).lower()
        # Skip places where a localhost default is expected/benign.
        if base.startswith(".env") or "config" in base or base in ("readme.md", "docker-compose.yml"):
            continue
        # Test/fixture/sample files legitimately hardcode localhost.
        if is_fixture_path(f.path):
            continue
        if f.language not in ("javascript", "typescript", "python"):
            continue
        for line_no, line in enumerate(f.content.splitlines(), start=1):
            if _LOCALHOST_RE.search(line) and not _ENV_REF_HINT.search(line):
                hits.append((f.path, line_no, line.strip()[:120]))
                break  # one per file is enough signal

    if hits:
        first = hits[0]
        findings.append(
            make_finding(
                severity=Severity.medium,
                category=Category.configuration,
                title="Hardcoded localhost URL in source",
                description=(
                    f"A localhost/base URL is hardcoded in {len(hits)} source file(s). "
                    "This typically breaks in other environments and should come from "
                    "configuration instead."
                ),
                recommendation="Move base URLs into environment variables "
                "(e.g. VITE_API_BASE_URL) rather than hardcoding them.",
                file=first[0],
                line=first[1],
                evidence=first[2],
                confidence=0.7,
                verification_status=VerificationStatus.evidence_backed,
            )
        )
    return findings

"""Testing and documentation assessment (FR-08)."""

from __future__ import annotations

from ..models.enums import Category, Severity, VerificationStatus
from ..models.schemas import Finding
from .base import make_finding
from .context import AnalysisContext

_SETUP_HINTS = (
    "install", "setup", "getting started", "npm install", "pip install",
    "yarn", "pnpm", "uvicorn", "npm run", "docker", "quick start", "usage",
)

_DEPLOY_FILES = (
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "render.yaml",
    "procfile", "vercel.json", "netlify.toml", "fly.toml", "railway.json",
    "app.yaml", "heroku.yml",
)


def assess_testing_docs(ctx: AnalysisContext) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_test_findings(ctx))
    findings.extend(_doc_findings(ctx))
    findings.extend(_deploy_findings(ctx))
    return findings


def _has_tests(ctx: AnalysisContext) -> bool:
    if ctx.has_path_segment("tests") or ctx.has_path_segment("test") or ctx.has_path_segment("__tests__"):
        return True
    py_tests = ctx.name_matches(lambda n: n.startswith("test_") and n.endswith(".py"))
    py_tests += ctx.name_matches(lambda n: n.endswith("_test.py"))
    if py_tests:
        return True
    js_tests = ctx.name_matches(lambda n: n.endswith((".test.js", ".test.ts", ".test.tsx", ".spec.js", ".spec.ts", ".spec.tsx")))
    return bool(js_tests)


def _test_findings(ctx: AnalysisContext) -> list[Finding]:
    if _has_tests(ctx):
        return []
    return [
        make_finding(
            severity=Severity.medium,
            category=Category.testing,
            title="No automated tests found",
            description="No recognizable test directory or test files were detected, "
            "so there is no automated safety net for changes.",
            recommendation="Add a test suite (e.g. Pytest for the backend, Vitest for "
            "the frontend) covering critical paths.",
            evidence="No tests/ directory or test_*/*.spec files found",
            confidence=0.8,
            verification_status=VerificationStatus.evidence_backed,
        )
    ]


def _doc_findings(ctx: AnalysisContext) -> list[Finding]:
    readme = None
    for f in ctx.files:
        if ctx.basename(f.path).lower().startswith("readme"):
            readme = f
            break

    if readme is None:
        return [
            make_finding(
                severity=Severity.high,
                category=Category.documentation,
                title="Missing README",
                description="No README was found, so there is no entry-point "
                "documentation explaining what the project is or how to run it.",
                recommendation="Add a README with an overview and setup/run instructions.",
                evidence="No README file present",
                confidence=0.9,
                verification_status=VerificationStatus.evidence_backed,
            )
        ]

    content = readme.content.lower()
    if len(readme.content.strip()) < 200 or not any(h in content for h in _SETUP_HINTS):
        return [
            make_finding(
                severity=Severity.medium,
                category=Category.documentation,
                title="README lacks setup instructions",
                description="A README exists but does not appear to include setup or run "
                "instructions, making onboarding difficult.",
                recommendation="Document install, configuration, and run steps in the README.",
                file=readme.path,
                evidence="No install/setup/run keywords detected in README",
                confidence=0.65,
                verification_status=VerificationStatus.inferred,
            )
        ]
    return []


def _deploy_findings(ctx: AnalysisContext) -> list[Finding]:
    for name in _DEPLOY_FILES:
        if ctx.has_name(name):
            return []
    if ctx.has_path_segment(".github"):
        # A workflows folder often carries deployment/CI config.
        if any("/workflows/" in f.path.lower() for f in ctx.files):
            return []
    return [
        make_finding(
            severity=Severity.low,
            category=Category.deployment,
            title="No deployment configuration found",
            description="No Dockerfile, platform config, or CI/deploy workflow was "
            "detected, so how the project is meant to be deployed is unclear.",
            recommendation="Add deployment configuration (e.g. a Dockerfile or a "
            "platform config such as render.yaml/vercel.json).",
            evidence="No recognized deployment/CI files found",
            confidence=0.6,
            verification_status=VerificationStatus.inferred,
        )
    ]

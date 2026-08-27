"""Benchmark runner (PRD section 17).

Runs the sample repositories and a set of intake/AI edge cases through the real
backend, checks each intentionally-introduced scenario, and reports metrics.

Run:  python -m evaluation.run_eval
"""

from __future__ import annotations

import os

# The benchmark measures deterministic analyzer/retrieval behavior. Force offline
# mode so a local .env with a real key doesn't make it hit the network or vary
# results run-to-run. Must run before app modules read settings.
os.environ["GEMINI_API_KEY"] = ""

import json
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path

from app.ai.chat import answer_question
from app.ai.provider import AIProviderError
from app.api.errors import AppError
from app.config import Settings
from app.core.exceptions import PipelineError
from app.core.records import AnalysisRecord
from app.intake.archive import extract_zip
from app.intake.github import parse_github_url

from .harness import run_repo, zip_bytes
from .samples import REPO_MORE_SECRETS_RAW, REPO_SECRETS_RAW, SAMPLE_REPOS


@dataclass
class ScenarioResult:
    id: str
    group: str
    description: str
    passed: bool
    detail: str = ""


@dataclass
class EvalReport:
    results: list[ScenarioResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total) if self.total else 0.0

    def group_rate(self, group: str) -> tuple[int, int]:
        items = [r for r in self.results if r.group == group]
        return sum(1 for r in items if r.passed), len(items)


# --- check helpers ---------------------------------------------------------


def _has_finding(record: AnalysisRecord, *, category: str | None = None, title_sub: str | None = None) -> bool:
    for f in record.findings:
        if category and f.category != category:
            continue
        if title_sub and title_sub.lower() not in f.title.lower():
            continue
        return True
    return False


def _stack_has(record: AnalysisRecord, bucket: str, value: str) -> bool:
    return value in getattr(record.stack, bucket, [])


def _priority_value(task) -> str:
    p = task.priority
    return p.value if hasattr(p, "value") else str(p)


def _roadmap_has(record: AnalysisRecord, title_sub: str, *, priority: str | None = None) -> bool:
    for t in record.roadmap:
        if title_sub.lower() not in t.title.lower():
            continue
        if priority and _priority_value(t) != priority:
            continue
        return True
    return False


def _arch_component_ids(record: AnalysisRecord) -> set[str]:
    return {c.id for c in record.architecture.components}


def _arch_component_type(record: AnalysisRecord, component_id: str) -> str | None:
    for c in record.architecture.components:
        if c.id == component_id:
            return c.type
    return None


def _arch_has_connection(record: AnalysisRecord, source: str, target: str) -> bool:
    return any(
        c.source == source and c.target == target for c in record.architecture.connections
    )


def evaluate() -> EvalReport:
    report = EvalReport()
    records = {name: run_repo(name, files) for name, files in SAMPLE_REPOS.items()}
    r = report.results

    healthy = records["healthy_react_fastapi"]
    # Stack detection correctness.
    r.append(ScenarioResult("stack-frontend-react", "stack", "Detect React", _stack_has(healthy, "frontend", "React")))
    r.append(ScenarioResult("stack-frontend-vite", "stack", "Detect Vite", _stack_has(healthy, "frontend", "Vite")))
    r.append(ScenarioResult("stack-frontend-ts", "stack", "Detect TypeScript", _stack_has(healthy, "frontend", "TypeScript")))
    r.append(ScenarioResult("stack-backend-fastapi", "stack", "Detect FastAPI", _stack_has(healthy, "backend", "FastAPI")))
    r.append(ScenarioResult("stack-db-postgres", "stack", "Detect PostgreSQL", _stack_has(healthy, "database", "PostgreSQL")))
    # Precision: healthy repo must NOT raise these.
    r.append(ScenarioResult("fp-no-testing", "precision", "No false test finding", not _has_finding(healthy, category="testing")))
    r.append(ScenarioResult("fp-no-docs", "precision", "No false docs finding", not _has_finding(healthy, category="documentation")))
    r.append(ScenarioResult("fp-no-deploy", "precision", "No false deploy finding", not _has_finding(healthy, category="deployment")))
    r.append(ScenarioResult("fp-no-config", "precision", "No false config finding", not _has_finding(healthy, category="configuration")))
    r.append(ScenarioResult("fp-no-secret", "precision", "No false secret finding", not _has_finding(healthy, category="secret")))
    r.append(ScenarioResult("healthy-api-mismatch", "findings", "Detect the one real API mismatch", _has_finding(healthy, category="api_mismatch")))

    cfg = records["broken_config"]
    r.append(ScenarioResult("cfg-missing-template", "findings", "Missing .env template", _has_finding(cfg, title_sub="Missing environment template")))
    r.append(ScenarioResult("cfg-hardcoded-url", "findings", "Hardcoded localhost URL", _has_finding(cfg, title_sub="Hardcoded localhost")))

    sec = records["exposed_secrets"]
    r.append(ScenarioResult("sec-aws", "findings", "Detect AWS key", _has_finding(sec, title_sub="AWS access key")))
    r.append(ScenarioResult("sec-github", "findings", "Detect GitHub token", _has_finding(sec, title_sub="GitHub token")))
    r.append(ScenarioResult("sec-private-key", "findings", "Detect private key", _has_finding(sec, title_sub="private key")))
    r.append(ScenarioResult("sec-generic", "findings", "Detect hardcoded credential", _has_finding(sec, category="secret")))
    redaction_clean = _redaction_clean(sec)
    r.append(ScenarioResult("sec-redaction", "redaction", "Raw secrets removed from stored content", redaction_clean[0], redaction_clean[1]))

    api = records["api_mismatch"]
    r.append(ScenarioResult("api-method", "findings", "Wrong HTTP method", _has_finding(api, title_sub="different HTTP method")))
    r.append(ScenarioResult("api-missing", "findings", "Missing backend route", _has_finding(api, title_sub="no matching backend route")))

    bare = records["bare_broken"]
    r.append(ScenarioResult("bare-invalid-pkg", "findings", "Invalid package.json", _has_finding(bare, category="dependency")))
    r.append(ScenarioResult("bare-missing-readme", "findings", "Missing README", _has_finding(bare, title_sub="Missing README")))
    r.append(ScenarioResult("bare-missing-tests", "findings", "Missing tests", _has_finding(bare, category="testing")))
    r.append(ScenarioResult("bare-missing-deploy", "findings", "Missing deployment config", _has_finding(bare, category="deployment")))

    flask = records["flask_mismatch"]
    r.append(ScenarioResult("flask-stack", "stack", "Detect Flask backend", _stack_has(flask, "backend", "Flask")))
    r.append(ScenarioResult("flask-method", "findings", "Flask wrong HTTP method", _has_finding(flask, title_sub="different HTTP method")))
    r.append(ScenarioResult("flask-missing", "findings", "Flask missing route", _has_finding(flask, title_sub="no matching backend route")))

    conflict = records["version_conflict"]
    r.append(ScenarioResult("dep-version-conflict", "findings", "Conflicting dependency versions", _has_finding(conflict, title_sub="Conflicting versions")))

    # --- Additional stack coverage ----------------------------------------
    django = records["django_postgres"]
    r.append(ScenarioResult("stack-django", "stack", "Detect Django", _stack_has(django, "backend", "Django")))
    r.append(ScenarioResult("stack-django-python", "stack", "Detect Python (Django)", _stack_has(django, "backend", "Python")))
    r.append(ScenarioResult("stack-django-postgres", "stack", "Detect PostgreSQL (Django)", _stack_has(django, "database", "PostgreSQL")))
    r.append(ScenarioResult("fp-django-clean", "precision", "Fully-configured Django repo raises no findings", not django.findings))

    em = records["express_mongo"]
    r.append(ScenarioResult("stack-express", "stack", "Detect Express", _stack_has(em, "backend", "Express")))
    r.append(ScenarioResult("stack-node", "stack", "Detect Node.js", _stack_has(em, "backend", "Node.js")))
    r.append(ScenarioResult("stack-mongodb", "stack", "Detect MongoDB", _stack_has(em, "database", "MongoDB")))
    r.append(ScenarioResult("stack-jest", "stack", "Detect Jest", _stack_has(em, "testing", "Jest")))
    r.append(ScenarioResult("express-api-missing", "findings", "Express missing backend route", _has_finding(em, title_sub="no matching backend route")))

    vue = records["vue_vite"]
    r.append(ScenarioResult("stack-vue", "stack", "Detect Vue", _stack_has(vue, "frontend", "Vue")))
    r.append(ScenarioResult("stack-vue-vite", "stack", "Detect Vite (Vue)", _stack_has(vue, "frontend", "Vite")))
    r.append(ScenarioResult("stack-vitest", "stack", "Detect Vitest", _stack_has(vue, "testing", "Vitest")))
    r.append(ScenarioResult("stack-cypress", "stack", "Detect Cypress", _stack_has(vue, "testing", "Cypress")))

    prisma = records["express_prisma"]
    r.append(ScenarioResult("stack-prisma-postgres", "stack", "Map Prisma provider to PostgreSQL", _stack_has(prisma, "database", "PostgreSQL")))

    # --- Additional secret-kind coverage ----------------------------------
    more = records["more_secrets"]
    r.append(ScenarioResult("sec-stripe", "findings", "Detect Stripe secret key", _has_finding(more, title_sub="Stripe secret key")))
    r.append(ScenarioResult("sec-slack", "findings", "Detect Slack token", _has_finding(more, title_sub="Slack token")))
    r.append(ScenarioResult("sec-google", "findings", "Detect Google API key", _has_finding(more, title_sub="Google API key")))
    r.append(ScenarioResult("sec-jwt", "findings", "Detect JSON Web Token", _has_finding(more, title_sub="JSON Web Token")))
    more_clean = _redaction_clean_of(more, REPO_MORE_SECRETS_RAW)
    r.append(ScenarioResult("sec-redaction-more", "redaction", "Stripe/Slack/Google/JWT removed from stored content", more_clean[0], more_clean[1]))

    # --- Recovery roadmap (FR-10) -----------------------------------------
    r.append(ScenarioResult("roadmap-secrets-security", "roadmap", "Secrets -> high-priority security task", _roadmap_has(sec, "Remove and rotate exposed secrets", priority="high")))
    r.append(ScenarioResult("roadmap-api-blockers", "roadmap", "API mismatch -> blocker task", _roadmap_has(api, "Resolve API contract mismatches")))
    r.append(ScenarioResult("roadmap-bare-quality", "roadmap", "Bare repo -> tests/docs task", _roadmap_has(bare, "Improve tests and documentation")))
    r.append(ScenarioResult("roadmap-bare-deploy", "roadmap", "Bare repo -> deployment task", _roadmap_has(bare, "Add deployment readiness")))
    r.append(ScenarioResult("roadmap-priority-order", "roadmap", "Roadmap lists highest priority first", bool(bare.roadmap) and _priority_value(bare.roadmap[0]) == "high"))

    # --- Architecture graph (FR-04) ---------------------------------------
    r.append(ScenarioResult("arch-healthy-components", "architecture", "Full-stack repo yields fe/be/db/deploy nodes", {"frontend", "backend", "database", "deployment"} <= _arch_component_ids(healthy)))
    r.append(ScenarioResult("arch-persistence-type", "architecture", "DB node uses PRD 'persistence' type", _arch_component_type(healthy, "database") == "persistence"))
    r.append(ScenarioResult("arch-fe-be-connection", "architecture", "Frontend->backend connection drawn", _arch_has_connection(healthy, "frontend", "backend")))
    r.append(ScenarioResult("arch-be-db-connection", "architecture", "Backend->database connection drawn", _arch_has_connection(healthy, "backend", "database")))
    r.append(ScenarioResult("arch-no-phantom-frontend", "architecture", "Backend-only repo has no frontend node", "frontend" not in _arch_component_ids(sec)))

    # --- Intake safety scenarios ------------------------------------------
    r.append(ScenarioResult("intake-bad-url", "intake", "Reject unsupported repo URL", _expect_apperror(lambda: parse_github_url("https://gitlab.com/a/b"), "INVALID_REPOSITORY_URL")))
    r.append(ScenarioResult("intake-oversize", "intake", "Reject oversized archive", _expect_pipeline_error(lambda: extract_zip(zip_bytes({"a.txt": "x" * 100}), Settings(max_extracted_bytes=10)), "ARCHIVE_TOO_LARGE")))
    traversal = zip_bytes({"ok.txt": "ok", "../evil.txt": "pwned"})
    r.append(ScenarioResult("intake-traversal", "intake", "Reject path traversal", _expect_pipeline_error(lambda: extract_zip(traversal, Settings()), "UNSAFE_ARCHIVE_ENTRY")))

    # --- Chat scenarios ----------------------------------------------------
    insufficient = answer_question(healthy, "quokka platypus zeppelin")
    r.append(ScenarioResult("chat-insufficient", "chat", "Insufficient evidence stated", insufficient.insufficient_evidence is True))
    r.append(ScenarioResult("chat-ai-error", "chat", "AI failure -> structured error", _chat_ai_error(healthy)))
    grounded = answer_question(healthy, "how does the health endpoint work")
    r.append(ScenarioResult("chat-grounded-citations", "chat", "Relevant question -> cited answer (offline)", grounded.insufficient_evidence is False and len(grounded.citations) > 0))

    return report


def _redaction_clean(record: AnalysisRecord) -> tuple[bool, str]:
    return _redaction_clean_of(record, REPO_SECRETS_RAW)


def _redaction_clean_of(record: AnalysisRecord, raw: list[str]) -> tuple[bool, str]:
    joined = "\n".join(f.content for f in record.files)
    leaked = [s for s in raw if s in joined]
    if leaked:
        return False, f"leaked: {leaked}"
    return True, "all raw secrets removed"


def _expect_apperror(fn, code: str) -> bool:
    try:
        fn()
    except AppError as exc:
        return exc.code == code
    except Exception:  # noqa: BLE001
        return False
    return False


def _expect_pipeline_error(fn, code: str) -> bool:
    try:
        fn()
    except PipelineError as exc:
        return exc.code == code
    except Exception:  # noqa: BLE001
        return False
    return False


def _chat_ai_error(record: AnalysisRecord) -> bool:
    import app.ai.chat as chat_mod

    class _FailingProvider:
        def available(self):
            return True

        def generate(self, *, system, prompt, max_output_tokens=1024):
            raise AIProviderError("AI_QUOTA_EXCEEDED", "quota", HTTPStatus.TOO_MANY_REQUESTS)

    original = chat_mod.get_provider
    chat_mod.get_provider = lambda settings: _FailingProvider()
    try:
        answer_question(record, "how does the health endpoint work")
        return False
    except AppError as exc:
        return exc.code == "AI_QUOTA_EXCEEDED"
    finally:
        chat_mod.get_provider = original


def _write_reports(report: EvalReport) -> None:
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    data = {
        "total": report.total,
        "passed": report.passed,
        "pass_rate": round(report.pass_rate, 3),
        "results": [r.__dict__ for r in report.results],
    }
    (out_dir / "latest.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> int:
    report = evaluate()
    print("RepoRevive evaluation")
    print("=" * 60)
    for res in report.results:
        mark = "PASS" if res.passed else "FAIL"
        extra = f"  ({res.detail})" if res.detail and not res.passed else ""
        print(f"[{mark}] {res.group:10s} {res.id:24s} {res.description}{extra}")
    print("=" * 60)
    for group in ("stack", "precision", "findings", "redaction", "roadmap", "architecture", "intake", "chat"):
        p, t = report.group_rate(group)
        if t:
            print(f"  {group:10s}: {p}/{t}")
    print(f"TOTAL: {report.passed}/{report.total} ({report.pass_rate * 100:.1f}%)")
    _write_reports(report)
    return 0 if report.passed == report.total else 1


if __name__ == "__main__":
    raise SystemExit(main())

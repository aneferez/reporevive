"""Technology-stack detection from explicit repository evidence (FR-03).

Only reports a technology when there is a concrete signal: a dependency
declaration, a config file, or characteristic source files. Records the evidence
files so the architecture view and findings can cite them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models.enums import Category, Severity, VerificationStatus
from ..models.schemas import Finding, StackInfo
from .base import make_finding
from .context import AnalysisContext


@dataclass
class StackResult:
    stack: StackInfo = field(default_factory=StackInfo)
    frontend_evidence: list[str] = field(default_factory=list)
    backend_evidence: list[str] = field(default_factory=list)
    database_evidence: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)
    package_managers: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def detect_stack(ctx: AnalysisContext) -> StackResult:
    result = StackResult()
    npm = ctx.all_npm_dependencies()
    npm_keys = set(npm.keys())
    py = ctx.python_dependencies()

    def has_npm(*names: str) -> bool:
        return any(n in npm_keys for n in names)

    pkg_paths = [p for p, _ in ctx.package_jsons()]
    req_paths = [f.path for f in ctx.find_by_name("requirements.txt")]
    req_paths += [f.path for f in ctx.find_by_name("pyproject.toml")]

    # --- Frontend ---------------------------------------------------------
    frontend: list[str] = []
    fe_evidence: set[str] = set()

    if has_npm("react", "react-dom") or ctx.find_by_suffix(".jsx", ".tsx"):
        frontend.append("React")
        fe_evidence.update(pkg_paths)
        fe_evidence.update(f.path for f in ctx.find_by_suffix(".jsx", ".tsx")[:3])
        result.flags["react"] = True

    vite_cfg = [f for f in ctx.files if ctx.basename(f.path).lower().startswith("vite.config")]
    if has_npm("vite") or vite_cfg:
        frontend.append("Vite")
        fe_evidence.update(f.path for f in vite_cfg)
        fe_evidence.update(pkg_paths)
        result.flags["vite"] = True

    if ctx.has_name("tsconfig.json") or has_npm("typescript") or ctx.find_by_suffix(".ts", ".tsx"):
        frontend.append("TypeScript")
        ts_cfg = ctx.first_by_name("tsconfig.json")
        if ts_cfg:
            fe_evidence.add(ts_cfg.path)
        result.flags["typescript"] = True

    if has_npm("vue") or ctx.find_by_suffix(".vue"):
        frontend.append("Vue")
        result.flags["vue"] = True
    if has_npm("svelte") or ctx.find_by_suffix(".svelte"):
        frontend.append("Svelte")
        result.flags["svelte"] = True
    if has_npm("next"):
        frontend.append("Next.js")
        result.flags["next"] = True
    if has_npm("@angular/core"):
        frontend.append("Angular")
        result.flags["angular"] = True
    if has_npm("nuxt"):
        frontend.append("Nuxt")
    if has_npm("@remix-run/react", "@remix-run/node"):
        frontend.append("Remix")
    if has_npm("solid-js"):
        frontend.append("SolidJS")
    if has_npm("astro") or ctx.find_by_suffix(".astro"):
        frontend.append("Astro")
    if has_npm("tailwindcss"):
        frontend.append("Tailwind CSS")

    # --- Backend ----------------------------------------------------------
    backend: list[str] = []
    be_evidence: set[str] = set()

    fastapi_imports = ctx.search(r"\b(from\s+fastapi|import\s+fastapi)\b", languages=("python",), limit=3)
    if "fastapi" in py or fastapi_imports:
        backend.append("FastAPI")
        result.flags["fastapi"] = True
        be_evidence.update(req_paths)
        be_evidence.update(f.path for f, _l, _t in fastapi_imports)

    if "flask" in py or ctx.search(r"\bfrom\s+flask\b", languages=("python",), limit=1):
        backend.append("Flask")
        result.flags["flask"] = True
        be_evidence.update(req_paths)
    if "django" in py:
        backend.append("Django")
        result.flags["django"] = True
        be_evidence.update(req_paths)

    express_imports = ctx.search(
        r"require\(['\"]express['\"]\)|from\s+['\"]express['\"]",
        languages=("javascript", "typescript"),
        limit=3,
    )
    if has_npm("express") or express_imports:
        backend.append("Express")
        result.flags["express"] = True
        be_evidence.update(pkg_paths)
        be_evidence.update(f.path for f, _l, _t in express_imports)

    # Python present if any python backend or .py source.
    if result.flags.get("fastapi") or result.flags.get("flask") or result.flags.get("django"):
        backend.append("Python")
    elif ctx.find_by_language("python"):
        # Python files present without a recognized framework.
        result.flags["python_only"] = True

    if result.flags.get("express") or (npm_keys and not frontend):
        if "Node.js" not in backend:
            backend.append("Node.js")

    # --- Package managers -------------------------------------------------
    if ctx.has_name("package-lock.json"):
        result.package_managers.append("npm")
    if ctx.has_name("yarn.lock"):
        result.package_managers.append("yarn")
    if ctx.has_name("pnpm-lock.yaml"):
        result.package_managers.append("pnpm")
    if req_paths and any("requirements" in p for p in req_paths):
        result.package_managers.append("pip")
    if any("[tool.poetry]" in (f.content or "") for f in ctx.find_by_name("pyproject.toml")):
        result.package_managers.append("poetry")

    # --- Testing ----------------------------------------------------------
    testing: list[str] = []
    py_test_files = ctx.name_matches(lambda n: n.startswith("test_") and n.endswith(".py")) + ctx.name_matches(
        lambda n: n.endswith("_test.py")
    )
    if "pytest" in py or py_test_files or ctx.has_path_segment("tests"):
        if "pytest" in py or py_test_files:
            testing.append("Pytest")
    if has_npm("vitest"):
        testing.append("Vitest")
    if has_npm("jest"):
        testing.append("Jest")
    if has_npm("@testing-library/react"):
        testing.append("React Testing Library")
    if has_npm("mocha"):
        testing.append("Mocha")
    if has_npm("cypress"):
        testing.append("Cypress")
    if has_npm("@playwright/test", "playwright"):
        testing.append("Playwright")

    # --- Database ---------------------------------------------------------
    database: list[str] = []
    db_evidence: set[str] = set()

    def add_db(name: str, evidence: list[str]) -> None:
        if name not in database:
            database.append(name)
        db_evidence.update(evidence)

    if any(p in py for p in ("psycopg2", "psycopg2-binary", "psycopg", "asyncpg")) or has_npm("pg"):
        add_db("PostgreSQL", req_paths + pkg_paths)
    if has_npm("@supabase/supabase-js") or "supabase" in py:
        add_db("PostgreSQL", req_paths + pkg_paths)
        result.flags["supabase"] = True
    if any(p in py for p in ("pymongo", "motor")) or has_npm("mongoose", "mongodb"):
        add_db("MongoDB", req_paths + pkg_paths)
    if any(p in py for p in ("pymysql", "mysqlclient")) or has_npm("mysql", "mysql2"):
        add_db("MySQL", req_paths + pkg_paths)
    if "redis" in py or has_npm("redis", "ioredis"):
        add_db("Redis", req_paths + pkg_paths)
    if ctx.find_by_suffix(".sqlite", ".sqlite3", ".db") or "aiosqlite" in py:
        add_db("SQLite", [f.path for f in ctx.find_by_suffix(".sqlite", ".sqlite3", ".db")] or req_paths)

    # DATABASE_URL hints in env templates.
    for hit_file, _line, text in ctx.search(r"(?i)DATABASE_URL\s*[=:].*postgres", limit=1):
        add_db("PostgreSQL", [hit_file.path])

    # Prisma (maps to its configured provider when the schema is available).
    if has_npm("@prisma/client", "prisma"):
        result.flags["prisma"] = True
        provider = _prisma_provider(ctx)
        schema_paths = [f.path for f in ctx.find_by_name("schema.prisma")]
        if provider:
            add_db(provider, schema_paths or pkg_paths)
        else:
            add_db("SQL (Prisma)", schema_paths or pkg_paths)

    # SQLAlchemy without a more specific dialect already found.
    if "sqlalchemy" in py and not any(d in database for d in ("PostgreSQL", "MySQL", "SQLite")):
        add_db("SQL (SQLAlchemy)", req_paths)

    # Firebase / Firestore.
    if has_npm("firebase", "firebase-admin") or "firebase-admin" in py:
        add_db("Firebase", pkg_paths + req_paths)

    result.stack = StackInfo(
        frontend=_dedupe(frontend),
        backend=_dedupe(backend),
        database=_dedupe(database),
        testing=_dedupe(testing),
    )
    result.frontend_evidence = sorted(fe_evidence)
    result.backend_evidence = sorted(be_evidence)
    result.database_evidence = sorted(db_evidence)

    result.findings.extend(_dependency_findings(ctx))
    result.findings.extend(_version_conflict_findings(ctx))
    return result


def _prisma_provider(ctx: AnalysisContext) -> str | None:
    mapping = {
        "postgresql": "PostgreSQL",
        "postgres": "PostgreSQL",
        "mysql": "MySQL",
        "sqlite": "SQLite",
        "mongodb": "MongoDB",
        "sqlserver": "SQL Server",
    }
    for f in ctx.find_by_name("schema.prisma"):
        m = re.search(r"provider\s*=\s*['\"]([a-zA-Z]+)['\"]", f.content)
        if m and m.group(1).lower() in mapping:
            return mapping[m.group(1).lower()]
    return None


def _first_major(spec: str) -> str | None:
    m = re.search(r"(\d+)", spec)
    return m.group(1) if m else None


def _version_conflict_findings(ctx: AnalysisContext) -> list[Finding]:
    findings: list[Finding] = []

    # npm: same package declared with conflicting MAJOR versions across manifests.
    npm_versions: dict[str, set[tuple[str, str]]] = {}  # pkg -> {(major, path)}
    for path, data in ctx.package_jsons():
        for section in ("dependencies", "devDependencies"):
            deps = data.get(section, {})
            if not isinstance(deps, dict):
                continue
            for pkg, spec in deps.items():
                major = _first_major(str(spec))
                if major:
                    npm_versions.setdefault(pkg, set()).add((major, path))

    for pkg, entries in npm_versions.items():
        majors = {major for major, _ in entries}
        if len(majors) > 1:
            detail = ", ".join(sorted(f"{major}.x in {path}" for major, path in entries))
            findings.append(
                make_finding(
                    severity=Severity.medium,
                    category=Category.dependency,
                    title=f"Conflicting versions of '{pkg}'",
                    description=f"'{pkg}' is declared with incompatible major versions "
                    "across package manifests, which can cause install or runtime errors.",
                    recommendation=f"Align '{pkg}' to a single compatible version.",
                    file=sorted(path for _, path in entries)[0],
                    evidence=detail,
                    confidence=0.8,
                    verification_status=VerificationStatus.evidence_backed,
                )
            )

    # Python: same package pinned to different exact versions across requirements.
    py_pins: dict[str, set[str]] = {}
    for f in ctx.find_by_name("requirements.txt") + ctx.find_by_name("requirements-dev.txt"):
        for line in f.content.splitlines():
            line = line.strip()
            if "==" in line and not line.startswith("#"):
                name, _, ver = line.partition("==")
                name = name.strip().lower()
                ver = ver.split(";")[0].strip()
                if name and ver:
                    py_pins.setdefault(name, set()).add(ver)

    for pkg, versions in py_pins.items():
        if len(versions) > 1:
            findings.append(
                make_finding(
                    severity=Severity.medium,
                    category=Category.dependency,
                    title=f"Conflicting pinned versions of '{pkg}'",
                    description=f"'{pkg}' is pinned to different versions across "
                    "requirements files.",
                    recommendation=f"Pin '{pkg}' to a single version.",
                    evidence=f"{pkg}: {', '.join(sorted(versions))}",
                    confidence=0.85,
                    verification_status=VerificationStatus.evidence_backed,
                )
            )

    return findings


def _dependency_findings(ctx: AnalysisContext) -> list[Finding]:
    findings: list[Finding] = []
    # Malformed package.json is a concrete, verifiable defect.
    for f in ctx.find_by_name("package.json"):
        from .context import safe_json

        if safe_json(f.content) is None:
            findings.append(
                make_finding(
                    severity=Severity.high,
                    category=Category.dependency,
                    title="Invalid package.json",
                    description="package.json is present but is not valid JSON, which "
                    "will break dependency installation and tooling.",
                    recommendation="Fix the JSON syntax in package.json.",
                    file=f.path,
                    evidence="package.json failed to parse as JSON",
                    confidence=0.95,
                    verification_status=VerificationStatus.evidence_backed,
                )
            )
    return findings


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out

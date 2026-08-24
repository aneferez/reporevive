"""API contract comparison (FR-06).

Extracts backend route declarations (FastAPI, Express) and frontend HTTP calls
(fetch, axios-style clients), normalizes paths, and flags:

* a frontend call with no matching backend route, and
* a path that exists but is called with a different HTTP method.

This is inherently heuristic, so it is deliberately lenient (generous prefix
handling, wildcarded path params) to avoid false "missing route" findings, and
every finding cites the frontend source location.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models.enums import Category, Severity, VerificationStatus
from ..models.schemas import Finding
from .base import make_finding
from .context import AnalysisContext

_METHODS = ("get", "post", "put", "delete", "patch")

_FASTAPI_DECORATOR = re.compile(
    r"\.(get|post|put|delete|patch|options|head)\(\s*f?['\"]([^'\"]+)['\"]"
)
_EXPRESS_ROUTE = re.compile(
    r"\.(get|post|put|delete|patch|all)\(\s*['\"`]([^'\"`]+)['\"`]"
)
# Flask: @app.route("/path", methods=[...]) — methods optional (defaults GET).
_FLASK_ROUTE = re.compile(r"\.route\(\s*['\"]([^'\"]+)['\"](?P<rest>[^)]*)\)")
_FLASK_METHODS = re.compile(r"methods\s*=\s*\[([^\]]*)\]")
_FLASK_URL_PREFIX = re.compile(r"url_prefix\s*=\s*['\"]([^'\"]+)['\"]")
# Django: path("route/", view) / re_path(r"^route/$", view) in a urlconf.
_DJANGO_PATH = re.compile(r"\b(?:re_path|path)\(\s*r?['\"]([^'\"]+)['\"]")
_PREFIX = re.compile(r"prefix\s*=\s*['\"]([^'\"]+)['\"]")
_EXPRESS_MOUNT = re.compile(r"\.use\(\s*['\"]([^'\"]+)['\"]")
# A JS/TS file is only treated as an Express backend (routes, not client calls)
# when it actually pulls in express — otherwise ``api.post('/x')`` client calls
# get misread as route declarations.
_EXPRESS_SIGNAL = re.compile(r"require\(['\"]express['\"]\)|from\s+['\"]express['\"]|express\(\)")

_FETCH = re.compile(r"fetch\(\s*[`'\"]([^`'\"]+)[`'\"]")
_CLIENT_CALL = re.compile(r"\b([a-zA-Z_]\w*)\.(get|post|put|delete|patch)\(\s*[`'\"]([^`'\"]+)[`'\"]")
_METHOD_OPT = re.compile(r"method\s*:\s*['\"](\w+)['\"]", re.IGNORECASE)

_HTTP_CLIENT_NAMES = {"axios", "api", "http", "client", "request", "service", "apiclient", "httpclient"}


@dataclass
class BackendRoute:
    method: str
    path: str  # normalized pattern
    file: str
    line: int


@dataclass
class FrontendCall:
    method: str
    path: str  # normalized pattern
    file: str
    line: int
    raw: str


@dataclass
class ApiResult:
    findings: list[Finding] = field(default_factory=list)
    backend_routes: int = 0
    frontend_calls: int = 0


def analyze_api_contract(ctx: AnalysisContext) -> ApiResult:
    routes = _extract_backend_routes(ctx)
    calls = _extract_frontend_calls(ctx)
    result = ApiResult(backend_routes=len(routes), frontend_calls=len(calls))

    if not routes or not calls:
        return result  # nothing reliable to compare

    route_keys = {(r.method, r.path) for r in routes}
    route_paths = {r.path for r in routes}
    backend_first_segments = {_first_segment(r.path) for r in routes}

    findings: list[Finding] = []
    for call in calls:
        # Only compare calls that plausibly target this backend.
        if "api" not in call.path and _first_segment(call.path) not in backend_first_segments:
            continue
        if (call.method, call.path) in route_keys:
            continue
        if call.path in route_paths:
            findings.append(
                make_finding(
                    severity=Severity.high,
                    category=Category.api_mismatch,
                    title="Frontend uses a different HTTP method than the backend route",
                    description=(
                        f"The frontend issues a {call.method} to '{call.path}', but the "
                        "backend declares that path with different method(s)."
                    ),
                    recommendation="Align the frontend method with the backend route, "
                    "or add the missing method handler.",
                    file=call.file,
                    line=call.line,
                    evidence=f"{call.method} {call.path}  ({call.raw})",
                    confidence=0.8,
                    verification_status=VerificationStatus.evidence_backed,
                )
            )
        else:
            findings.append(
                make_finding(
                    severity=Severity.high,
                    category=Category.api_mismatch,
                    title="Frontend endpoint has no matching backend route",
                    description=(
                        f"A frontend request references '{call.path}' ({call.method}), "
                        "which was not found in the detected backend route map."
                    ),
                    recommendation="Implement the matching backend route or update the "
                    "frontend to call an existing endpoint.",
                    file=call.file,
                    line=call.line,
                    evidence=f"{call.method} {call.path}  ({call.raw})",
                    confidence=0.75,
                    verification_status=VerificationStatus.evidence_backed,
                )
            )

    # Cap to keep the findings list actionable rather than overwhelming.
    result.findings = findings[:12]
    return result


def _extract_backend_routes(ctx: AnalysisContext) -> list[BackendRoute]:
    routes: list[BackendRoute] = []

    # FastAPI + Flask (Python): decorator lines only.
    py_files = ctx.find_by_language("python")
    prefixes = _collect_prefixes(py_files, _PREFIX) + _collect_prefixes(py_files, _FLASK_URL_PREFIX)
    prefixes = sorted(set(prefixes))
    for f in py_files:
        for line_no, line in enumerate(f.content.splitlines(), start=1):
            stripped = line.lstrip()
            if not stripped.startswith("@"):
                continue
            fastapi_m = _FASTAPI_DECORATOR.search(stripped)
            if fastapi_m:
                method, raw_path = fastapi_m.group(1).upper(), fastapi_m.group(2)
                if raw_path.startswith("/"):
                    for variant in _path_variants(raw_path, prefixes):
                        routes.append(BackendRoute(method, variant, f.path, line_no))
                continue
            flask_m = _FLASK_ROUTE.search(stripped)
            if flask_m:
                raw_path = flask_m.group(1)
                if not raw_path.startswith("/"):
                    continue
                methods = _flask_methods(flask_m.group("rest"))
                for meth in methods:
                    for variant in _path_variants(raw_path, prefixes):
                        routes.append(BackendRoute(meth, variant, f.path, line_no))

    routes.extend(_extract_django_routes(ctx))

    # Express (JS/TS) — only files that actually import express.
    js_files = [
        f for f in ctx.find_by_language("javascript", "typescript")
        if _EXPRESS_SIGNAL.search(f.content)
    ]
    mounts = _collect_prefixes(js_files, _EXPRESS_MOUNT)
    for f in js_files:
        for line_no, line in enumerate(f.content.splitlines(), start=1):
            m = _EXPRESS_ROUTE.search(line)
            if not m:
                continue
            raw_path = m.group(2)
            if not raw_path.startswith("/"):
                continue
            method = m.group(1).upper()
            methods = _METHODS if method == "ALL" else (method,)
            for meth in methods:
                for variant in _path_variants(raw_path, mounts):
                    routes.append(BackendRoute(meth.upper(), variant, f.path, line_no))

    return routes


def _extract_frontend_calls(ctx: AnalysisContext) -> list[FrontendCall]:
    calls: list[FrontendCall] = []
    for f in ctx.find_by_language("javascript", "typescript"):
        # Express backend files declare routes, not client calls.
        if _EXPRESS_SIGNAL.search(f.content):
            continue
        lines = f.content.splitlines()
        for line_no, line in enumerate(lines, start=1):
            window = " ".join(lines[line_no - 1 : line_no + 2])  # this + next 2 lines

            for m in _FETCH.finditer(line):
                path = _normalize_path(m.group(1))
                if path is None:
                    continue
                method_match = _METHOD_OPT.search(window)
                method = (method_match.group(1).upper() if method_match else "GET")
                calls.append(FrontendCall(method, path, f.path, line_no, m.group(0)[:80]))

            for m in _CLIENT_CALL.finditer(line):
                obj, method, raw = m.group(1).lower(), m.group(2).upper(), m.group(3)
                path = _normalize_path(raw)
                if path is None:
                    continue
                if obj not in _HTTP_CLIENT_NAMES and "api" not in raw:
                    continue
                calls.append(FrontendCall(method, path, f.path, line_no, m.group(0)[:80]))
    return calls


def _flask_methods(rest: str) -> tuple[str, ...]:
    m = _FLASK_METHODS.search(rest or "")
    if not m:
        return ("GET",)
    names = re.findall(r"['\"](\w+)['\"]", m.group(1))
    return tuple(n.upper() for n in names) or ("GET",)


def _extract_django_routes(ctx: AnalysisContext) -> list[BackendRoute]:
    django_used = bool(ctx.python_dependencies() & {"django"}) or bool(
        ctx.search(r"^\s*(from|import)\s+django", languages=("python",), limit=1)
    )
    if not django_used:
        return []

    routes: list[BackendRoute] = []
    for f in ctx.find_by_language("python"):
        if "urlpatterns" not in f.content and not f.path.lower().endswith("urls.py"):
            continue
        for line_no, line in enumerate(f.content.splitlines(), start=1):
            if "include(" in line:  # nested urlconf prefix, not a leaf route
                continue
            m = _DJANGO_PATH.search(line)
            if not m:
                continue
            norm = _django_normalize(m.group(1))
            if not norm:
                continue
            # Django routing is method-agnostic at the URL layer; register all
            # methods so only genuine missing-route mismatches are reported.
            for meth in _METHODS:
                routes.append(BackendRoute(meth.upper(), norm, f.path, line_no))
    return routes


def _django_normalize(raw: str) -> str | None:
    raw = raw.strip().lstrip("^").rstrip("$")
    raw = re.sub(r"<[^>]+>", "*", raw)  # <int:id> path converters
    raw = re.sub(r"\(\?P<[^>]+>[^)]*\)", "*", raw)  # named regex groups
    raw = re.sub(r"\([^)]*\)", "*", raw)  # other regex groups
    if not raw.startswith("/"):
        raw = "/" + raw
    return _normalize_path(raw)


def _collect_prefixes(files, pattern: re.Pattern[str]) -> list[str]:
    prefixes: set[str] = set()
    for f in files:
        for m in pattern.finditer(f.content):
            value = m.group(1)
            if value.startswith("/"):
                prefixes.add(value.rstrip("/"))
    return sorted(prefixes)


def _path_variants(raw_path: str, prefixes: list[str]) -> set[str]:
    """A route path plus every plausible prefixed form (lenient matching)."""

    base = _normalize_path(raw_path)
    variants: set[str] = set()
    if base:
        variants.add(base)
    for prefix in prefixes:
        combined = _normalize_path(prefix + raw_path)
        if combined:
            variants.add(combined)
    return variants or ({base} if base else set())


def _normalize_path(raw: str) -> str | None:
    path = raw.split("?", 1)[0].split("#", 1)[0]
    # Start at the first slash so leading base-URL interpolation is dropped.
    idx = path.find("/")
    if idx == -1:
        return None
    path = path[idx:]
    path = re.sub(r"\$\{[^}]*\}", "*", path)
    path = re.sub(r"\{[^}]*\}", "*", path)
    path = re.sub(r":[A-Za-z_]\w*", "*", path)

    segments: list[str] = []
    for seg in path.split("/"):
        if seg == "":
            continue
        if seg.isdigit():
            seg = "*"
        segments.append(seg)
    if not segments:
        return "/"
    return "/" + "/".join(segments)


def _first_segment(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    return parts[0] if parts else ""

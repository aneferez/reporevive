from __future__ import annotations

from app.analyzers.api_contract import analyze_api_contract

from .helpers import make_ctx

_BACKEND = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/jobs")
def list_jobs():
    return []

@app.get("/api/items")
def items():
    return []
"""


def test_missing_backend_route_flagged():
    ctx = make_ctx(
        {
            "backend/main.py": _BACKEND,
            "frontend/jobs.ts": (
                'export const search = () => fetch("/api/jobs/search", { method: "POST" });\n'
            ),
        }
    )
    result = analyze_api_contract(ctx)
    assert any(
        f.title == "Frontend endpoint has no matching backend route" for f in result.findings
    )


def test_method_mismatch_flagged():
    ctx = make_ctx(
        {
            "backend/main.py": _BACKEND,
            "frontend/items.ts": 'export const add = () => api.post("/api/items");\n',
        }
    )
    result = analyze_api_contract(ctx)
    assert any("different HTTP method" in f.title for f in result.findings)


def test_matching_route_produces_no_finding():
    ctx = make_ctx(
        {
            "backend/main.py": _BACKEND,
            "frontend/jobs.ts": 'export const load = () => fetch("/api/jobs");\n',
        }
    )
    result = analyze_api_contract(ctx)
    assert result.findings == []


def test_no_backend_routes_means_no_comparison():
    ctx = make_ctx({"frontend/jobs.ts": 'fetch("/api/jobs/search");\n'})
    result = analyze_api_contract(ctx)
    assert result.findings == []

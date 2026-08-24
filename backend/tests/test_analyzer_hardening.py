from __future__ import annotations

from app.analyzers.api_contract import analyze_api_contract
from app.analyzers.stack import detect_stack

from .helpers import make_ctx


# --- Flask -----------------------------------------------------------------

_FLASK_BACKEND = """
from flask import Flask
app = Flask(__name__)

@app.route("/api/users", methods=["GET"])
def users():
    return []

@app.route("/api/login", methods=["POST"])
def login():
    return {}
"""


def test_flask_routes_extracted_and_method_mismatch():
    ctx = make_ctx(
        {
            "backend/requirements.txt": "flask\n",
            "backend/app.py": _FLASK_BACKEND,
            "frontend/api.ts": 'export const u = () => fetch("/api/users", { method: "POST" });\n',
        }
    )
    result = analyze_api_contract(ctx)
    assert any("different HTTP method" in f.title for f in result.findings)


def test_flask_missing_route():
    ctx = make_ctx(
        {
            "backend/requirements.txt": "flask\n",
            "backend/app.py": _FLASK_BACKEND,
            "frontend/api.ts": 'export const o = () => fetch("/api/orders");\n',
        }
    )
    result = analyze_api_contract(ctx)
    assert any("no matching backend route" in f.title for f in result.findings)


# --- Django ----------------------------------------------------------------


def test_django_routes_extracted():
    ctx = make_ctx(
        {
            "backend/requirements.txt": "django\n",
            "backend/urls.py": (
                "from django.urls import path\n"
                "urlpatterns = [\n"
                '    path("api/items/", views.items),\n'
                '    path("api/items/<int:pk>/", views.item),\n'
                "]\n"
            ),
            "frontend/api.ts": (
                'export const missing = () => fetch("/api/orders");\n'
                'export const ok = () => fetch("/api/items/");\n'
            ),
        }
    )
    result = analyze_api_contract(ctx)
    titles = [f.title for f in result.findings]
    # /api/orders is missing; /api/items/ exists (method-agnostic) -> not flagged.
    assert any("no matching backend route" in t for t in titles)
    assert all("/api/items" not in (f.evidence or "") for f in result.findings)


# --- Stack additions -------------------------------------------------------


def test_prisma_provider_detected_as_postgres():
    ctx = make_ctx(
        {
            "package.json": '{"dependencies":{"@prisma/client":"5"}}',
            "prisma/schema.prisma": 'datasource db {\n  provider = "postgresql"\n  url = env("DATABASE_URL")\n}\n',
        }
    )
    result = detect_stack(ctx)
    assert "PostgreSQL" in result.stack.database


def test_firebase_detected():
    ctx = make_ctx({"package.json": '{"dependencies":{"firebase":"10"}}'})
    result = detect_stack(ctx)
    assert "Firebase" in result.stack.database


def test_npm_version_conflict_flagged():
    ctx = make_ctx(
        {
            "frontend/package.json": '{"dependencies":{"react":"^18.2.0"}}',
            "admin/package.json": '{"dependencies":{"react":"^17.0.2"}}',
        }
    )
    result = detect_stack(ctx)
    assert any("Conflicting versions of 'react'" in f.title for f in result.findings)


def test_python_pin_conflict_flagged():
    ctx = make_ctx(
        {
            "requirements.txt": "requests==2.31.0\n",
            "requirements-dev.txt": "requests==2.28.0\n",
        }
    )
    result = detect_stack(ctx)
    assert any("Conflicting pinned versions of 'requests'" in f.title for f in result.findings)

"""Synthetic sample repositories for evaluation (PRD section 17).

Each repo is a dict of repo-relative path -> file content. They deliberately
introduce known scenarios (missing config, API mismatches, secrets, etc.) so the
analyzers can be measured for precision and false positives. All secrets here are
fake, non-functional dummy values used only for pattern testing.
"""

from __future__ import annotations

_LONG_README = (
    "# Sample Project\n\n"
    "This is a sample project used for evaluation. " * 6
    + "\n\n## Setup\n\n"
    "1. Run `npm install` in `frontend/`.\n"
    "2. Run `pip install -r requirements.txt` in `backend/`.\n"
    "3. Start the API with `uvicorn app.main:app --reload`.\n"
)

# ---------------------------------------------------------------------------
# 1. A mostly-healthy React + FastAPI app with a single API mismatch.
#    Used to verify precision (no false positives on tests/docs/deploy/config).
# ---------------------------------------------------------------------------
REPO_HEALTHY = {
    "frontend/package.json": (
        '{"name":"web","dependencies":{"react":"^18","react-dom":"^18"},'
        '"devDependencies":{"vite":"^5","typescript":"^5","vitest":"^1",'
        '"@testing-library/react":"^14"}}'
    ),
    "frontend/tsconfig.json": "{}",
    "frontend/src/api.ts": (
        "const BASE = import.meta.env.VITE_API_BASE_URL;\n"
        'export async function getHealth() { return fetch("/api/health"); }\n'
        "export async function searchJobs(q: string) {\n"
        '  return fetch(`${BASE}/api/jobs/search`, { method: "POST", body: q });\n'
        "}\n"
    ),
    "backend/requirements.txt": "fastapi\nuvicorn\npsycopg2-binary\npytest\n",
    "backend/app/main.py": (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n\n"
        '@app.get("/api/health")\n'
        "def health():\n    return {'ok': True}\n\n"
        '@app.get("/api/jobs")\n'
        "def jobs():\n    return []\n"
    ),
    "backend/tests/test_main.py": "def test_health():\n    assert True\n",
    "README.md": _LONG_README,
    ".env.example": (
        "VITE_API_BASE_URL=http://localhost:8000\n"
        "DATABASE_URL=postgres://user:pass@localhost/db\n"
    ),
    "Dockerfile": "FROM python:3.12-slim\nCMD [\"uvicorn\", \"app.main:app\"]\n",
}

# ---------------------------------------------------------------------------
# 2. Broken configuration: missing .env template + hardcoded localhost.
# ---------------------------------------------------------------------------
REPO_BROKEN_CONFIG = {
    "backend/requirements.txt": "fastapi\nuvicorn\npytest\n",
    "backend/app/main.py": (
        "from fastapi import FastAPI\n"
        "import os\n"
        "app = FastAPI()\n"
        'SECRET = os.getenv("SECRET_TOKEN")\n'
        'BASE = os.environ["API_BASE"]\n\n'
        '@app.get("/api/ping")\n'
        "def ping():\n    return 'ok'\n"
    ),
    "backend/tests/test_ping.py": "def test_ping():\n    assert True\n",
    "src/client.py": 'API_URL = "http://localhost:8000/api"\n',
    "README.md": _LONG_README,
    "Dockerfile": "FROM python:3.12-slim\n",
    # Intentionally NO .env.example.
}

# ---------------------------------------------------------------------------
# 3. Exposed dummy secrets (all fake). Verifies detection + redaction.
# ---------------------------------------------------------------------------
REPO_SECRETS = {
    "backend/config.py": (
        'AWS_KEY = "AKIA1234567890ABCDEF"\n'
        'GITHUB_TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"\n'
        'PASSWORD = "sup3rS3cr3tValue!"\n'
        'PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----\n'
        "MIIBFAKEKEYBODYLINEONE0000\n"
        "MIIBFAKEKEYBODYLINETWO1111\n"
        '-----END PRIVATE KEY-----"""\n'
    ),
    "backend/app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
    "backend/tests/test_x.py": "def test_x():\n    assert True\n",
    "README.md": _LONG_README,
    "Dockerfile": "FROM python:3.12-slim\n",
}

# Raw secret strings that must NOT survive in stored content.
REPO_SECRETS_RAW = [
    "AKIA1234567890ABCDEF",
    "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "sup3rS3cr3tValue!",
    "MIIBFAKEKEYBODYLINEONE0000",
]

# ---------------------------------------------------------------------------
# 4. API mismatches: wrong method + missing route (plus a correct call).
# ---------------------------------------------------------------------------
REPO_API_MISMATCH = {
    "frontend/package.json": '{"dependencies":{"react":"^18","react-dom":"^18"},"devDependencies":{"vite":"^5"}}',
    "frontend/src/api.ts": (
        'export const addUser = () => fetch("/api/users", { method: "POST" });\n'
        'export const listOrders = () => fetch("/api/orders");\n'
        'export const login = () => fetch("/api/login", { method: "POST" });\n'
    ),
    "backend/requirements.txt": "fastapi\nuvicorn\n",
    "backend/app/main.py": (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n\n"
        '@app.get("/api/users")\n'
        "def users():\n    return []\n\n"
        '@app.post("/api/login")\n'
        "def login():\n    return {}\n"
    ),
    "README.md": _LONG_README,
    "backend/tests/test_users.py": "def test_users():\n    assert True\n",
    "Dockerfile": "FROM python:3.12-slim\n",
}

# ---------------------------------------------------------------------------
# 5. Bare/broken repo: invalid manifest, no README/tests/deploy.
# ---------------------------------------------------------------------------
REPO_BARE = {
    "package.json": "{ this is not valid json",
    "src/index.js": "console.log('hello');\n",
}

# ---------------------------------------------------------------------------
# 6. Flask backend with method mismatch + missing route.
# ---------------------------------------------------------------------------
REPO_FLASK = {
    "frontend/package.json": '{"dependencies":{"react":"^18","react-dom":"^18"},"devDependencies":{"vite":"^5"}}',
    "frontend/src/api.ts": (
        'export const addTask = () => fetch("/api/tasks", { method: "POST" });\n'
        'export const missing = () => fetch("/api/reports");\n'
        'export const login = () => fetch("/api/login", { method: "POST" });\n'
    ),
    "backend/requirements.txt": "flask\n",
    "backend/app.py": (
        "from flask import Flask\n"
        "app = Flask(__name__)\n\n"
        '@app.route("/api/tasks", methods=["GET"])\n'
        "def tasks():\n    return []\n\n"
        '@app.route("/api/login", methods=["POST"])\n'
        "def login():\n    return {}\n"
    ),
    "README.md": _LONG_README,
    "backend/tests/test_tasks.py": "def test_tasks():\n    assert True\n",
    "Dockerfile": "FROM python:3.12-slim\n",
}

# ---------------------------------------------------------------------------
# 7. Monorepo with conflicting dependency versions.
# ---------------------------------------------------------------------------
REPO_VERSION_CONFLICT = {
    "web/package.json": '{"dependencies":{"react":"^18.2.0"}}',
    "admin/package.json": '{"dependencies":{"react":"^17.0.2"}}',
    "README.md": _LONG_README,
    "web/tests/app.test.tsx": "test('x', () => {});\n",
    "Dockerfile": "FROM node:20\n",
}

# ---------------------------------------------------------------------------
# 8. Django + PostgreSQL backend, fully configured (clean detection baseline).
#    Exercises the Django/Python/Postgres stack path with no findings.
# ---------------------------------------------------------------------------
REPO_DJANGO = {
    "backend/requirements.txt": "django\npsycopg2-binary\npytest\n",
    "backend/manage.py": "import django\n",
    "backend/app/urls.py": (
        "from django.urls import path\n"
        "urlpatterns = [path('api/health', None)]\n"
    ),
    "backend/app/settings.py": "import django\nDEBUG = True\n",
    "backend/tests/test_app.py": "def test_app():\n    assert True\n",
    "README.md": _LONG_README,
    "Dockerfile": "FROM python:3.12-slim\n",
    ".env.example": "DATABASE_URL=postgres://user:pass@localhost/db\n",
}

# ---------------------------------------------------------------------------
# 9. React + Express (Node) + MongoDB, with one API mismatch (missing route).
#    Exercises the JS/TS backend + Mongo path and Express route parsing.
# ---------------------------------------------------------------------------
REPO_EXPRESS_MONGO = {
    "frontend/package.json": (
        '{"dependencies":{"react":"^18","react-dom":"^18"},'
        '"devDependencies":{"vite":"^5","jest":"^29"}}'
    ),
    "frontend/src/api.ts": (
        'export const listUsers = () => fetch("/api/users");\n'
        'export const addUser = () => fetch("/api/users", { method: "POST" });\n'
        'export const missing = () => fetch("/api/reports");\n'
    ),
    "backend/package.json": '{"dependencies":{"express":"^4","mongoose":"^8"}}',
    "backend/server.js": (
        "const express = require('express');\n"
        "const app = express();\n"
        "app.get('/api/users', (req, res) => res.json([]));\n"
        "app.post('/api/users', (req, res) => res.json({}));\n"
    ),
    "README.md": _LONG_README,
    "Dockerfile": "FROM node:20\n",
}

# ---------------------------------------------------------------------------
# 10. Vue 3 + Vite frontend with Vitest + Cypress declared.
#     Exercises Vue detection and JS test-framework detection.
# ---------------------------------------------------------------------------
REPO_VUE = {
    "package.json": (
        '{"dependencies":{"vue":"^3"},'
        '"devDependencies":{"vite":"^5","vitest":"^1","cypress":"^13"}}'
    ),
    "src/App.vue": "<template><div>hi</div></template>\n",
    "vite.config.ts": "export default {}\n",
    "README.md": _LONG_README,
    "Dockerfile": "FROM node:20\n",
}

# ---------------------------------------------------------------------------
# 11. Express + Prisma (PostgreSQL provider). Exercises Prisma provider mapping
#     to a concrete database in the stack detector.
# ---------------------------------------------------------------------------
REPO_PRISMA = {
    "package.json": (
        '{"dependencies":{"express":"^4","@prisma/client":"^5"},'
        '"devDependencies":{"prisma":"^5"}}'
    ),
    "prisma/schema.prisma": (
        "datasource db {\n"
        '  provider = "postgresql"\n'
        '  url = env("DATABASE_URL")\n'
        "}\n"
    ),
    "server.js": "const express = require('express');\nconst app = express();\n",
    "README.md": _LONG_README,
    "Dockerfile": "FROM node:20\n",
}

# ---------------------------------------------------------------------------
# 12. Additional dummy secret types (all fake): Stripe, Slack, Google, JWT.
#     Broadens secret-kind detection + redaction beyond REPO_SECRETS.
#
#     Each value is assembled from adjacent string fragments so no complete
#     secret-shaped literal ever appears in this source file. These are fake,
#     but they match real credential formats, so a contiguous literal would trip
#     GitHub secret scanning / push protection. Fragmenting keeps the repo clean
#     while the assembled runtime strings still exercise the detector exactly.
# ---------------------------------------------------------------------------
_FAKE_STRIPE = "sk_" "live_" "abcdefghijklmnop1234567890"
_FAKE_SLACK = "xox" "b-1234567890-abcdefghijklmnop"
_FAKE_GOOGLE = "AI" "zaSyA1234567890abcdefghijklmnopqrstuv"
_FAKE_JWT = "eyJ" "hbGciOiJIUzI1NiIs.eyJzdWIioMTIzNDU2.abcDEFghiJKLmno"

REPO_MORE_SECRETS = {
    "backend/config.py": (
        f'STRIPE = "{_FAKE_STRIPE}"\n'
        f'SLACK = "{_FAKE_SLACK}"\n'
        f'GOOGLE = "{_FAKE_GOOGLE}"\n'
        f'JWT = "{_FAKE_JWT}"\n'
    ),
    "backend/app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
    "backend/tests/test_x.py": "def test_x():\n    assert True\n",
    "README.md": _LONG_README,
    "Dockerfile": "FROM python:3.12-slim\n",
}

# Raw secret strings from REPO_MORE_SECRETS that must NOT survive in stored content.
REPO_MORE_SECRETS_RAW = [_FAKE_STRIPE, _FAKE_SLACK, _FAKE_GOOGLE, _FAKE_JWT]

# ---------------------------------------------------------------------------
# 13. The same fake secret in a production path AND a test/fixture path.
#     Verifies real-path secrets stay high-signal while fixture-path secrets are
#     down-weighted to informational (so a security tool's own test data doesn't
#     produce false "critical secret" findings).
# ---------------------------------------------------------------------------
REPO_FIXTURE_SECRETS = {
    "backend/config.py": 'AWS_KEY = "AKIA1234567890ABCDEF"\n',  # prod -> high
    "backend/tests/test_creds.py": 'FAKE_AWS = "AKIAZZZZ0000ZZZZ1111"\n',  # fixture -> info
    "README.md": _LONG_README,
}

# ---------------------------------------------------------------------------
# 14. Mock/demo and test files that hold illustrative API strings and localhost
#     URLs. A precise analyzer must NOT report these as real mismatches or
#     hardcoded-URL problems. The real frontend call (api.ts -> /api/users)
#     matches the backend, so the repo is clean.
# ---------------------------------------------------------------------------
REPO_FIXTURE_NOISE = {
    "frontend/package.json": '{"dependencies":{"react":"^18","react-dom":"^18"},"devDependencies":{"vite":"^5"}}',
    "frontend/src/api.ts": 'export const listUsers = () => fetch("/api/users");\n',
    # Demo data with a fake broken call — must be ignored.
    "frontend/src/mockData.ts": (
        "export const demoFinding = { evidence: \"client.post('/api/does-not-exist')\" };\n"
    ),
    # A test file that legitimately hardcodes localhost — must be ignored.
    "frontend/src/api.test.ts": 'const BASE = "http://localhost:8000";\nfetch(`${BASE}/api/users`);\n',
    "backend/requirements.txt": "fastapi\n",
    "backend/app/main.py": (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n\n"
        '@app.get("/api/users")\n'
        "def users():\n    return []\n"
    ),
    "README.md": _LONG_README,
    "Dockerfile": "FROM python:3.12-slim\n",
}

SAMPLE_REPOS: dict[str, dict[str, str]] = {
    "healthy_react_fastapi": REPO_HEALTHY,
    "broken_config": REPO_BROKEN_CONFIG,
    "exposed_secrets": REPO_SECRETS,
    "api_mismatch": REPO_API_MISMATCH,
    "bare_broken": REPO_BARE,
    "flask_mismatch": REPO_FLASK,
    "version_conflict": REPO_VERSION_CONFLICT,
    "django_postgres": REPO_DJANGO,
    "express_mongo": REPO_EXPRESS_MONGO,
    "vue_vite": REPO_VUE,
    "express_prisma": REPO_PRISMA,
    "more_secrets": REPO_MORE_SECRETS,
    "fixture_secrets": REPO_FIXTURE_SECRETS,
    "fixture_noise": REPO_FIXTURE_NOISE,
}

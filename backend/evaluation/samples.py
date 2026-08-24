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

SAMPLE_REPOS: dict[str, dict[str, str]] = {
    "healthy_react_fastapi": REPO_HEALTHY,
    "broken_config": REPO_BROKEN_CONFIG,
    "exposed_secrets": REPO_SECRETS,
    "api_mismatch": REPO_API_MISMATCH,
    "bare_broken": REPO_BARE,
}

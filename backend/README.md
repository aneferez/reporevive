# RepoRevive — Backend

AI-assisted repository analysis and recovery API. Built with **FastAPI** +
**Pydantic**. This service inspects public GitHub repositories and uploaded ZIP
archives, produces evidence-backed findings and a prioritized recovery roadmap,
and answers repository-grounded questions.

> **Repository code is never executed.** The backend only reads and inspects
> redacted source text within strict size and count limits.

Owner: **Claude** (backend). Frontend (React/Vite) is owned separately and
consumes the API contract in [`RepoRevive_PRD.md`](../RepoRevive_PRD.md) §11.

---

## Status

**Phases 1–4 complete.** Foundation, safe repository intake, deterministic
analyzers, and AI/retrieval are all implemented and tested.

| Endpoint | State |
| --- | --- |
| `GET /health` | ✅ live |
| `POST /api/repositories/analyze` | ✅ validates URL, fetches + analyzes public repo |
| `POST /api/repositories/upload` | ✅ safe ZIP extraction + analysis |
| `GET /api/analysis/{id}` | ✅ status/summary + stage/progress + errors |
| `GET /api/analysis/{id}/architecture` | ✅ component/connection graph with evidence |
| `GET /api/analysis/{id}/findings` | ✅ evidence-backed findings, sorted by severity |
| `GET /api/analysis/{id}/roadmap` | ✅ prioritized recovery tasks |
| `POST /api/analysis/{id}/chat` | ✅ retrieval-grounded, cited (AI optional) |
| `GET /api/analysis/{id}/report` | ✅ full report bundle |
| `DELETE /api/analysis/{id}` | ✅ deletes stored analysis |

Analyzers implemented: stack detection (FR-03), architecture (FR-04),
configuration inspection (FR-05), API-contract comparison (FR-06), masked secret
detection (FR-07), tests/docs assessment (FR-08), evidence-backed findings
(FR-09), recovery roadmap (FR-10), and grounded chat (FR-11).

---

## Local setup

Requires Python 3.11+ (tested on 3.14).

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# Git Bash:            source .venv/Scripts/activate
pip install -r requirements-dev.txt
```

Copy the environment template and adjust as needed:

```bash
cp .env.example .env
```

Run the API:

```bash
uvicorn app.main:app --reload --port 8000
```

- Health check: <http://localhost:8000/health>
- Interactive OpenAPI docs: <http://localhost:8000/docs>

### Optional: enable the AI layer (Gemini)

The backend runs fully in **deterministic-only mode** without a key. To enable
grounded AI narration later:

```bash
pip install -r requirements-ai.txt
# then set GEMINI_API_KEY and GEMINI_MODEL in .env
```

---

## Testing

```bash
pytest
```

## Evaluation

A benchmark harness runs 13 synthetic sample repositories through the real
pipeline and checks **68 intentionally-introduced scenarios**, then reports
metrics:

```bash
python -m evaluation.run_eval
```

Current outcome: **68/68 (100%)**. Coverage by group:

| Group | Checks | What it verifies |
| --- | --- | --- |
| `stack` | 18 | Detection of React, Vue, Vite, TypeScript, FastAPI, Flask, Django, Express/Node, Prisma, and the Postgres/MongoDB/Pytest/Vitest/Jest/Cypress signals |
| `precision` | 8 | A healthy repo raises no false findings, and secrets in test/fixture/sample paths are down-weighted to informational (not false criticals) |
| `findings` | 22 | API mismatches (method + missing route), config gaps, dependency conflicts, and 8 secret kinds (AWS, GitHub, Google, Slack, Stripe, private key, JWT, generic) |
| `redaction` | 2 | Raw secret values never survive in stored content |
| `roadmap` | 7 | Findings map to the right recovery buckets in priority order, and informational findings never create tasks (FR-10) |
| `architecture` | 5 | Component/connection graph with the PRD `persistence` taxonomy and no phantom nodes (FR-04) |
| `intake` | 3 | Unsupported URLs, oversized archives, and path traversal are rejected |
| `chat` | 3 | Insufficient-evidence honesty, structured AI-failure errors, and cited answers on the offline path (FR-11) |

Results are written to `evaluation/results/latest.json`. The same checks run in
CI via `tests/test_evaluation.py`, which enforces a ≥25-scenario floor (PRD
§17 / DoD #9) and a 100% pass rate.

## Deployment

The service is stateless (in-memory store) and reads all configuration from
environment variables. Provided configs:

- **Docker**: `docker build -t reporevive-backend . && docker run -p 8000:8000 --env-file .env reporevive-backend`
- **Render**: Blueprint at the repo root ([`../render.yaml`](../render.yaml)) — the
  Docker/build already installs the AI deps.
- **Procfile**: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT` for
  Procfile-based platforms.

Set `FRONTEND_ORIGIN` to the deployed frontend origin(s) so CORS allows it. See
the full step-by-step in [`../DEPLOY.md`](../DEPLOY.md).

---

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | Runtime mode; controls log verbosity. |
| `PORT` | `8000` | Server port. |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Comma-separated CORS allowlist. |
| `GEMINI_API_KEY` | _(empty)_ | Server-side Gemini key. Empty → deterministic-only. |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Configurable model id. |
| `EMBEDDING_MODEL` | `text-embedding-004` | Embedding model for embeddings retrieval. |
| `RETRIEVAL_MODE` | `lexical` | `lexical` \| `embeddings` \| `pgvector` \| `auto`. |
| `GITHUB_TOKEN` | _(empty)_ | Optional; public repos only, raises rate limit. |
| `DATABASE_URL` | _(empty)_ | Optional persistence (Supabase/Postgres). |
| `MAX_ARCHIVE_BYTES` | `10485760` | Max compressed upload (10 MB). |
| `MAX_ARCHIVE_ENTRIES` | `10000` | Max ZIP/TAR metadata entries. |
| `MAX_EXTRACTED_BYTES` | `52428800` | Max extracted total (50 MB). |
| `MAX_ANALYZED_FILES` | `1000` | Max inspected files. |
| `MAX_FILE_BYTES` | `262144` | Max per-file text size (256 KB). |
| `MAX_AI_FILES` | `100` | Max files sent to AI per analysis. |
| `MAX_STORED_ANALYSES` | `100` | In-memory retention cap. |
| `ANALYSIS_TTL_SECONDS` | `0` | Time-based retention; `0` disables TTL expiry. |
| `RATE_LIMIT_ENABLED` | `true` | Per-client limits on POST endpoints. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate-limit window. |
| `RATE_LIMIT_ANALYSIS_START_MAX` | `10` | analyze+upload per window, per client. |
| `RATE_LIMIT_CHAT_MAX` | `30` | chat questions per window, per client. |
| `TRUSTED_PROXY_HOPS` | `0` | Trusted proxy hops for client-IP rate limiting. |
| `REQUIRE_OWNER_TOKEN` | `false` | Require `X-Owner-Token` on analysis-scoped endpoints. |

Never commit real secrets. `.env.example` holds placeholders only.

---

## Project layout

```text
backend/
├── app/
│   ├── main.py              # FastAPI app: CORS, middleware, routers
│   ├── config.py            # env-driven settings
│   ├── logging_config.py    # redaction-aware logging setup
│   ├── models/              # Pydantic schemas + enums (API contract)
│   ├── api/
│   │   ├── errors.py        # error codes + exception handlers
│   │   ├── middleware.py    # request id + timing
│   │   ├── deps.py          # shared dependencies
│   │   └── routes/          # health, repositories, analysis
│   ├── core/                # records, in-memory store, analysis pipeline
│   ├── intake/              # GitHub URL validation, ZIP extraction (phase 2)
│   ├── analyzers/           # deterministic inspectors (phase 3)
│   ├── retrieval/           # lexical search (phase 4)
│   └── ai/                  # Gemini provider, grounded findings, chat
└── tests/                   # pytest suite
```

## Safety guarantees

- No execution of analyzed repository code, install hooks, or shell commands.
- Only valid public `github.com/{owner}/{repo}` URLs are fetched (SSRF guard).
- Archive path-traversal / symlink rejection and size/count limits.
- Suspected secrets are redacted before storage, logging, AI calls, or responses.
- Per-client rate limiting on POST endpoints (analyze/upload/chat); GET polling is exempt.
- Uncertain findings are marked explicitly; inference is never shown as fact.

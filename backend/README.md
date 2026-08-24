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

A benchmark harness runs 5 synthetic sample repositories through the real
pipeline and checks 29 intentionally-introduced scenarios (stack detection,
precision/false-positives, config, API mismatches, secrets + redaction, intake
safety, and chat behavior), then reports metrics:

```bash
python -m evaluation.run_eval
```

Results are written to `evaluation/results/latest.json`. The same checks run in
CI via `tests/test_evaluation.py` and must stay at 100%.

## Deployment

The service is stateless (in-memory store) and reads all configuration from
environment variables. Provided configs:

- **Docker**: `docker build -t reporevive-backend . && docker run -p 8000:8000 --env-file .env reporevive-backend`
- **Render**: `render.yaml` blueprint (free plan, `healthCheckPath: /health`).
- **Procfile**: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT` for
  Procfile-based platforms.

Set `FRONTEND_ORIGIN` to the deployed frontend origin(s) so CORS allows it.

---

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | Runtime mode; controls log verbosity. |
| `PORT` | `8000` | Server port. |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Comma-separated CORS allowlist. |
| `GEMINI_API_KEY` | _(empty)_ | Server-side Gemini key. Empty → deterministic-only. |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Configurable model id. |
| `GITHUB_TOKEN` | _(empty)_ | Optional; public repos only, raises rate limit. |
| `DATABASE_URL` | _(empty)_ | Optional persistence (Supabase/Postgres). |
| `MAX_ARCHIVE_BYTES` | `10485760` | Max compressed upload (10 MB). |
| `MAX_EXTRACTED_BYTES` | `52428800` | Max extracted total (50 MB). |
| `MAX_ANALYZED_FILES` | `1000` | Max inspected files. |
| `MAX_FILE_BYTES` | `262144` | Max per-file text size (256 KB). |
| `MAX_AI_FILES` | `100` | Max files sent to AI per analysis. |
| `MAX_STORED_ANALYSES` | `100` | In-memory retention cap. |

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
- Uncertain findings are marked explicitly; inference is never shown as fact.

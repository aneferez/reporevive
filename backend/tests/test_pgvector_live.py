"""Live pgvector integration test.

Runs the real PgVectorRetriever (build -> search -> cleanup) against a real
Postgres+pgvector database. SKIPPED unless DATABASE_URL is configured, so the
normal suite stays offline. Uses a deterministic embedder and an isolated test
table (dropped afterward), so it needs no AI key and never touches the real
``reporevive_chunks`` table or any other data.

Enable by setting DATABASE_URL (e.g. a Supabase connection string) in the
environment or backend/.env, then run:  pytest tests/test_pgvector_live.py
"""

from __future__ import annotations

import pytest

psycopg = pytest.importorskip("psycopg")
pytest.importorskip("pgvector.psycopg")

from app.config import Settings
from app.retrieval.pgvector import PgVectorRetriever

from .helpers import make_files

_SETTINGS = Settings()  # reads DATABASE_URL from env/.env
_TEST_TABLE = "reporevive_livetest"

pytestmark = pytest.mark.skipif(
    not _SETTINGS.database_url,
    reason="DATABASE_URL not configured; skipping live pgvector test",
)


class _VocabEmbedder:
    VOCAB = ["auth", "login", "widget", "render", "dashboard", "user", "token", "config"]

    def available(self) -> bool:
        return True

    def embed(self, texts, *, task_type=None):
        return [[float(t.lower().count(w)) for w in self.VOCAB] for t in texts]


@pytest.fixture()
def drop_test_table():
    yield
    try:
        with psycopg.connect(_SETTINGS.database_url) as conn:
            conn.execute(f"DROP TABLE IF EXISTS {_TEST_TABLE}")
            conn.commit()
    except Exception:  # noqa: BLE001 - best-effort teardown
        pass


def test_pgvector_live_build_search_cleanup(drop_test_table):
    files = make_files(
        {
            "src/widget.py": "def render_widget():\n    # renders the dashboard widget\n",
            "src/auth.py": "def login():\n    # user auth and login token\n",
        }
    )
    retr = PgVectorRetriever.build(files, _VocabEmbedder(), _SETTINGS, table=_TEST_TABLE)
    assert retr.size >= 2

    # Semantic-ish match: the widget file ranks first for a widget query.
    hits = retr.search("widget render dashboard")
    assert hits, "expected retrieval hits from the live database"
    assert hits[0].file == "src/widget.py"

    # Retention: cleanup removes this analysis's rows.
    retr.cleanup()
    assert retr.search("widget render dashboard") == []

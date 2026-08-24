from __future__ import annotations

from http import HTTPStatus

from app.ai.provider import AIProviderError

from .helpers import make_zip

_REPO = {
    "README.md": b"# Widget App\n\nRenders dashboard widgets.\n",
    "src/widget.py": b"def render_widget():\n    # renders the dashboard widget component\n    return True\n",
}


def _analyze(client) -> str:
    resp = client.post(
        "/api/repositories/upload",
        files={"file": ("app.zip", make_zip(_REPO), "application/zip")},
    )
    assert resp.status_code == 202
    return resp.json()["analysis_id"]


def test_chat_extractive_answer_with_citations(client):
    analysis_id = _analyze(client)
    resp = client.post(
        f"/api/analysis/{analysis_id}/chat",
        json={"question": "how does widget rendering work?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["insufficient_evidence"] is False
    assert body["citations"]
    assert any("widget" in c["file"] for c in body["citations"])


def test_chat_insufficient_evidence(client):
    analysis_id = _analyze(client)
    resp = client.post(
        f"/api/analysis/{analysis_id}/chat",
        json={"question": "quokka platypus xylophone zeppelin"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["insufficient_evidence"] is True
    assert body["citations"] == []


def test_context_block_respects_char_cap():
    from app.ai.grounding import build_context_block
    from app.retrieval.base import SearchHit

    hits = [
        SearchHit(file=f"f{i}.py", start_line=1, end_line=40, text="x" * 500, score=1.0)
        for i in range(20)
    ]
    ctx = build_context_block(hits, max_chars=1000, max_files=100)
    assert len(ctx) <= 1000 + 100  # bounded (tiny separator overhead allowed)


def test_context_block_respects_file_cap():
    from app.ai.grounding import build_context_block
    from app.retrieval.base import SearchHit

    hits = [
        SearchHit(file=f"f{i}.py", start_line=1, end_line=5, text="hello world", score=1.0)
        for i in range(10)
    ]
    ctx = build_context_block(hits, max_chars=100000, max_files=3)
    files = {ln[1:].split(":")[0] for ln in ctx.splitlines() if ln.startswith("[")}
    assert len(files) <= 3


def _fake_provider(generate):
    class _P:
        def available(self):
            return True

        def generate(self, *, system, prompt, max_output_tokens=1024):
            return generate(system=system, prompt=prompt)

    return _P()


def test_chat_uses_ai_when_available(client, monkeypatch):
    analysis_id = _analyze(client)

    def gen(system, prompt):
        return "The widget is rendered by render_widget in [src/widget.py:1]."

    monkeypatch.setattr("app.ai.chat.get_provider", lambda settings: _fake_provider(gen))
    resp = client.post(
        f"/api/analysis/{analysis_id}/chat",
        json={"question": "how does widget rendering work?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "render_widget" in body["answer"]
    assert body["insufficient_evidence"] is False
    assert body["confidence"] > 0.5
    assert body["citations"]


def test_chat_ai_failure_returns_structured_error(client, monkeypatch):
    analysis_id = _analyze(client)

    def gen(system, prompt):
        raise AIProviderError("AI_QUOTA_EXCEEDED", "quota exceeded", HTTPStatus.TOO_MANY_REQUESTS)

    monkeypatch.setattr("app.ai.chat.get_provider", lambda settings: _fake_provider(gen))
    resp = client.post(
        f"/api/analysis/{analysis_id}/chat",
        json={"question": "how does widget rendering work?"},
    )
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "AI_QUOTA_EXCEEDED"

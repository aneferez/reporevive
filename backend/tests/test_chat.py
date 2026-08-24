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

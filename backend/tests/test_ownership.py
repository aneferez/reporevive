from __future__ import annotations

import app.api.deps as deps
from app.config import Settings
from app.security.ownership import hash_owner_token, new_owner_token, verify_owner_token

from .helpers import make_zip


def _enable(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: Settings(require_owner_token=True))


def _start(client) -> dict:
    resp = client.post(
        "/api/repositories/upload",
        files={"file": ("demo.zip", make_zip({"README.md": b"# demo\n"}), "application/zip")},
    )
    assert resp.status_code == 202
    return resp.json()


def test_token_helpers_roundtrip():
    token = new_owner_token()
    assert len(token) > 20
    assert verify_owner_token(token, hash_owner_token(token))
    assert not verify_owner_token("wrong", hash_owner_token(token))
    assert not verify_owner_token("", "")


def test_owner_token_returned_on_creation(client):
    body = _start(client)
    assert body["owner_token"]


def test_no_token_required_by_default(client):
    # Default config leaves enforcement off — existing clients keep working.
    aid = _start(client)["analysis_id"]
    assert client.get(f"/api/analysis/{aid}").status_code == 200
    assert client.delete(f"/api/analysis/{aid}").status_code == 200


def test_enforced_access_requires_correct_token(client, monkeypatch):
    body = _start(client)
    aid, token = body["analysis_id"], body["owner_token"]
    _enable(monkeypatch)

    # Missing token -> 403
    r = client.get(f"/api/analysis/{aid}")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "OWNER_TOKEN_INVALID"

    # Wrong token -> 403
    assert client.get(f"/api/analysis/{aid}", headers={"X-Owner-Token": "nope"}).status_code == 403

    # Correct token -> 200 across scoped endpoints
    hdr = {"X-Owner-Token": token}
    assert client.get(f"/api/analysis/{aid}", headers=hdr).status_code == 200
    assert client.get(f"/api/analysis/{aid}/findings", headers=hdr).status_code == 200


def test_enforced_delete_requires_token(client, monkeypatch):
    body = _start(client)
    aid, token = body["analysis_id"], body["owner_token"]
    _enable(monkeypatch)

    assert client.delete(f"/api/analysis/{aid}").status_code == 403
    assert client.delete(f"/api/analysis/{aid}", headers={"X-Owner-Token": token}).status_code == 200


def test_owner_token_isolates_across_analyses(client, monkeypatch):
    # The core isolation guarantee: a *valid* token for one analysis must not
    # grant access to a different analysis.
    a = _start(client)
    b = _start(client)
    aid, atok = a["analysis_id"], a["owner_token"]
    bid, btok = b["analysis_id"], b["owner_token"]
    assert atok != btok
    _enable(monkeypatch)

    # Each token unlocks only its own analysis.
    assert client.get(f"/api/analysis/{aid}", headers={"X-Owner-Token": atok}).status_code == 200
    assert client.get(f"/api/analysis/{bid}", headers={"X-Owner-Token": btok}).status_code == 200
    # Cross-use is rejected in both directions.
    assert client.get(f"/api/analysis/{aid}", headers={"X-Owner-Token": btok}).status_code == 403
    assert client.get(f"/api/analysis/{bid}", headers={"X-Owner-Token": atok}).status_code == 403


def test_enforced_on_every_scoped_endpoint(client, monkeypatch):
    body = _start(client)
    aid, token = body["analysis_id"], body["owner_token"]
    _enable(monkeypatch)
    hdr = {"X-Owner-Token": token}

    # Scoped GETs: 403 without a token, 200 with the right one.
    for path in (
        f"/api/analysis/{aid}/architecture",
        f"/api/analysis/{aid}/roadmap",
        f"/api/analysis/{aid}/report",
    ):
        assert client.get(path).status_code == 403, path
        assert client.get(path, headers=hdr).status_code == 200, path

    # Chat is a scoped POST and must be guarded too.
    chat = f"/api/analysis/{aid}/chat"
    question = {"question": "what does this project do"}
    assert client.post(chat, json=question).status_code == 403
    assert client.post(chat, json=question, headers=hdr).status_code == 200


def test_owner_token_not_echoed_on_reads(client, monkeypatch):
    # The secret is returned once at creation; it must never come back on reads.
    body = _start(client)
    aid, token = body["analysis_id"], body["owner_token"]
    _enable(monkeypatch)
    hdr = {"X-Owner-Token": token}

    status = client.get(f"/api/analysis/{aid}", headers=hdr)
    assert "owner_token" not in status.json()
    assert token not in status.text

    report = client.get(f"/api/analysis/{aid}/report", headers=hdr)
    assert "owner_token" not in report.json()
    assert token not in report.text

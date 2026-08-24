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

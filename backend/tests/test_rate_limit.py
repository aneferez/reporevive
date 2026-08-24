from __future__ import annotations

from app.api.ratelimit import RateLimiter

from .helpers import make_zip


def test_limiter_allows_up_to_limit_then_blocks():
    limiter = RateLimiter()
    key = "chat:1.2.3.4"
    for _ in range(3):
        allowed, retry = limiter.hit(key, limit=3, window_s=60)
        assert allowed is True
        assert retry == 0
    allowed, retry = limiter.hit(key, limit=3, window_s=60)
    assert allowed is False
    assert retry >= 1


def test_limiter_separate_keys_independent():
    limiter = RateLimiter()
    assert limiter.hit("a", 1, 60)[0] is True
    assert limiter.hit("a", 1, 60)[0] is False
    # Different key unaffected.
    assert limiter.hit("b", 1, 60)[0] is True


def test_analysis_start_endpoint_is_rate_limited(client):
    # Default analysis_start limit is 10 per window.
    zip_bytes = make_zip({"README.md": b"# demo\n"})
    last = None
    for _ in range(11):
        last = client.post(
            "/api/repositories/upload",
            files={"file": ("demo.zip", zip_bytes, "application/zip")},
        )
    assert last.status_code == 429
    body = last.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert last.headers.get("Retry-After")


def test_status_polling_is_not_rate_limited(client):
    # GET status must remain pollable without tripping limits.
    aid = client.post(
        "/api/repositories/upload",
        files={"file": ("demo.zip", make_zip({"README.md": b"# demo\n"}), "application/zip")},
    ).json()["analysis_id"]
    for _ in range(30):
        assert client.get(f"/api/analysis/{aid}").status_code == 200

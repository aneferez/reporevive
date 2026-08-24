"""Shared pytest fixtures."""

from __future__ import annotations

import os

# Force deterministic, offline behavior in tests regardless of any local .env:
# an OS env var overrides the .env file in pydantic-settings. Must run before
# app modules read settings (app.main builds the app at import time).
os.environ["GEMINI_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from app.api.ratelimit import reset_limiter
from app.config import get_settings
from app.core.store import reset_store
from app.main import create_app

from .helpers import make_tar_gz

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _isolate_state():
    # Store and rate limiter are process-wide singletons; reset around each test.
    reset_store()
    reset_limiter()
    yield
    reset_store()
    reset_limiter()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Keep GitHub-source analyses offline and deterministic in tests.

    Replaces the tarball fetch with a small in-memory repository so no test
    reaches out to the network. Tests that need specific fetch behavior can
    monkeypatch again or call the status mapper directly.
    """

    def fake_fetch(ref, settings):
        return make_tar_gz(
            {
                "README.md": b"# demo\n\nA small demo repository.\n",
                "src/main.py": b"print('hello world')\n",
                "package.json": b'{"name": "demo", "version": "1.0.0"}\n',
            }
        )

    monkeypatch.setattr("app.intake.service.fetch_repo_tarball", fake_fetch)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())

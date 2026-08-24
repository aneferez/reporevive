"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.store import reset_store
from app.main import create_app

from .helpers import make_tar_gz


@pytest.fixture(autouse=True)
def _isolate_store():
    # The store is a process-wide singleton; reset it around each test.
    reset_store()
    yield
    reset_store()


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

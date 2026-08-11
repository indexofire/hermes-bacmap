"""Security tests for web/app.py API-key authentication boundary.

BACMAP_API_KEY env var gates enforcement:
- unset  → all endpoints open (backward compatible, localhost default)
- set    → every request must carry matching X-API-Key header
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setenv("BACMAP_API_KEY", "test-secret-key")
    monkeypatch.chdir(_PROJECT_ROOT)
    import importlib

    from fastapi.testclient import TestClient

    import web.app as app_module

    importlib.reload(app_module)
    with TestClient(app_module.app) as client:
        yield client


@pytest.fixture
def open_client(monkeypatch):
    monkeypatch.delenv("BACMAP_API_KEY", raising=False)
    monkeypatch.chdir(_PROJECT_ROOT)
    import importlib

    from fastapi.testclient import TestClient

    import web.app as app_module

    importlib.reload(app_module)
    with TestClient(app_module.app) as client:
        yield client


class TestApiKeyEnforcement:
    def test_missing_header_returns_401_when_key_set(self, app_client):
        r = app_client.get("/api/status")
        assert r.status_code == 401
        assert "X-API-Key" in r.json()["detail"]

    def test_wrong_header_returns_401(self, app_client):
        r = app_client.get("/api/status", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401

    def test_correct_header_passes(self, app_client):
        r = app_client.get("/api/status", headers={"X-API-Key": "test-secret-key"})
        assert r.status_code == 200

    def test_endpoints_open_when_key_unset(self, open_client):
        r = open_client.get("/api/status")
        assert r.status_code == 200


class TestApiKeyDependencyDirect:
    """Unit-test the dependency function in isolation (no HTTP layer)."""

    def test_returns_none_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("BACMAP_API_KEY", raising=False)
        import importlib

        import web.app as app_module

        importlib.reload(app_module)
        assert app_module._require_api_key(None) is None

    def test_raises_when_env_set_and_header_missing(self, monkeypatch):
        monkeypatch.setenv("BACMAP_API_KEY", "s3cret")
        import importlib

        import web.app as app_module

        importlib.reload(app_module)
        with pytest.raises(Exception) as exc:
            app_module._require_api_key(None)
        assert exc.value.status_code == 401

    def test_returns_key_when_match(self, monkeypatch):
        monkeypatch.setenv("BACMAP_API_KEY", "s3cret")
        import importlib

        import web.app as app_module

        importlib.reload(app_module)
        assert app_module._require_api_key("s3cret") == "s3cret"

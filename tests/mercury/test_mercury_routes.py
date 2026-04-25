from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mercury_cli.mercury_routes import TailscaleIdentityMiddleware, mercury_router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(mercury_router)
    app.add_middleware(TailscaleIdentityMiddleware)
    return TestClient(app)


def test_brains_endpoint_returns_full_catalog(client: TestClient):
    resp = client.get("/api/mercury/brains")
    assert resp.status_code == 200
    body = resp.json()

    catalog = body["catalog"]
    assert {m["model_id"] for m in catalog["zero_premium"]} == {"gpt-5-mini", "gpt-4o", "gpt-4.1"}
    for m in catalog["zero_premium"]:
        assert m["multiplier"] == 0
        assert m["provider"] == "copilot"

    assert {m["model_id"] for m in catalog["part_time"]} == {"gemma4:e4b"}
    assert all(m["multiplier"] >= 1 for m in catalog["escalation"])


def test_brains_endpoint_includes_defaults(client: TestClient):
    body = client.get("/api/mercury/brains").json()
    assert body["defaults"]["fulltime"]["model_id"] == "gpt-5-mini"
    assert body["defaults"]["vision"]["supports_vision"] is True
    assert body["defaults"]["part_time"]["provider"] == "ollama"


def test_brains_endpoint_includes_cortex_and_tailscale(client: TestClient):
    body = client.get("/api/mercury/brains").json()
    assert "cortex" in body
    assert "state" in body["cortex"]
    assert "vram" in body["cortex"]
    assert "tailscale" in body
    assert "running" in body["tailscale"]


def test_cortex_state_endpoint(client: TestClient):
    resp = client.get("/api/mercury/cortex/state")
    assert resp.status_code == 200
    body = resp.json()
    assert "available" in body
    assert "state" in body
    assert "tribe_running" in body


def test_tailscale_endpoint(client: TestClient):
    resp = client.get("/api/mercury/tailscale")
    assert resp.status_code == 200
    body = resp.json()
    assert "installed" in body
    assert "running" in body
    assert "magic_dns" in body


def test_tailscale_middleware_attaches_identity(client: TestClient):
    headers = {
        "Tailscale-User-Login": "alice@example.com",
        "Tailscale-User-Name": "Alice",
        "Tailscale-User-Profile-Pic": "https://avatar/x.png",
    }
    body = client.get("/api/mercury/tailscale", headers=headers).json()
    identity = body["identity"]
    assert identity is not None
    assert identity["login"] == "alice@example.com"
    assert identity["name"] == "Alice"
    assert identity["profile_picture"] == "https://avatar/x.png"


def test_tailscale_middleware_no_headers_yields_null_identity(client: TestClient):
    body = client.get("/api/mercury/tailscale").json()
    assert body["identity"] is None


def test_brains_endpoint_surfaces_identity_when_present(client: TestClient):
    headers = {"Tailscale-User-Login": "bob@example.com"}
    body = client.get("/api/mercury/brains", headers=headers).json()
    assert body["identity"] is not None
    assert body["identity"]["login"] == "bob@example.com"
    # name falls back to login when missing
    assert body["identity"]["name"] == "bob@example.com"


def test_brains_cortex_unavailable_degrades_cleanly(client: TestClient):
    with patch("mercury.cortex_bridge.cortex_available", return_value=False):
        body = client.get("/api/mercury/brains").json()
    assert body["cortex"]["available"] is False
    assert body["cortex"]["state"] == "unavailable"

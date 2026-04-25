"""Provider discovery + model-test endpoint tests.

No real providers are reachable in the test environment, so we assert that the
endpoints return a well-shaped response that lists every provider with ok=False
and a non-empty error, rather than 500ing.
"""
from __future__ import annotations


def _register(client, email: str, password: str = "s3cretpass!"):
    client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )


def _token(client, email: str, password: str = "s3cretpass!") -> str:
    return client.post(
        "/api/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]


def _bearer(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def _workspace(client, tok: str) -> str:
    return client.post(
        "/api/workspaces",
        headers=_bearer(tok),
        json={"name": "Acme", "slug": "acme", "description": ""},
    ).json()["id"]


def test_list_models_shape(client) -> None:
    _register(client, "owner@example.com")
    tok = _token(client, "owner@example.com")
    r = client.get("/api/providers/models", headers=_bearer(tok))
    assert r.status_code == 200
    body = r.json()
    assert "providers" in body
    assert "all_models" in body
    names = {p["provider"] for p in body["providers"]}
    # Every provider we probe in services/providers.discover_all must show up.
    assert names == {"ollama", "lmstudio", "openai", "openrouter", "anthropic"}
    for p in body["providers"]:
        assert set(p.keys()) == {"provider", "ok", "models", "error"}


def test_test_model_requires_model_field(client) -> None:
    _register(client, "owner@example.com")
    tok = _token(client, "owner@example.com")
    ws_id = _workspace(client, tok)
    r = client.post(
        "/api/providers/test-model",
        headers=_bearer(tok),
        params={"workspace_id": ws_id},
        json={},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": False, "error": "model required"}


def test_test_model_returns_failure_when_litellm_offline(client) -> None:
    _register(client, "owner@example.com")
    tok = _token(client, "owner@example.com")
    ws_id = _workspace(client, tok)
    r = client.post(
        "/api/providers/test-model",
        headers=_bearer(tok),
        params={"workspace_id": ws_id},
        json={"model": "openai/gpt-4o-mini", "prompt": "ping"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert isinstance(body["latency_ms"], int)
    assert body["error"]


def test_providers_requires_auth(client) -> None:
    assert client.get("/api/providers/models").status_code == 401

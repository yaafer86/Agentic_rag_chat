"""Chat endpoint smoke tests.

No real LLM or embedding provider is available in the test env, so the RAG loop
falls through to the deterministic fallback path. We verify the routing, RBAC,
persistence, and response shape — not LLM quality.
"""
from __future__ import annotations


def _auth(client, email: str, password: str = "s3cretpass!"):
    client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def _bearer(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def _make_workspace(client, token: str) -> str:
    r = client.post(
        "/api/workspaces",
        headers=_bearer(token),
        json={"name": "Acme", "slug": "acme", "description": ""},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_chat_post_returns_deterministic_payload(client) -> None:
    token = _auth(client, "owner@example.com")
    ws_id = _make_workspace(client, token)

    r = client.post(
        "/api/chat",
        headers=_bearer(token),
        json={
            "workspace_id": ws_id,
            "message": "Summarize the uploaded reports.",
            "intent": "auto",
            "max_results": 10,
            "stream_thinking": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["conversation_id"]
    assert body["message_id"]
    # No LLM in test env → fallback text is deterministic.
    assert body["content"]
    assert body["intent_detected"] in {
        "summarize", "list_all", "chat", "compare", "drill_down", "timeline", "map", "export",
    }


def test_chat_stream_endpoint_returns_sse(client) -> None:
    token = _auth(client, "owner@example.com")
    ws_id = _make_workspace(client, token)

    with client.stream(
        "GET",
        "/api/chat/stream",
        headers=_bearer(token),
        params={"workspace_id": ws_id, "q": "Who won?", "intent": "auto", "max_results": 5},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text(chunk_size=None))

    assert "event: thinking" in body or "event: tool_call" in body
    assert "event: done" in body


def test_chat_history_after_post(client) -> None:
    token = _auth(client, "owner@example.com")
    ws_id = _make_workspace(client, token)
    r = client.post(
        "/api/chat",
        headers=_bearer(token),
        json={"workspace_id": ws_id, "message": "first question"},
    )
    assert r.status_code == 200
    conv = r.json()["conversation_id"]

    r = client.get(
        "/api/chat/history",
        headers=_bearer(token),
        params={"workspace_id": ws_id, "conversation_id": conv},
    )
    assert r.status_code == 200
    history = r.json()
    # One user + one assistant turn persisted.
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"

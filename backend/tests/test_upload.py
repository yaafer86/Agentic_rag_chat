"""Upload endpoint tests. Pipeline is skipped so no MinIO/Qdrant/LLM calls are needed."""
from __future__ import annotations

import io


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


def test_upload_and_list(client) -> None:
    token = _auth(client, "owner@example.com")
    ws_id = _make_workspace(client, token)

    r = client.post(
        "/api/upload",
        headers=_bearer(token),
        params={"workspace_id": ws_id},
        files={"file": ("notes.txt", io.BytesIO(b"hello world"), "text/plain")},
        data={"skip_pipeline": "true"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["filename"] == "notes.txt"
    assert body["size_bytes"] == len(b"hello world")
    assert body["status"] == "pending"

    # Listing returns the doc.
    r = client.get("/api/upload", headers=_bearer(token), params={"workspace_id": ws_id})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_upload_requires_membership(client) -> None:
    owner = _auth(client, "owner@example.com")
    ws_id = _make_workspace(client, owner)
    outsider = _auth(client, "outsider@example.com")

    r = client.post(
        "/api/upload",
        headers=_bearer(outsider),
        params={"workspace_id": ws_id},
        files={"file": ("notes.txt", io.BytesIO(b"hi"), "text/plain")},
        data={"skip_pipeline": "true"},
    )
    assert r.status_code == 403


def test_upload_rejects_empty(client) -> None:
    token = _auth(client, "owner@example.com")
    ws_id = _make_workspace(client, token)
    r = client.post(
        "/api/upload",
        headers=_bearer(token),
        params={"workspace_id": ws_id},
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        data={"skip_pipeline": "true"},
    )
    assert r.status_code == 400


def test_quota_enforced(client) -> None:
    """Upload succeeds until quota is reached, then is rejected with 402."""
    token = _auth(client, "owner@example.com")
    ws_id = _make_workspace(client, token)

    # Shrink quota via direct DB write (no API for this yet).
    import asyncio

    from sqlalchemy import update

    from app.core.db import SessionLocal
    from app.models.db import Workspace

    async def _shrink():
        async with SessionLocal() as db:
            await db.execute(update(Workspace).where(Workspace.id == ws_id).values(quota_bytes=5))
            await db.commit()

    asyncio.get_event_loop().run_until_complete(_shrink())

    r = client.post(
        "/api/upload",
        headers=_bearer(token),
        params={"workspace_id": ws_id},
        files={"file": ("big.txt", io.BytesIO(b"way too many bytes to fit"), "text/plain")},
        data={"skip_pipeline": "true"},
    )
    assert r.status_code == 402

"""Workspace + RBAC tests."""
from __future__ import annotations


def _auth(client, email: str):
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "s3cretpass!", "display_name": email.split("@")[0]},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "s3cretpass!"})
    r.raise_for_status()
    return r.json()["access_token"]


def _bearer(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def test_workspace_lifecycle_and_rbac(client) -> None:
    admin = _auth(client, "owner@example.com")
    editor = _auth(client, "editor@example.com")
    outsider = _auth(client, "outsider@example.com")

    # Create workspace as owner.
    r = client.post(
        "/api/workspaces",
        headers=_bearer(admin),
        json={"name": "Acme", "slug": "acme", "description": "test"},
    )
    assert r.status_code == 201, r.text
    ws_id = r.json()["id"]

    # Duplicate slug rejected.
    r = client.post(
        "/api/workspaces",
        headers=_bearer(admin),
        json={"name": "Acme2", "slug": "acme", "description": ""},
    )
    assert r.status_code == 409

    # Outsider cannot see.
    r = client.get(f"/api/workspaces/{ws_id}", headers=_bearer(outsider))
    assert r.status_code == 403

    # Owner can list own.
    r = client.get("/api/workspaces", headers=_bearer(admin))
    assert r.status_code == 200
    assert any(w["id"] == ws_id for w in r.json())

    # Invite editor.
    # First resolve editor's user id via admin listing.
    r = client.get("/api/workspaces/_admin/users", headers=_bearer(admin))
    assert r.status_code == 200
    editor_id = next(u["id"] for u in r.json() if u["email"] == "editor@example.com")

    r = client.post(
        f"/api/workspaces/{ws_id}/members",
        headers=_bearer(admin),
        json={"user_id": editor_id, "role": "workspace_editor"},
    )
    assert r.status_code == 201

    # Editor can now fetch workspace.
    r = client.get(f"/api/workspaces/{ws_id}", headers=_bearer(editor))
    assert r.status_code == 200

    # Editor cannot set model_prefs (admin-only).
    r = client.put(
        f"/api/workspaces/{ws_id}/model-prefs",
        headers=_bearer(editor),
        json={"rag_model": "foo/bar"},
    )
    assert r.status_code == 403

    # Admin can.
    r = client.put(
        f"/api/workspaces/{ws_id}/model-prefs",
        headers=_bearer(admin),
        json={"rag_model": "openai/gpt-4o-mini", "temperature": 0.1},
    )
    assert r.status_code == 200
    assert r.json()["model_prefs"]["rag_model"] == "openai/gpt-4o-mini"

    # Folder creation allowed for editor.
    r = client.post(
        f"/api/workspaces/{ws_id}/folders",
        headers=_bearer(editor),
        json={"path": "reports/2024", "acl": {}},
    )
    assert r.status_code == 201

    # Outsider still cannot create a folder.
    r = client.post(
        f"/api/workspaces/{ws_id}/folders",
        headers=_bearer(outsider),
        json={"path": "evil", "acl": {}},
    )
    assert r.status_code == 403

    # Remove member.
    r = client.delete(
        f"/api/workspaces/{ws_id}/members/{editor_id}",
        headers=_bearer(admin),
    )
    assert r.status_code == 204

    # Editor can no longer access.
    r = client.get(f"/api/workspaces/{ws_id}", headers=_bearer(editor))
    assert r.status_code == 403

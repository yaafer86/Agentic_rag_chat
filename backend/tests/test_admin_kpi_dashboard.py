"""Admin + KPI + Dashboard endpoint tests."""
from __future__ import annotations


def _register(client, email: str, password: str = "s3cretpass!"):
    client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )


def _token(client, email: str, password: str = "s3cretpass!") -> str:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def _bearer(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def _workspace(client, token: str, slug: str = "acme") -> str:
    r = client.post(
        "/api/workspaces",
        headers=_bearer(token),
        json={"name": "Acme", "slug": slug, "description": ""},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_admin_endpoints_require_global_admin(client) -> None:
    # First user registered → global_admin (per app.api.auth.register).
    _register(client, "root@example.com")
    _register(client, "user@example.com")
    root = _token(client, "root@example.com")
    user = _token(client, "user@example.com")

    # Non-admin hits admin → 403.
    r = client.get("/api/admin/users", headers=_bearer(user))
    assert r.status_code == 403

    # Admin gets list.
    r = client.get("/api/admin/users", headers=_bearer(root))
    assert r.status_code == 200
    assert any(u["email"] == "user@example.com" for u in r.json())


def test_admin_can_disable_and_promote(client) -> None:
    _register(client, "root@example.com")
    _register(client, "user@example.com")
    root = _token(client, "root@example.com")

    users = client.get("/api/admin/users", headers=_bearer(root)).json()
    uid = next(u["id"] for u in users if u["email"] == "user@example.com")

    r = client.put(
        f"/api/admin/users/{uid}/active",
        headers=_bearer(root),
        params={"active": False},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # Disabled user can't log in.
    r = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "s3cretpass!"},
    )
    assert r.status_code == 403

    # Promote + reactivate.
    client.put(f"/api/admin/users/{uid}/active", headers=_bearer(root), params={"active": True})
    r = client.put(
        f"/api/admin/users/{uid}/global-admin",
        headers=_bearer(root),
        params={"value": True},
    )
    assert r.status_code == 200
    assert r.json()["is_global_admin"] is True


def test_audit_log_records_admin_actions(client) -> None:
    _register(client, "root@example.com")
    _register(client, "user@example.com")
    root = _token(client, "root@example.com")
    users = client.get("/api/admin/users", headers=_bearer(root)).json()
    uid = next(u["id"] for u in users if u["email"] == "user@example.com")
    client.put(
        f"/api/admin/users/{uid}/active", headers=_bearer(root), params={"active": False}
    )
    r = client.get("/api/admin/audit", headers=_bearer(root))
    assert r.status_code == 200
    actions = {entry["action"] for entry in r.json()}
    assert "admin.user.set_active" in actions


def test_kpi_crud_and_rejection(client) -> None:
    _register(client, "owner@example.com")
    token = _token(client, "owner@example.com")
    ws_id = _workspace(client, token)

    # Valid formula.
    r = client.post(
        "/api/kpi",
        headers=_bearer(token),
        params={"workspace_id": ws_id},
        json={"name": "Gross margin", "formula": "(rev - cogs) / rev", "unit": "ratio"},
    )
    assert r.status_code == 201, r.text
    kpi_id = r.json()["id"]

    # Unsafe formula rejected at creation.
    r = client.post(
        "/api/kpi",
        headers=_bearer(token),
        params={"workspace_id": ws_id},
        json={"name": "bad", "formula": "__import__('os')", "unit": ""},
    )
    assert r.status_code == 400

    # Evaluate.
    r = client.post(
        "/api/kpi/evaluate",
        headers=_bearer(token),
        params={"workspace_id": ws_id},
        json={"formula": "rev - cogs", "variables": {"rev": 100, "cogs": 60}},
    )
    assert r.status_code == 200
    assert r.json()["value"] == 40

    # List shows it.
    r = client.get(
        "/api/kpi", headers=_bearer(token), params={"workspace_id": ws_id}
    )
    assert any(k["id"] == kpi_id for k in r.json())


def test_dashboard_crud(client) -> None:
    _register(client, "owner@example.com")
    token = _token(client, "owner@example.com")
    ws_id = _workspace(client, token)

    r = client.post(
        "/api/dashboards",
        headers=_bearer(token),
        params={"workspace_id": ws_id},
        json={
            "name": "Quarterly",
            "layout": {"widgets": [{"id": "w1", "type": "bar", "kpi_id": "x"}]},
            "global_filters": {"period": "Q1"},
        },
    )
    assert r.status_code == 201, r.text
    did = r.json()["id"]

    r = client.get(
        f"/api/dashboards/{did}",
        headers=_bearer(token),
        params={"workspace_id": ws_id},
    )
    assert r.status_code == 200
    assert r.json()["global_filters"]["period"] == "Q1"

    r = client.put(
        f"/api/dashboards/{did}",
        headers=_bearer(token),
        params={"workspace_id": ws_id},
        json={
            "name": "Quarterly v2",
            "layout": r.json()["layout"],
            "global_filters": {"period": "Q2"},
        },
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Quarterly v2"

    r = client.delete(
        f"/api/dashboards/{did}",
        headers=_bearer(token),
        params={"workspace_id": ws_id},
    )
    assert r.status_code == 204


def test_providers_endpoint_returns_status(client) -> None:
    _register(client, "root@example.com")
    token = _token(client, "root@example.com")
    r = client.get("/api/admin/providers", headers=_bearer(token))
    assert r.status_code == 200
    body = r.json()
    # In the test env nothing is reachable; all probes should return False cleanly.
    for key in ("qdrant", "neo4j", "minio"):
        assert key in body

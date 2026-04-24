"""Sandbox endpoint tests.

The Docker daemon is not available in the CI/test env. We expect a 503 with a
clear error — the endpoint contract is covered; real execution is exercised
only in the integration suite on a host with Docker.
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


def test_sandbox_requires_membership(client) -> None:
    owner = _auth(client, "owner@example.com")
    ws_id = _make_workspace(client, owner)
    outsider = _auth(client, "outsider@example.com")
    r = client.post(
        "/api/sandbox/run",
        headers=_bearer(outsider),
        params={"workspace_id": ws_id},
        json={"code": "print('hi')"},
    )
    assert r.status_code == 403


def test_sandbox_returns_503_without_docker(client) -> None:
    owner = _auth(client, "owner@example.com")
    ws_id = _make_workspace(client, owner)
    r = client.post(
        "/api/sandbox/run",
        headers=_bearer(owner),
        params={"workspace_id": ws_id},
        json={"code": "print('hi')", "timeout_s": 5, "memory_mb": 256},
    )
    # In an environment with Docker this would be 200; without, we expect 503.
    assert r.status_code in (200, 503)
    if r.status_code == 503:
        assert "sandbox unavailable" in r.json()["detail"]


def test_sandbox_validates_payload(client) -> None:
    owner = _auth(client, "owner@example.com")
    ws_id = _make_workspace(client, owner)
    r = client.post(
        "/api/sandbox/run",
        headers=_bearer(owner),
        params={"workspace_id": ws_id},
        json={"code": "", "timeout_s": 5, "memory_mb": 256},
    )
    assert r.status_code == 422  # empty code rejected by min_length


def test_sandbox_build_tar_roundtrip() -> None:
    """Verify the input-tar builder produces a readable archive."""
    import base64
    import tarfile
    from io import BytesIO

    from app.services.sandbox import _build_input_tar

    buf = _build_input_tar(
        "print(1)",
        [{"name": "data.csv", "base64": base64.b64encode(b"a,b\n1,2").decode()}],
    )
    with tarfile.open(fileobj=BytesIO(buf.getvalue()), mode="r") as tar:
        names = {m.name for m in tar.getmembers()}
    assert "user_code.py" in names
    assert "bootstrap.py" in names
    assert "inputs/data.csv" in names

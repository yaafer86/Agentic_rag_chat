"""Auth flow tests."""
from __future__ import annotations


def _register(client, email: str, password: str = "s3cretpass!"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )


def test_register_login_me_refresh(client) -> None:
    r = _register(client, "alice@example.com")
    assert r.status_code == 201, r.text
    # First user becomes global admin.
    assert r.json()["is_global_admin"] is True

    r = _register(client, "bob@example.com")
    assert r.status_code == 201
    assert r.json()["is_global_admin"] is False

    # Duplicate email.
    r = _register(client, "alice@example.com")
    assert r.status_code == 409

    # Login.
    r = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "s3cretpass!"},
    )
    assert r.status_code == 200
    tokens = r.json()
    assert tokens["token_type"] == "bearer"

    # Wrong password.
    r = client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "wrong"},
    )
    assert r.status_code == 401

    # /me requires access token.
    r = client.get("/api/auth/me")
    assert r.status_code == 401

    r = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == "bob@example.com"

    # Refresh token exchange.
    r = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert r.status_code == 200
    new_tokens = r.json()
    assert new_tokens["access_token"] != tokens["access_token"]

    # Access token cannot be used for refresh.
    r = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )
    assert r.status_code == 401

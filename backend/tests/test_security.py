from app.core.security import (
    decode_token,
    hash_password,
    issue_access_token,
    issue_refresh_token,
    verify_password,
)


def test_password_roundtrip() -> None:
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong password", h)


def test_long_password_not_silently_truncated() -> None:
    # Longer than bcrypt's 72-byte cap; our sha256 pre-hash makes this safe.
    p1 = "a" * 100 + "X"
    p2 = "a" * 100 + "Y"
    h = hash_password(p1)
    assert verify_password(p1, h)
    assert not verify_password(p2, h)


def test_tokens_roundtrip() -> None:
    tok = issue_access_token("user-123", admin=True)
    payload = decode_token(tok)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["admin"] is True

    rtok = issue_refresh_token("user-123")
    rp = decode_token(rtok)
    assert rp["type"] == "refresh"

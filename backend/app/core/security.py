"""Password hashing and JWT utilities."""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

_settings = get_settings()
_ALGO = "HS256"

ACCESS_TTL = timedelta(minutes=60)
REFRESH_TTL = timedelta(days=14)


def _prepare(password: str) -> bytes:
    # bcrypt caps inputs at 72 bytes; pre-hash with sha256 to avoid silent truncation.
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), hashed.encode("ascii"))
    except Exception:
        return False


def _issue(sub: str, kind: Literal["access", "refresh"], extra: dict[str, Any] | None = None) -> str:
    ttl = ACCESS_TTL if kind == "access" else REFRESH_TTL
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "type": kind,
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_ALGO)


def issue_access_token(user_id: str, **extra: Any) -> str:
    return _issue(user_id, "access", extra)


def issue_refresh_token(user_id: str) -> str:
    return _issue(user_id, "refresh")


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _settings.jwt_secret, algorithms=[_ALGO])
    except JWTError as e:
        raise ValueError(f"invalid token: {e}") from e


def api_key_hash(raw: str) -> str:
    return hmac.new(_settings.jwt_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()


__all__ = [
    "api_key_hash",
    "decode_token",
    "hash_password",
    "issue_access_token",
    "issue_refresh_token",
    "verify_password",
]

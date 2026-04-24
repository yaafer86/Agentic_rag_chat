"""Shared pytest fixtures.

Each test gets a fresh schema (tables dropped and recreated) so tests are order-independent.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import tempfile

import pytest

_tmp = pathlib.Path(tempfile.mkdtemp(prefix="rag-test-"))
os.environ["POSTGRES_URL"] = f"sqlite+aiosqlite:///{_tmp / 'test.db'}"
os.environ["JWT_SECRET"] = "test-secret-change-in-prod-but-long-enough"
os.environ["APP_BASE_URL"] = "http://testserver"


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.core.db import Base, engine
    from app.main import app

    async def _reset() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_reset())

    with TestClient(app) as c:
        yield c

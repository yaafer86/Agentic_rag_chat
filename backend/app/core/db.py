"""Database engine, session, and RLS context management."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()


def _engine_kwargs(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


engine = create_async_engine(_settings.postgres_url, **_engine_kwargs(_settings.postgres_url))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def session_scope(
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> AsyncIterator[AsyncSession]:
    """Yield a session with RLS context variables set on Postgres.

    On SQLite (tests) the SET LOCAL calls are no-ops.
    """
    async with SessionLocal() as session:
        if engine.dialect.name == "postgresql":
            if user_id:
                await session.execute(
                    _raw("SELECT set_config('app.current_user', :v, true)"),
                    {"v": user_id},
                )
            if workspace_id:
                await session.execute(
                    _raw("SELECT set_config('app.current_workspace', :v, true)"),
                    {"v": workspace_id},
                )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _raw(sql: str):
    from sqlalchemy import text

    return text(sql)


async def init_db() -> None:
    """Dev-only helper: create all tables. Production uses Alembic."""
    from app.models import db as _models  # noqa: F401 ensure models are imported

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    await engine.dispose()


__all__ = ["Base", "SessionLocal", "dispose_engine", "engine", "init_db", "session_scope"]

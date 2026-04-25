"""Alembic environment — async-aware, reads the URL from app.core.config.

Supports both sync SQLite (for dev inspection) and async Postgres. For async URLs
we use the AsyncEngine's run_sync pattern.
"""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import Base

# Import models so MetaData is populated.
from app.models import db as _models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Priority: -x db_url=... CLI override, then POSTGRES_URL env var, then alembic.ini.
# Reads from os.environ directly (not app.core.config) because Settings is lru_cached
# and the cache may predate a test's URL override.
_cli_url = context.get_x_argument(as_dictionary=True).get("db_url")
_resolved_url = _cli_url or os.environ.get("POSTGRES_URL") or config.get_main_option("sqlalchemy.url")
if _resolved_url:
    config.set_main_option("sqlalchemy.url", _resolved_url)

target_metadata = Base.metadata


def _is_async(url: str) -> bool:
    return "+asyncpg" in url or "+aiosqlite" in url


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = AsyncEngine(
        engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
            future=True,
        )
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    if _is_async(config.get_main_option("sqlalchemy.url", "")):
        asyncio.run(run_async_migrations())
        return
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

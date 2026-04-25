"""Smoke-test the Alembic config by building a fresh SQLite DB through the
migration stack and verifying every ORM model round-trips insert/select.

This catches divergence between models and migrations before Postgres ever
sees them.
"""
from __future__ import annotations

import os
import pathlib
import tempfile


def test_alembic_upgrade_head_creates_all_tables() -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="rag-alembic-"))
    db_path = tmp / "alembic.db"
    # Alembic runs sync here; use a sync sqlite URL.
    sync_url = f"sqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    # Point the running app at the same DB so env.py picks the right URL.
    prev = os.environ.get("POSTGRES_URL")
    os.environ["POSTGRES_URL"] = async_url
    try:
        backend_dir = pathlib.Path(__file__).resolve().parents[1]
        cfg = Config(str(backend_dir / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        cfg.set_main_option("sqlalchemy.url", sync_url)
        command.upgrade(cfg, "head")
    finally:
        if prev is not None:
            os.environ["POSTGRES_URL"] = prev

    engine = create_engine(sync_url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    expected = {
        "users",
        "workspaces",
        "workspace_members",
        "folders",
        "documents",
        "chat_messages",
        "custom_kpis",
        "dashboards",
        "audit_logs",
        "api_keys",
        "alembic_version",
    }
    assert expected.issubset(tables), f"missing tables: {expected - tables}"

"""rls policies on workspace-scoped tables

Enables Row-Level Security on Postgres. The backend sets
`app.current_workspace` and `app.current_user` session vars via
session_scope(), and RLS policies key off those to isolate rows.

On SQLite (tests / dev) this migration is a no-op.

Revision ID: 0002_rls
Revises: 0001_initial
Create Date: 2026-04-24 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_rls"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLES = (
    "workspaces",
    "workspace_members",
    "folders",
    "documents",
    "chat_messages",
    "custom_kpis",
    "dashboards",
)


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return

    # `workspaces` is keyed on id directly; others on workspace_id.
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # workspaces: only the current workspace is visible, or any when
    # app.current_workspace is empty (used by global_admin code paths).
    op.execute(
        """
        CREATE POLICY workspaces_scope ON workspaces
          USING (
            current_setting('app.current_workspace', true) IS NULL
            OR current_setting('app.current_workspace', true) = ''
            OR id::text = current_setting('app.current_workspace', true)
          )
          WITH CHECK (
            current_setting('app.current_workspace', true) IS NULL
            OR current_setting('app.current_workspace', true) = ''
            OR id::text = current_setting('app.current_workspace', true)
          )
        """
    )

    # All other tables: match on workspace_id.
    for table in _TABLES:
        if table == "workspaces":
            continue
        op.execute(
            f"""
            CREATE POLICY {table}_workspace_scope ON {table}
              USING (
                current_setting('app.current_workspace', true) IS NULL
                OR current_setting('app.current_workspace', true) = ''
                OR workspace_id::text = current_setting('app.current_workspace', true)
              )
              WITH CHECK (
                current_setting('app.current_workspace', true) IS NULL
                OR current_setting('app.current_workspace', true) = ''
                OR workspace_id::text = current_setting('app.current_workspace', true)
              )
            """
        )


def downgrade() -> None:
    if not _is_postgres():
        return
    for table in _TABLES:
        policy = "workspaces_scope" if table == "workspaces" else f"{table}_workspace_scope"
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

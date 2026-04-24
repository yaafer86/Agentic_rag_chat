-- PostgreSQL bootstrap
-- Runs automatically on first container start (mounted to /docker-entrypoint-initdb.d).
-- Creates extensions needed by the platform. RLS policies are added in P0 via Alembic migrations.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Example placeholder for the RLS pattern that P0 will implement:
--
-- ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY doc_workspace_isolation ON documents
--     USING (workspace_id = current_setting('app.current_workspace')::uuid);
--
-- The backend sets `app.current_workspace` per request via SET LOCAL in a
-- transaction hook. See backend/app/core/db.py (to be added in P0).

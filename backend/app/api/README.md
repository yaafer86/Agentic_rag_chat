# Backend API routers — planned

Mapped to the roadmap phases in the top-level README.

| Router file | Phase | Responsibility |
|------------|-------|---------------|
| `auth.py` | P0 | Login, refresh, JWT issuance, password reset |
| `upload.py` | P1 | File upload, VLM ingestion trigger, quota check |
| `chat.py` | P2 | RAG chat, intent routing, SSE thinking stream |
| `sandbox.py` | P3 | `POST /sandbox/run`, artifact download |
| `kg.py` | P4 | Knowledge-graph queries, Cypher templates, viz data |
| `dashboard.py` | P5 | KPI builder, dashboard CRUD, export |
| `admin.py` | P0/P5 | User & workspace admin, audit log, provider config |

Each router mounts under `/api/...` and enforces RBAC via `@require_role` / `@check_folder_acl` decorators (added in P0).

# Architecture

System topology, data ownership, and the security envelope. Diagrams render natively on GitHub via Mermaid.

---

## 1. Service topology

```mermaid
flowchart TB
    subgraph Client["Browser (Vite + React 18)"]
        UI[App Shell + Tabs]
        UI --> ChatUI[Chat<br/>RTL detect · thinking stream]
        UI --> SandboxUI[Sandbox<br/>code editor + plots]
        UI --> KGUI[Knowledge<br/>timeline + themes]
        UI --> DashUI[Dashboards<br/>builder]
        UI --> SettingsUI[Settings<br/>model prefs]
        UI --> AdminUI[Admin<br/>users + audit]
    end

    Client -- HTTPS / SSE --> API[FastAPI Gateway<br/>JWT · CORS · RBAC deps]

    subgraph Backend["Backend services"]
        API --> Auth[/api/auth/]
        API --> WS[/api/workspaces/]
        API --> Upload[/api/upload/]
        API --> Chat[/api/chat<br/>RAG agent + SSE/]
        API --> Sandbox[/api/sandbox/run/]
        API --> KG[/api/kg/]
        API --> KPI[/api/kpi/]
        API --> Dash[/api/dashboards/]
        API --> Adm[/api/admin/]
        API --> Prov[/api/providers/]
    end

    subgraph Stores["Data stores"]
        PG[(PostgreSQL<br/>users · workspaces<br/>RLS policies)]
        QD[(Qdrant<br/>vectors + metadata<br/>workspace filter)]
        N4[(Neo4j<br/>entities · relations<br/>composite indexes)]
        S3[(MinIO<br/>files · artifacts)]
    end

    subgraph Compute["Compute"]
        SBX[Microsandbox<br/>cap_drop=ALL · no-net]
        LLM[LiteLLM router<br/>fallback chain]
    end

    subgraph Providers["LLM providers (any subset)"]
        OAI[OpenAI]
        ANT[Anthropic]
        OR[OpenRouter]
        OL[Ollama local]
        LMS[LMStudio local]
    end

    Auth --> PG
    WS --> PG
    Upload --> PG
    Upload --> S3
    Upload --> QD
    Chat --> QD
    Chat --> N4
    Chat --> LLM
    Sandbox --> SBX
    KG --> N4
    KPI --> PG
    Dash --> PG
    Adm --> PG
    Prov --> OAI
    Prov --> ANT
    Prov --> OR
    Prov --> OL
    Prov --> LMS
    LLM --> OAI
    LLM --> ANT
    LLM --> OR
    LLM --> OL
    LLM --> LMS
```

---

## 2. Data ownership matrix

| Store | Owns | Workspace-scoped? | RLS / filter |
|-------|------|-------------------|--------------|
| PostgreSQL | users, workspaces, members, folders, documents (rows), chat history, KPIs, dashboards, audit log, API keys | Yes (except `users`) | Postgres RLS via `app.current_workspace` session var |
| Qdrant | chunk vectors + payload (workspace_id, folder_id, document_id, text, metadata) | Yes | `workspace_id` filter is **mandatory** in every query |
| Neo4j | entities, events, locations, relationships | Yes | `workspace_id` property + composite indexes |
| MinIO | raw uploaded files, sandbox artifacts, exports | Yes | Object key prefixed with `<workspace_id>/<doc_id>/...` |

---

## 3. Auth + RBAC decision tree

```mermaid
flowchart TD
    R[Request hits FastAPI] --> H{Has Authorization header?}
    H -- no --> R401[401 missing header]
    H -- yes --> J{Decode JWT}
    J -- fail --> R401b[401 invalid token]
    J -- ok --> T{type == access?}
    T -- no --> R401c[401 wrong type]
    T -- yes --> U[Load User by sub]
    U --> A{is_active?}
    A -- no --> R401d[401 user inactive]
    A -- yes --> E{Endpoint requires<br/>global_admin?}
    E -- yes --> GA{user.is_global_admin?}
    GA -- no --> R403a[403 admin required]
    GA -- yes --> OK1[Allowed]
    E -- no --> WS{Endpoint scoped<br/>to workspace?}
    WS -- no --> OK2[Allowed]
    WS -- yes --> M{User in<br/>workspace_members<br/>OR global_admin?}
    M -- no --> R403b[403 not a member]
    M -- yes --> RR{Role check via<br/>require_role?}
    RR -- fail --> R403c[403 insufficient role]
    RR -- pass --> FA{Folder ACL<br/>required?}
    FA -- no --> OK3[Allowed]
    FA -- yes --> ACL{check_folder_acl<br/>matches user/role?}
    ACL -- no --> R403d[403 folder ACL]
    ACL -- yes --> OK4[Allowed]
```

Roles:
- `global_admin` — system-wide. CRUD users, workspaces, providers, audit log, impersonation.
- `workspace_admin` — within their workspace. Members, ACL, model prefs, quotas, dashboards, KPIs.
- `workspace_editor` — upload, chat, sandbox, KPI/dashboard create.
- `workspace_viewer` — read-only chat + dashboard view.

---

## 4. Request lifecycle (read path)

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant API as FastAPI
    participant AU as Auth dep
    participant WS as Workspace dep
    participant DB as Postgres (RLS)
    participant QD as Qdrant
    participant LLM as LiteLLM
    participant U as User
    B->>API: GET /api/chat/stream?q=...&workspace_id=...
    API->>AU: get_current_user
    AU->>DB: SELECT user
    DB-->>AU: user row
    API->>WS: _resolve_workspace
    WS->>DB: SELECT membership
    DB-->>WS: ok
    API->>API: run_rag(...)
    API->>LLM: aembed(query)
    LLM-->>API: vector
    API->>QD: hybrid_search(workspace_id, vector)
    QD-->>API: top-K hits
    API->>LLM: astream(prompt + context)
    LLM-->>API: chunk events
    API-->>B: SSE: thinking → tool_call → chunk → done
    API->>DB: persist user + assistant messages
    B-->>U: render bubbles + thinking panel
```

---

## 5. Request lifecycle (write path — upload + ingestion)

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant API as FastAPI
    participant DB as Postgres
    participant S3 as MinIO
    participant BG as BackgroundTask
    participant P as Pipeline
    participant VLM as VLM (LiteLLM)
    participant OCR as Doctr OCR
    participant LLM as Embedding
    participant QD as Qdrant
    B->>API: POST /api/upload (multipart)
    API->>DB: insert Document(status=pending)
    API->>S3: put_object(workspace/doc/filename)
    API->>DB: insert AuditLog
    API->>BG: schedule run_pipeline
    API-->>B: 201 Created (DocumentOut)
    BG->>P: ingest_bytes
    P->>P: parsers.parse → ParsedUnits
    loop per page/sheet
        alt unit.kind == image
            P->>VLM: extract_page (T=0.2)
            VLM-->>P: PageExtraction or None
            opt confidence < threshold
                P->>OCR: ocr_image (fallback)
                OCR-->>P: text + confidence
            end
        else unit.kind == text
            P->>P: chunk_text
        end
    end
    P->>LLM: aembed(chunks)
    LLM-->>P: vectors
    P->>QD: upsert(records w/ workspace_id)
    P->>DB: update Document status=indexed, confidence=avg
```

---

## 6. Security envelope

| Surface | Defense in depth |
|---------|------------------|
| Transport | HTTPS at the proxy; `Secure` cookies if you switch to cookie auth |
| Auth | JWT with `jti` nonce per token; bcrypt + sha256 pre-hash for passwords |
| AuthZ — table level | RLS on every workspace-scoped table, `FORCE ROW LEVEL SECURITY` so even superuser respects policies |
| AuthZ — application | `require_role`, `require_global_admin`, `check_folder_acl` decorators run before any business logic |
| Vector store | Mandatory `workspace_id` filter in `qdrant.hybrid_search`; client cannot omit it |
| Graph store | Every Cypher template includes `workspace_id`; relation types clamped to a fixed allowlist; no string interpolation of user-supplied values |
| Code execution | Microsandbox with `cap_drop=ALL`, `no-new-privileges`, `network=none`, `read_only`, tmpfs `/sandbox` + `/tmp`, mem/cpu quotas, timeout via `container.wait` + forced stop |
| LLM input | Aggregate before injection: > 100 hits → Neo4j theme aggregation, never raw chunks |
| LLM output | Pydantic v2 `strict=True, extra="forbid"` for VLM and KG extraction; retry once then fall back |
| KPI formulas | AST whitelist (no `eval`, no attribute access, no arbitrary calls); allowed funcs frozen at module level |
| File uploads | 100 MB hard cap, workspace quota check before write, MIME-typed parser dispatch |
| Audit | Every admin write + workspace mutation persists an `AuditLog` row; `/api/admin/audit` paginated query for review |

---

## 7. Configuration resolution order

```mermaid
flowchart LR
    A[API request] --> B{model_override<br/>in payload?}
    B -- yes --> Use[Use override]
    B -- no --> C{workspace.model_prefs<br/>has the field?}
    C -- yes --> Use2[Use workspace pref]
    C -- no --> D{default_fallback<br/>passed by caller?}
    D -- yes --> Use3[Use default]
    D -- no --> Err["Raise:<br/>no kind configured"]
    Use --> Litellm[litellm.acompletion<br/>fallbacks=workspace.fallback_chain]
    Use2 --> Litellm
    Use3 --> Litellm
```

The chat endpoint catches the "no model configured" exception and degrades to deterministic fallback so the UI keeps working.

---

## 8. Dark/light + RTL contract

```mermaid
flowchart LR
    Boot[main.tsx boot] --> Pref{localStorage.theme?}
    Pref -- dark --> AddDark[document.documentElement.add 'dark']
    Pref -- light --> RemoveDark[remove 'dark']
    Pref -- unset --> Sys{prefers-color-scheme: dark?}
    Sys -- yes --> AddDark
    Sys -- no --> RemoveDark
    AddDark --> Tailwind[Tailwind reads .dark var<br/>HSL tokens flip]
    RemoveDark --> Tailwind

    Msg[Each chat message text] --> Detect[lib/direction.detectDirection]
    Detect --> Range{First strong char<br/>in RTL Unicode range?}
    Range -- Hebrew/Arabic/Syriac/Thaana<br/>NKo/Samaritan/Mandaic/PF --> RTL[bubble dir='rtl']
    Range -- otherwise --> LTR[bubble dir='ltr']
    RTL --> Logical[CSS logical properties<br/>margin-inline-* etc.]
    LTR --> Logical
```

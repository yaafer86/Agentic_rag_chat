# Feature Flows

Per-feature flowcharts. Cross-reference with `ARCHITECTURE.md` for system topology.

---

## 1. Authentication & registration

```mermaid
flowchart TD
    Start([User opens app]) --> Hyd[Auth store hydrate]
    Hyd --> Tok{access_token in<br/>localStorage?}
    Tok -- yes --> Me[GET /api/auth/me]
    Me --> MeOk{200?}
    MeOk -- yes --> Auth[render AppShell]
    MeOk -- no --> Refresh{401 + has refresh?}
    Refresh -- yes --> Rfr[POST /api/auth/refresh]
    Rfr --> RfrOk{200?}
    RfrOk -- yes --> Store[store new tokens] --> Me
    RfrOk -- no --> Clear[clear tokens] --> Login
    Refresh -- no --> Login
    Tok -- no --> Login[render LoginPage]

    Login --> Mode{mode}
    Mode -- login --> POSTLog[POST /api/auth/login]
    Mode -- register --> POSTReg[POST /api/auth/register]
    POSTReg --> First{first user?}
    First -- yes --> Promote[promote to global_admin]
    First -- no --> Reg[regular user]
    Promote --> POSTLog
    Reg --> POSTLog
    POSTLog --> Issue[issue access + refresh<br/>both with jti nonce]
    Issue --> Auth
```

---

## 2. Document ingestion (VLM + OCR fallback)

```mermaid
flowchart TD
    U[User picks file] --> POST[POST /api/upload<br/>multipart]
    POST --> Empty{size==0?}
    Empty -- yes --> R400[400 empty file]
    Empty -- no --> Big{size > 100MB?}
    Big -- yes --> R413[413 too large]
    Big -- no --> Quota{used+size > quota?}
    Quota -- yes --> R402[402 quota exceeded]
    Quota -- no --> InsRow[Insert Document<br/>status=pending]
    InsRow --> Put[MinIO put_object]
    Put --> PutOk{ok?}
    PutOk -- no --> StoreFail[record storage_error<br/>continue with metadata]
    PutOk -- yes --> AuditL[Audit log]
    StoreFail --> AuditL
    AuditL --> BG[Schedule background<br/>ingest_bytes]
    AuditL --> R201[201 DocumentOut]

    BG --> Parse[parsers.parse → ParsedUnits]
    Parse --> Loop{for each unit}
    Loop -- text --> Chunk[chunk_text<br/>~500 tokens, overlap 50]
    Loop -- image --> ResolveVLM{vlm_model<br/>configured?}
    ResolveVLM -- no --> Skip[skip VLM, OCR-only]
    ResolveVLM -- yes --> CallVLM[acomplete @ T=0.2<br/>JSON-only system prompt]
    CallVLM --> Validate[Pydantic strict validate<br/>PageExtraction]
    Validate -- valid --> Conf{confidence ≥<br/>OCR_FALLBACK_THRESHOLD?}
    Validate -- invalid --> Retry{retries left?}
    Retry -- yes --> CallVLM
    Retry -- no --> OCR
    Conf -- yes --> Blocks[blocks → text]
    Conf -- no --> OCR[Doctr OCR fallback]
    Skip --> OCR
    OCR --> Confidences[avg word confidence]
    Blocks --> Chunk
    Confidences --> Chunk
    Chunk --> Embed[embed_texts<br/>batched 64]
    Embed --> Upsert[Qdrant upsert<br/>workspace_id payload]
    Upsert --> Update[Document.status=indexed<br/>confidence=avg]
    Update --> Done([end])

    R400 -.-> Done
    R413 -.-> Done
    R402 -.-> Done
```

---

## 3. RAG chat with thinking stream

```mermaid
flowchart TD
    Q[User submits message] --> SSE[GET /api/chat/stream<br/>fetch with Authorization]
    SSE --> Auth[get_current_user]
    Auth --> Member[verify workspace membership]
    Member --> Run[run_rag async generator]

    Run --> Classify[intent_mod.classify<br/>rule-based, 8 classes]
    Classify --> Y1[yield thinking event<br/>'Intent detected: ...']
    Y1 --> ResRag{rag_model configured?}
    ResRag -- no --> NoteR[yield thinking<br/>'deterministic mode']
    ResRag -- yes --> ResEmb{embedding_model<br/>configured?}
    NoteR --> ResEmb
    ResEmb -- yes --> Emb[aembed query]
    ResEmb -- no --> NoteE[yield thinking<br/>'no vector search']

    Emb --> EmbOk{ok?}
    EmbOk -- no --> NoteE
    EmbOk -- yes --> Y2[yield tool_call qdrant.hybrid_search]
    Y2 --> Search[Qdrant hybrid_search<br/>workspace_id MANDATORY]
    Search --> Y3[yield tool_result count]
    NoteE --> Y3

    Y3 --> Intent{intent}
    Intent -- timeline --> KGtl[neo4j.timeline]
    Intent -- summarize+>100 hits --> Agg[neo4j.aggregate_events_by_theme]
    Intent -- otherwise --> Direct[use top-K chunks]
    KGtl --> Compose
    Agg --> Compose[compose context<br/>aggregated wins over raw]
    Direct --> Compose

    Compose --> ResRag2{rag_model?}
    ResRag2 -- no --> Fallback[deterministic summary]
    ResRag2 -- yes --> Stream[astream chat completion]
    Stream --> StreamOk{ok?}
    StreamOk -- no --> Fallback
    StreamOk -- yes --> ChunkLoop[for each chunk → yield chunk]
    Fallback --> ChunkLoop
    ChunkLoop --> Done[yield done<br/>content + sources + meta]
    Done --> Persist[INSERT user + assistant<br/>ChatMessage rows]
    Persist --> EndSSE([close SSE])

    EndSSE --> UI[Frontend renders<br/>bubbles + thinking panel]
```

Event types yielded by `run_rag` and forwarded over SSE:

| Event | When | Frontend renders as |
|-------|------|---------------------|
| `thinking` | reasoning step | line in collapsible thinking panel |
| `tool_call` | retrieval/aggregation about to run | `→ name(args)` line in panel |
| `tool_result` | retrieval/aggregation finished | `← name: N result(s)` line |
| `chunk` | LLM streamed delta | append to assistant bubble |
| `done` | terminal success | freeze bubble, show sources |
| `error` | terminal failure | red ⚠ in bubble |

---

## 4. Knowledge graph extraction & query

```mermaid
flowchart TD
    Trigger[KG extraction trigger] --> Pas[Passage from chunk or document]
    Pas --> Call[acomplete @ T=0.1<br/>strict JSON system prompt]
    Call --> Parse[parse_extraction]
    Parse --> Strict[Pydantic strict validate<br/>KGExtraction]
    Strict -- fail --> Drop[log + drop]
    Strict -- pass --> Slug[slugify entity ids]
    Slug --> Clamp{relation in<br/>RELATION_ALLOWLIST?}
    Clamp -- no --> Default[clamp to RELATED_TO]
    Clamp -- yes --> Keep[keep type]
    Default --> Merge
    Keep --> Merge[merge_into_graph]
    Merge --> Upsert[MERGE Entity by id<br/>SET workspace_id, kind, props]
    Upsert --> Rel[MATCH+MERGE relation<br/>type from allowlist only]

    subgraph Read["Read paths"]
        Tline[GET /api/kg/timeline] --> CTLine["MATCH (ev:Event)<br/>WHERE workspace_id = $ws"]
        Themes[GET /api/kg/themes] --> CThemes["MATCH (ev:Event {ws})<br/>WITH ev.theme, count(*)"]
        Network[GET /api/kg/entity/:id/network] --> CNet["MATCH (e:Entity {id, ws})<br/>+ neighbors[*1..N]"]
        CTLine --> Render[Frontend KGPage]
        CThemes --> Render
        CNet --> Render
    end
```

---

## 5. Microsandbox execution

```mermaid
flowchart TD
    UI[User clicks Run] --> POST[POST /api/sandbox/run<br/>code + files + timeout + memory]
    POST --> Auth[require_role editor/admin]
    Auth --> Exec[sandbox.run async]
    Exec --> Ping{docker.ping ok?}
    Ping -- no --> R503[503 SandboxUnavailable]
    Ping -- yes --> Create[containers.create]

    Create --> Cfg[--cap-drop=ALL<br/>--no-new-privileges<br/>--network=none<br/>--read-only<br/>--tmpfs /sandbox /tmp<br/>--memory --cpus]
    Cfg --> Tar[build tar archive<br/>user_code.py + bootstrap.py + inputs/]
    Tar --> PutTar[container.put_archive /sandbox]
    PutTar --> Start[container.start]
    Start --> Wait[container.wait timeout=N]
    Wait --> WaitOk{exited in time?}
    WaitOk -- no --> Stop[container.stop force]
    Stop --> Logs
    WaitOk -- yes --> Logs[collect stdout/stderr]
    Logs --> Get[get_archive /sandbox/out]
    Get --> Extract[extract plots/<br/>extract artifacts/]
    Extract --> Remove[container.remove force]
    Remove --> Resp[200 SandboxRunResponse<br/>plots base64 + artifacts]
    Resp --> Frontend[Render plots inline<br/>artifact download buttons]
```

---

## 6. KPI definition & evaluation

```mermaid
flowchart TD
    Create[POST /api/kpi<br/>name+formula+filters+thresholds] --> Extract[_extract_variable_names]
    Extract --> SafeEval[evaluate_formula<br/>with sample={var: 1}]
    SafeEval --> SyntaxOk{ok?}
    SyntaxOk -- no --> R400[400 invalid formula]
    SyntaxOk -- yes --> Insert[INSERT custom_kpis<br/>+ AuditLog]

    subgraph AST["AST whitelist evaluator"]
        Parse[ast.parse mode=eval] --> Walk[Walk nodes]
        Walk --> Allow{node type in whitelist?}
        Allow -- BinOp/UnaryOp/Compare<br/>BoolOp/Constant/Name/IfExp --> Recurse[recurse]
        Allow -- Call --> Func{name in known_funcs?}
        Func -- min/max/sum/abs<br/>round/avg/sqrt --> Apply[apply func]
        Func -- otherwise --> R[FormulaError]
        Allow -- otherwise --> R
    end

    Eval[POST /api/kpi/evaluate] --> Layer1[validate_formula_shape<br/>Layer 1 type/syntax]
    Layer1 --> Layer2[validate_arithmetic_consistency<br/>Layer 2 div-by-zero/non-finite]
    Layer2 --> Layer3{cross_source provided?}
    Layer3 -- yes --> CrossLayer[validate_cross_source<br/>Layer 3 missing/unknown sources]
    Layer3 -- no --> Skip[skip Layer 3]
    CrossLayer --> RunEval
    Skip --> RunEval[evaluate_formula]
    RunEval --> Out[Return value + issues array]
```

---

## 7. Dashboard builder

```mermaid
flowchart LR
    Pick[Select dashboard<br/>or click + New] --> Layout[Center pane:<br/>render layout.widgets]
    Pick --> KPIs[Right pane:<br/>list KPIs + create form]

    KPIs --> Add{Click 'add to dashboard'}
    Add --> AppendW[append widget<br/>{id, type, kpi_id, title}]
    AppendW --> Put[PUT /api/dashboards/:id<br/>updated layout]
    Put --> Render[invalidate query → re-render]

    Layout --> Remove{Click × on widget}
    Remove --> Filter[filter widgets by id]
    Filter --> Put

    Layout --> Rename[Edit name inline]
    Rename --> Put

    Layout --> Delete[Click delete]
    Delete --> Confirm{confirm?}
    Confirm -- yes --> Del[DELETE /api/dashboards/:id]
    Del --> Render
```

---

## 8. Settings: live model wiring

```mermaid
flowchart TD
    Load[Open Settings tab] --> WSQ[GET /api/workspaces/:id]
    WSQ --> Hydrate[populate form from<br/>workspace.model_prefs]
    Load --> ProvQ[GET /api/providers/models]
    ProvQ --> Probe{probe each provider}
    Probe --> Ollama["Ollama: GET /api/tags"]
    Probe --> LMStudio["LMStudio: GET /v1/models"]
    Probe --> OpenAI["OpenAI: GET /v1/models"]
    Probe --> OpenRouter["OpenRouter: GET /api/v1/models"]
    Probe --> Anthropic[Anthropic: curated list<br/>if key set]

    Ollama --> Combine[combine into<br/>all_models sorted]
    LMStudio --> Combine
    OpenAI --> Combine
    OpenRouter --> Combine
    Anthropic --> Combine
    Combine --> Datalist[populate &lt;datalist&gt;<br/>per model field]

    User[User picks model] --> Test{Click Test?}
    Test -- yes --> POST[POST /api/providers/test-model]
    POST --> Resolve[ResolvedModel + acomplete<br/>max_tokens=16, prompt='ping']
    Resolve --> Render[render latency + sample<br/>or error string]

    User --> Save{Click Save preferences}
    Save --> PUT[PUT /api/workspaces/:id/model-prefs]
    PUT --> Audit[INSERT AuditLog<br/>workspace.set_model_prefs]
    PUT --> Inval[invalidate workspace query]
```

---

## 9. RBAC enforcement (per-request)

```mermaid
sequenceDiagram
    autonumber
    participant Req as Request
    participant Mid as FastAPI router
    participant Auth as get_current_user
    participant WS as get_workspace
    participant RR as require_role / require_global_admin
    participant ACL as check_folder_acl
    participant H as Handler
    participant DB as Postgres
    Req->>Mid: HTTP
    Mid->>Auth: dep
    Auth->>DB: SELECT user
    DB-->>Auth: user row
    Auth-->>Mid: User
    Mid->>WS: dep (if scoped)
    WS->>DB: SELECT membership
    DB-->>WS: row or null
    alt outsider + not global_admin
        WS-->>Req: 403
    end
    Mid->>RR: dep (if role-gated)
    alt role insufficient
        RR-->>Req: 403
    end
    Mid->>H: invoke
    opt folder-scoped op
        H->>ACL: check_folder_acl(folder.acl, user.id, member.role, action)
        alt no match
            H-->>Req: 403
        end
    end
    H->>DB: business logic (RLS engaged)
    DB-->>H: rows scoped by app.current_workspace
    H-->>Req: 200
```

---

## 10. End-to-end: a user asks a question

```mermaid
flowchart TD
    A[User types message] --> B{First strong char<br/>RTL range?}
    B -- yes --> C[Composer dir='rtl'<br/>logical CSS flips]
    B -- no --> D[Composer dir='ltr']
    C --> E[Click Send]
    D --> E
    E --> F[openChatStream<br/>fetch SSE]
    F --> G[run_rag yields events]
    G --> H[ThinkingStream panel<br/>updates per event]
    G --> I[Assistant bubble<br/>per-message RTL detection]
    H --> J[Done event<br/>sources [S1] [S2] rendered]
    I --> J
    J --> K[Persist conversation]
    K --> L([User sees answer])
```

---

## See also

- `INSTALL.md` — getting from zero to a running stack
- `ARCHITECTURE.md` — service topology and security envelope
- `../README.md` — feature spec, RBAC matrix, 500+ results strategy

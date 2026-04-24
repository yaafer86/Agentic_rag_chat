# Frontend features — planned

Each feature folder owns its components, hooks, and local state. Mapped to the roadmap in the top-level README.

| Feature | Phase | Notes |
|---------|-------|-------|
| `auth/` | P0 | Login, signup, session refresh, route guards |
| `chat/` | P2 | Conversation UI, message bubbles, **RTL auto-detection per message**, **thinking-stream panel** (SSE), file drop |
| `workspace/` | P2 | Workspace switcher, subfolder tree, ACL display |
| `sandbox/` | P3 | Code editor, run button, inline charts, artifact download |
| `admin/` | P5 | User/workspace management, audit log viewer, provider config |
| `settings/` | P0+ | Theme toggle (**dark/light**), language/direction preference, model prefs |

## Cross-cutting UX concerns

- **Theme (dark/light)** — Tailwind `darkMode: "class"`. The `<html>` element gets `class="dark"` from a Zustand store persisted to `localStorage`, initialized in `src/main.tsx` from `prefers-color-scheme`. Every component must be authored in both palettes.
- **RTL direction** — Chat messages auto-detect direction from their content (first strong character, Unicode script ranges for Arabic, Hebrew, Persian, Urdu). The message bubble receives `dir="rtl"` and uses CSS logical properties (`margin-inline-*`, `padding-inline-*`, `text-align: start`). A global `dir` override lives in user settings.
- **Thinking stream** — The chat feature subscribes to `GET /api/chat/stream` (SSE). While the model is reasoning, a collapsible "Thinking..." panel streams the intermediate tokens in real time. Collapsed by default; user can pin it open. Content is auditable and preserved in the message record.

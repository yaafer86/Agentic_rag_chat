import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { useWorkspaceStore } from "@/store/workspace";

type Workspace = {
  id: string;
  name: string;
  slug: string;
  description: string;
  model_prefs: ModelPrefs;
};

type ModelPrefs = {
  rag_model?: string;
  vlm_model?: string;
  agent_model?: string;
  embedding_model?: string;
  fallback_chain?: string[];
  temperature?: number;
  max_tokens?: number;
  cost_budget_usd?: number | null;
  enable_cache?: boolean;
};

type ProviderEntry = {
  provider: string;
  ok: boolean;
  models: string[];
  error: string | null;
};

type ProvidersResponse = {
  providers: ProviderEntry[];
  all_models: string[];
};

type TestResult = { ok: boolean; latency_ms: number; error: string | null; sample: string };

const KEYS: Array<{ key: keyof ModelPrefs; label: string; help: string }> = [
  { key: "rag_model", label: "RAG model", help: "Synthesizes the chat answer over retrieved context." },
  { key: "vlm_model", label: "VLM model", help: "Extracts structured data from images and PDF pages." },
  { key: "agent_model", label: "Agent model", help: "Used for intent classification and tool routing." },
  { key: "embedding_model", label: "Embedding model", help: "Vectorizes chunks for Qdrant search." },
];

export function SettingsPage() {
  const { currentId } = useWorkspaceStore();
  const { user } = useAuthStore();
  const qc = useQueryClient();

  const wsQ = useQuery({
    queryKey: ["workspace", currentId],
    queryFn: async () => (await api.get<Workspace>(`/api/workspaces/${currentId}`)).data,
    enabled: !!currentId,
  });

  const providersQ = useQuery({
    queryKey: ["providers", "models"],
    queryFn: async () => (await api.get<ProvidersResponse>("/api/providers/models")).data,
    retry: false,
    staleTime: 60_000,
  });

  const [draft, setDraft] = useState<ModelPrefs>({});
  const [fallbackInput, setFallbackInput] = useState("");
  const [testResults, setTestResults] = useState<Record<string, TestResult | null>>({});
  const [testing, setTesting] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (wsQ.data) setDraft(wsQ.data.model_prefs ?? {});
  }, [wsQ.data]);

  const allModels = useMemo(() => providersQ.data?.all_models ?? [], [providersQ.data]);

  const saveMut = useMutation({
    mutationFn: async (prefs: ModelPrefs) =>
      (await api.put<Workspace>(`/api/workspaces/${currentId}/model-prefs`, prefs)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace", currentId] });
      qc.invalidateQueries({ queryKey: ["workspaces"] });
    },
  });

  async function testField(field: keyof ModelPrefs) {
    const model = draft[field] as string | undefined;
    if (!model) return;
    setTesting((s) => ({ ...s, [field]: true }));
    try {
      const r = await api.post<TestResult>(
        "/api/providers/test-model",
        { model, prompt: "Reply with the single word: pong" },
        { params: { workspace_id: currentId } },
      );
      setTestResults((s) => ({ ...s, [field]: r.data }));
    } finally {
      setTesting((s) => ({ ...s, [field]: false }));
    }
  }

  function setKey<K extends keyof ModelPrefs>(k: K, v: ModelPrefs[K]) {
    setDraft((d) => ({ ...d, [k]: v }));
  }

  function addFallback() {
    const m = fallbackInput.trim();
    if (!m) return;
    setDraft((d) => ({ ...d, fallback_chain: [...(d.fallback_chain ?? []), m] }));
    setFallbackInput("");
  }

  function removeFallback(idx: number) {
    setDraft((d) => ({
      ...d,
      fallback_chain: (d.fallback_chain ?? []).filter((_, i) => i !== idx),
    }));
  }

  if (!currentId) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Select a workspace first.
      </div>
    );
  }

  if (wsQ.isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Loading…
      </div>
    );
  }

  // The backend enforces workspace_admin for the PUT; we just hint at it in the UI.
  const canSave = !!user; // membership is implicit (workspace was already loaded)

  return (
    <div className="grid h-full grid-cols-[1fr_300px] gap-4 overflow-hidden p-4 text-xs">
      <section className="flex min-h-0 flex-col gap-3 overflow-y-auto">
        <h2 className="text-sm font-medium">Model preferences</h2>
        <p className="text-muted-foreground">
          Models are resolved at runtime from this configuration plus an optional
          per-call override. Pick from the live-discovered list, or free-type a
          provider/slug pair (e.g. <code>openai/gpt-4o-mini</code>).
        </p>

        {KEYS.map(({ key, label, help }) => {
          const val = (draft[key] as string | undefined) ?? "";
          const result = testResults[key] ?? null;
          return (
            <div key={key} className="rounded-md border border-border bg-muted/40 p-3">
              <div className="mb-1 flex items-center justify-between">
                <label className="text-sm font-medium">{label}</label>
                <button
                  onClick={() => testField(key)}
                  disabled={!val || !!testing[key]}
                  className="rounded-md border border-border bg-background px-2 py-0.5 text-[11px] disabled:opacity-50"
                >
                  {testing[key] ? "Testing…" : "Test"}
                </button>
              </div>
              <p className="mb-2 text-muted-foreground">{help}</p>
              <input
                list={`models-${key}`}
                value={val}
                onChange={(e) => setKey(key, e.target.value)}
                placeholder="provider/model"
                className="w-full rounded-md border border-border bg-background px-2 py-1 font-mono"
              />
              <datalist id={`models-${key}`}>
                {allModels.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
              {result && (
                <div className="mt-2 rounded-md border border-border bg-background p-2">
                  <div className="flex items-center gap-2">
                    {result.ok ? (
                      <Check size={12} className="text-green-500" />
                    ) : (
                      <X size={12} className="text-red-500" />
                    )}
                    <span>{result.ok ? "ok" : "failed"}</span>
                    <span className="text-muted-foreground">
                      · {result.latency_ms} ms
                    </span>
                  </div>
                  {result.error && (
                    <pre className="mt-1 whitespace-pre-wrap text-red-500">{result.error}</pre>
                  )}
                  {result.sample && (
                    <pre className="mt-1 whitespace-pre-wrap text-muted-foreground">
                      {result.sample}
                    </pre>
                  )}
                </div>
              )}
            </div>
          );
        })}

        <div className="rounded-md border border-border bg-muted/40 p-3">
          <label className="text-sm font-medium">Fallback chain</label>
          <p className="mb-2 text-muted-foreground">
            Tried in order if the primary model fails. Common pattern: hosted →
            local Ollama.
          </p>
          <ul className="mb-2 flex flex-wrap gap-1">
            {(draft.fallback_chain ?? []).map((m, i) => (
              <li
                key={i}
                className="inline-flex items-center gap-1 rounded-full bg-accent/20 px-2 py-0.5"
              >
                <code>{m}</code>
                <button
                  onClick={() => removeFallback(i)}
                  className="text-muted-foreground hover:text-red-500"
                  aria-label="remove"
                >
                  ×
                </button>
              </li>
            ))}
            {(draft.fallback_chain ?? []).length === 0 && (
              <li className="text-muted-foreground">none</li>
            )}
          </ul>
          <div className="flex gap-1">
            <input
              list="models-fallback"
              value={fallbackInput}
              onChange={(e) => setFallbackInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addFallback();
                }
              }}
              placeholder="provider/model"
              className="flex-1 rounded-md border border-border bg-background px-2 py-1 font-mono"
            />
            <datalist id="models-fallback">
              {allModels.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
            <button
              type="button"
              onClick={addFallback}
              className="rounded-md bg-accent px-2 py-1 font-medium text-accent-foreground"
            >
              Add
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-md border border-border bg-muted/40 p-3">
            <label className="text-sm font-medium">Temperature</label>
            <input
              type="number"
              step="0.05"
              min={0}
              max={2}
              value={draft.temperature ?? 0.3}
              onChange={(e) => setKey("temperature", Number(e.target.value))}
              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1"
            />
          </div>
          <div className="rounded-md border border-border bg-muted/40 p-3">
            <label className="text-sm font-medium">Max tokens</label>
            <input
              type="number"
              min={64}
              max={32000}
              value={draft.max_tokens ?? 4096}
              onChange={(e) => setKey("max_tokens", Number(e.target.value))}
              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1"
            />
          </div>
          <div className="rounded-md border border-border bg-muted/40 p-3">
            <label className="text-sm font-medium">Cost budget (USD)</label>
            <input
              type="number"
              step="0.01"
              min={0}
              value={draft.cost_budget_usd ?? ""}
              onChange={(e) =>
                setKey(
                  "cost_budget_usd",
                  e.target.value === "" ? null : Number(e.target.value),
                )
              }
              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1"
              placeholder="unbounded"
            />
          </div>
        </div>

        <label className="inline-flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={draft.enable_cache ?? true}
            onChange={(e) => setKey("enable_cache", e.target.checked)}
          />
          Enable LiteLLM semantic cache
        </label>

        <div className="flex items-center gap-2">
          <button
            onClick={() => saveMut.mutate(draft)}
            disabled={!canSave || saveMut.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-3 py-1 font-medium text-accent-foreground disabled:opacity-50"
          >
            {saveMut.isPending && <Loader2 size={12} className="animate-spin" />}
            Save preferences
          </button>
          {saveMut.isSuccess && <span className="text-green-500">saved</span>}
          {saveMut.error && (
            <span className="text-red-500">
              {(saveMut.error as any)?.response?.data?.detail ?? "save failed"}
            </span>
          )}
          <span className="ms-auto text-muted-foreground">
            workspace_admin role required
          </span>
        </div>
      </section>

      <aside className="flex min-h-0 flex-col rounded-md border border-border bg-muted/40 p-3">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-medium">Providers</h2>
          <button
            onClick={() => qc.invalidateQueries({ queryKey: ["providers", "models"] })}
            className="text-[11px] text-muted-foreground hover:text-foreground"
          >
            refresh
          </button>
        </div>
        {providersQ.isLoading && <div className="text-muted-foreground">Probing…</div>}
        <ul className="space-y-2">
          {providersQ.data?.providers.map((p) => (
            <li key={p.provider} className="rounded-md border border-border bg-background p-2">
              <div className="flex items-center justify-between">
                <span className="font-medium capitalize">{p.provider}</span>
                <span
                  className={p.ok ? "text-green-500" : "text-red-500"}
                  title={p.error ?? ""}
                >
                  {p.ok ? `${p.models.length} models` : "unreachable"}
                </span>
              </div>
              {p.error && (
                <div className="mt-1 truncate text-muted-foreground" title={p.error}>
                  {p.error}
                </div>
              )}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

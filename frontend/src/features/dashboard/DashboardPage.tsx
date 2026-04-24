import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type KPI = {
  id: string;
  name: string;
  formula: string;
  unit: string;
};

type Dashboard = {
  id: string;
  name: string;
  layout: { widgets?: Array<{ id: string; type: string; kpi_id?: string; title?: string }> };
  global_filters: Record<string, unknown>;
};

export function DashboardPage() {
  const { currentId } = useWorkspaceStore();
  const qc = useQueryClient();

  const kpisQ = useQuery({
    queryKey: ["kpis", currentId],
    queryFn: async () =>
      (await api.get<KPI[]>("/api/kpi", { params: { workspace_id: currentId } })).data,
    enabled: !!currentId,
  });

  const dashboardsQ = useQuery({
    queryKey: ["dashboards", currentId],
    queryFn: async () =>
      (await api.get<Dashboard[]>("/api/dashboards", { params: { workspace_id: currentId } })).data,
    enabled: !!currentId,
  });

  const [dashboardName, setDashboardName] = useState("New dashboard");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const createDashboard = useMutation({
    mutationFn: async () =>
      (await api.post<Dashboard>(
        "/api/dashboards",
        { name: dashboardName, layout: { widgets: [] }, global_filters: {} },
        { params: { workspace_id: currentId } },
      )).data,
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["dashboards", currentId] });
      setSelectedId(d.id);
    },
  });

  const updateDashboard = useMutation({
    mutationFn: async (d: Dashboard) =>
      (await api.put<Dashboard>(
        `/api/dashboards/${d.id}`,
        { name: d.name, layout: d.layout, global_filters: d.global_filters },
        { params: { workspace_id: currentId } },
      )).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboards", currentId] }),
  });

  const deleteDashboard = useMutation({
    mutationFn: async (id: string) =>
      api.delete(`/api/dashboards/${id}`, { params: { workspace_id: currentId } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboards", currentId] }),
  });

  const [newKPI, setNewKPI] = useState({ name: "", formula: "", unit: "" });
  const createKPI = useMutation({
    mutationFn: async () =>
      (await api.post<KPI>(
        "/api/kpi",
        { ...newKPI, filters: {}, thresholds: {}, source_document_ids: [] },
        { params: { workspace_id: currentId } },
      )).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["kpis", currentId] });
      setNewKPI({ name: "", formula: "", unit: "" });
    },
    onError: (e: any) => {
      alert(e?.response?.data?.detail ?? "failed");
    },
  });

  const selected = dashboardsQ.data?.find((d) => d.id === selectedId) ?? null;

  function addWidget(kpi: KPI) {
    if (!selected) return;
    const updated: Dashboard = {
      ...selected,
      layout: {
        widgets: [
          ...(selected.layout.widgets ?? []),
          { id: crypto.randomUUID(), type: "kpi_card", kpi_id: kpi.id, title: kpi.name },
        ],
      },
    };
    updateDashboard.mutate(updated);
  }

  function removeWidget(widgetId: string) {
    if (!selected) return;
    const updated: Dashboard = {
      ...selected,
      layout: {
        widgets: (selected.layout.widgets ?? []).filter((w) => w.id !== widgetId),
      },
    };
    updateDashboard.mutate(updated);
  }

  if (!currentId) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Select a workspace first.
      </div>
    );
  }

  return (
    <div className="grid h-full grid-cols-[240px_1fr_260px] gap-4 overflow-hidden p-4 text-xs">
      {/* Left: dashboards */}
      <aside className="flex min-h-0 flex-col rounded-md border border-border bg-muted/40 p-3">
        <div className="mb-2 flex items-center justify-between text-sm font-medium">
          Dashboards
          <button
            onClick={() => createDashboard.mutate()}
            className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-accent text-accent-foreground"
            aria-label="New dashboard"
          >
            <Plus size={12} />
          </button>
        </div>
        <div className="mb-2 flex gap-1">
          <input
            value={dashboardName}
            onChange={(e) => setDashboardName(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-2 py-1"
          />
        </div>
        <ul className="flex-1 space-y-1 overflow-y-auto">
          {dashboardsQ.data?.map((d) => (
            <li key={d.id}>
              <button
                onClick={() => setSelectedId(d.id)}
                className={
                  "w-full rounded-md px-2 py-1 text-start " +
                  (selectedId === d.id ? "bg-accent/20" : "hover:bg-muted")
                }
              >
                {d.name}
                <span className="ms-2 text-muted-foreground">
                  {(d.layout.widgets ?? []).length} widgets
                </span>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      {/* Center: canvas */}
      <main className="flex min-h-0 flex-col rounded-md border border-border bg-muted/40 p-3">
        {!selected && (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            Select or create a dashboard.
          </div>
        )}
        {selected && (
          <>
            <div className="mb-3 flex items-center justify-between">
              <input
                value={selected.name}
                onChange={(e) =>
                  updateDashboard.mutate({ ...selected, name: e.target.value })
                }
                className="rounded-md border border-transparent bg-transparent px-2 py-1 text-sm font-medium hover:border-border"
              />
              <button
                onClick={() => {
                  if (confirm(`Delete dashboard "${selected.name}"?`)) {
                    deleteDashboard.mutate(selected.id);
                    setSelectedId(null);
                  }
                }}
                className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-1 text-red-500"
              >
                <Trash2 size={12} /> delete
              </button>
            </div>

            <div className="grid flex-1 auto-rows-min grid-cols-3 gap-2 overflow-y-auto">
              {(selected.layout.widgets ?? []).map((w) => {
                const kpi = kpisQ.data?.find((k) => k.id === w.kpi_id);
                return (
                  <div
                    key={w.id}
                    className="flex min-h-24 flex-col rounded-md border border-border bg-background p-3"
                  >
                    <div className="mb-1 flex items-center justify-between">
                      <div className="font-medium">{w.title ?? "Widget"}</div>
                      <button
                        onClick={() => removeWidget(w.id)}
                        aria-label="Remove widget"
                        className="text-muted-foreground hover:text-red-500"
                      >
                        ×
                      </button>
                    </div>
                    {kpi ? (
                      <>
                        <code className="text-muted-foreground">{kpi.formula}</code>
                        {kpi.unit && (
                          <div className="mt-1 text-muted-foreground">unit: {kpi.unit}</div>
                        )}
                      </>
                    ) : (
                      <div className="text-muted-foreground">KPI not found</div>
                    )}
                  </div>
                );
              })}
              {(selected.layout.widgets ?? []).length === 0 && (
                <div className="col-span-3 flex h-32 items-center justify-center text-muted-foreground">
                  Empty — add a widget from the KPI list.
                </div>
              )}
            </div>
          </>
        )}
      </main>

      {/* Right: KPI palette */}
      <aside className="flex min-h-0 flex-col rounded-md border border-border bg-muted/40 p-3">
        <div className="mb-2 text-sm font-medium">KPIs</div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!newKPI.name || !newKPI.formula) return;
            createKPI.mutate();
          }}
          className="mb-2 space-y-1 rounded-md border border-border bg-background p-2"
        >
          <input
            placeholder="name"
            value={newKPI.name}
            onChange={(e) => setNewKPI((k) => ({ ...k, name: e.target.value }))}
            className="w-full rounded-md border border-border bg-background px-2 py-1"
          />
          <input
            placeholder="formula (e.g. (rev - cogs) / rev)"
            value={newKPI.formula}
            onChange={(e) => setNewKPI((k) => ({ ...k, formula: e.target.value }))}
            className="w-full rounded-md border border-border bg-background px-2 py-1 font-mono"
          />
          <div className="flex gap-1">
            <input
              placeholder="unit"
              value={newKPI.unit}
              onChange={(e) => setNewKPI((k) => ({ ...k, unit: e.target.value }))}
              className="flex-1 rounded-md border border-border bg-background px-2 py-1"
            />
            <button
              type="submit"
              className="rounded-md bg-accent px-2 py-1 font-medium text-accent-foreground"
            >
              Add
            </button>
          </div>
        </form>

        <ul className="flex-1 space-y-1 overflow-y-auto">
          {kpisQ.data?.map((k) => (
            <li key={k.id} className="rounded-md border border-border bg-background p-2">
              <div className="font-medium">
                {k.name}
                {k.unit && <span className="ms-1 text-muted-foreground">({k.unit})</span>}
              </div>
              <code className="block text-muted-foreground">{k.formula}</code>
              {selected && (
                <button
                  onClick={() => addWidget(k)}
                  className="mt-1 rounded-md border border-border px-2 py-0.5 text-[10px] hover:bg-accent/10"
                >
                  + add to dashboard
                </button>
              )}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

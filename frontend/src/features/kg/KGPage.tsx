import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type TimelineEvent = {
  id: string;
  title: string;
  date: string;
  theme: string | null;
  description: string | null;
};

type ThemeRow = { theme: string | null; cnt: number; samples: { id: string; title: string; date: string }[] };

export function KGPage() {
  const { currentId } = useWorkspaceStore();

  const timelineQ = useQuery({
    queryKey: ["kg", "timeline", currentId],
    queryFn: async () =>
      (await api.get<TimelineEvent[]>("/api/kg/timeline", { params: { workspace_id: currentId } })).data,
    enabled: !!currentId,
    retry: false,
  });

  const themesQ = useQuery({
    queryKey: ["kg", "themes", currentId],
    queryFn: async () =>
      (await api.get<ThemeRow[]>("/api/kg/themes", { params: { workspace_id: currentId } })).data,
    enabled: !!currentId,
    retry: false,
  });

  if (!currentId) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Select a workspace first.
      </div>
    );
  }

  const timelineErr = timelineQ.error as any;
  const themesErr = themesQ.error as any;

  return (
    <div className="grid h-full grid-cols-2 gap-4 overflow-hidden p-4">
      <section className="flex min-h-0 flex-col">
        <h2 className="mb-2 text-sm font-medium">Timeline</h2>
        <div className="flex-1 overflow-y-auto rounded-md border border-border bg-muted/40 p-3 text-xs">
          {timelineQ.isLoading && <div className="text-muted-foreground">Loading…</div>}
          {timelineErr && (
            <div className="text-muted-foreground">
              KG unavailable
              {timelineErr?.response?.data?.detail && <>: {String(timelineErr.response.data.detail)}</>}.
              Ingest documents or start Neo4j to populate this view.
            </div>
          )}
          {timelineQ.data && timelineQ.data.length === 0 && (
            <div className="text-muted-foreground">No events recorded yet.</div>
          )}
          {timelineQ.data && timelineQ.data.length > 0 && (
            <ol className="space-y-2">
              {timelineQ.data.map((ev) => (
                <li key={ev.id} className="border-s-2 border-accent/60 ps-3">
                  <div className="font-medium">{ev.title}</div>
                  <div className="text-muted-foreground">
                    {ev.date}
                    {ev.theme && <span className="ms-2 opacity-70">· {ev.theme}</span>}
                  </div>
                  {ev.description && <p className="mt-1 opacity-80">{ev.description}</p>}
                </li>
              ))}
            </ol>
          )}
        </div>
      </section>

      <section className="flex min-h-0 flex-col">
        <h2 className="mb-2 text-sm font-medium">Themes</h2>
        <div className="flex-1 overflow-y-auto rounded-md border border-border bg-muted/40 p-3 text-xs">
          {themesQ.isLoading && <div className="text-muted-foreground">Loading…</div>}
          {themesErr && (
            <div className="text-muted-foreground">
              KG unavailable
              {themesErr?.response?.data?.detail && <>: {String(themesErr.response.data.detail)}</>}.
            </div>
          )}
          {themesQ.data && themesQ.data.length === 0 && (
            <div className="text-muted-foreground">No themes recorded yet.</div>
          )}
          {themesQ.data && themesQ.data.length > 0 && (
            <ul className="space-y-3">
              {themesQ.data.map((t, i) => (
                <li key={i}>
                  <div className="font-medium">
                    {t.theme ?? "(untagged)"} · <span className="text-muted-foreground">{t.cnt}</span>
                  </div>
                  <ul className="mt-1 space-y-0.5 opacity-80">
                    {t.samples.slice(0, 5).map((s) => (
                      <li key={s.id} className="truncate">
                        {s.date} — {s.title}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}

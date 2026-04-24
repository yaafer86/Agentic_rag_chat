import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createWorkspace, listWorkspaces } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

export function WorkspacePicker() {
  const qc = useQueryClient();
  const { currentId, setCurrent } = useWorkspaceStore();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const { data: workspaces = [], isLoading } = useQuery({
    queryKey: ["workspaces"],
    queryFn: listWorkspaces,
  });

  const createMut = useMutation({
    mutationFn: ({ name, slug }: { name: string; slug: string }) => createWorkspace(name, slug),
    onSuccess: (ws: { id: string }) => {
      qc.invalidateQueries({ queryKey: ["workspaces"] });
      setCurrent(ws.id);
      setCreating(false);
      setName("");
      setSlug("");
    },
  });

  useEffect(() => {
    if (!currentId && workspaces.length > 0) setCurrent(workspaces[0].id);
  }, [currentId, workspaces, setCurrent]);

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading workspaces…</div>;

  return (
    <div className="flex items-center gap-2">
      <select
        value={currentId ?? ""}
        onChange={(e) => setCurrent(e.target.value || null)}
        className="rounded-md border border-border bg-background px-2 py-1 text-sm"
      >
        <option value="">Select workspace…</option>
        {workspaces.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </select>
      <button
        onClick={() => setCreating((c) => !c)}
        className="rounded-md border border-border bg-muted px-2 py-1 text-sm hover:bg-accent/10"
      >
        {creating ? "Cancel" : "+ New"}
      </button>
      {creating && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!name || !slug) return;
            createMut.mutate({ name, slug });
          }}
          className="flex items-center gap-2"
        >
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name"
            className="rounded-md border border-border bg-background px-2 py-1 text-sm"
          />
          <input
            value={slug}
            onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
            placeholder="slug"
            className="rounded-md border border-border bg-background px-2 py-1 text-sm font-mono"
          />
          <button
            type="submit"
            className="rounded-md bg-accent px-2 py-1 text-sm font-medium text-accent-foreground"
            disabled={createMut.isPending}
          >
            Create
          </button>
        </form>
      )}
    </div>
  );
}

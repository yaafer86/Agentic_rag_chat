import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

type AdminUser = {
  id: string;
  email: string;
  display_name: string;
  is_global_admin: boolean;
  is_active: boolean;
  created_at: string;
};

type AuditEntry = {
  id: string;
  workspace_id: string | null;
  user_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

type ProviderStatus = Record<string, boolean>;

export function AdminPage() {
  const { user } = useAuthStore();
  const qc = useQueryClient();

  const usersQ = useQuery({
    queryKey: ["admin", "users"],
    queryFn: async () => (await api.get<AdminUser[]>("/api/admin/users")).data,
    enabled: !!user?.is_global_admin,
    retry: false,
  });

  const auditQ = useQuery({
    queryKey: ["admin", "audit"],
    queryFn: async () =>
      (await api.get<AuditEntry[]>("/api/admin/audit", { params: { limit: 50 } })).data,
    enabled: !!user?.is_global_admin,
    retry: false,
  });

  const providersQ = useQuery({
    queryKey: ["admin", "providers"],
    queryFn: async () => (await api.get<ProviderStatus>("/api/admin/providers")).data,
    enabled: !!user?.is_global_admin,
    retry: false,
    refetchInterval: 30_000,
  });

  const setActive = useMutation({
    mutationFn: async ({ id, active }: { id: string; active: boolean }) =>
      api.put(`/api/admin/users/${id}/active`, null, { params: { active } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  const setAdmin = useMutation({
    mutationFn: async ({ id, value }: { id: string; value: boolean }) =>
      api.put(`/api/admin/users/${id}/global-admin`, null, { params: { value } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  if (!user?.is_global_admin) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Admin area is reserved for global admins.
      </div>
    );
  }

  return (
    <div className="grid h-full grid-cols-3 gap-4 overflow-hidden p-4 text-xs">
      <section className="col-span-2 flex min-h-0 flex-col">
        <h2 className="mb-2 text-sm font-medium">Users</h2>
        <div className="flex-1 overflow-y-auto rounded-md border border-border bg-muted/40">
          <table className="w-full text-xs">
            <thead className="border-b border-border bg-muted text-muted-foreground">
              <tr>
                <th className="p-2 text-start">Email</th>
                <th className="p-2 text-start">Active</th>
                <th className="p-2 text-start">Admin</th>
                <th className="p-2 text-start">Created</th>
              </tr>
            </thead>
            <tbody>
              {usersQ.data?.map((u) => (
                <tr key={u.id} className="border-b border-border/50 last:border-b-0">
                  <td className="p-2">
                    <div>{u.email}</div>
                    <div className="text-muted-foreground">{u.display_name}</div>
                  </td>
                  <td className="p-2">
                    <button
                      onClick={() =>
                        setActive.mutate({ id: u.id, active: !u.is_active })
                      }
                      className={
                        "rounded-md px-2 py-0.5 " +
                        (u.is_active
                          ? "bg-accent/20 text-accent"
                          : "bg-muted text-muted-foreground")
                      }
                    >
                      {u.is_active ? "active" : "disabled"}
                    </button>
                  </td>
                  <td className="p-2">
                    <button
                      onClick={() =>
                        setAdmin.mutate({ id: u.id, value: !u.is_global_admin })
                      }
                      className={
                        "rounded-md px-2 py-0.5 " +
                        (u.is_global_admin
                          ? "bg-accent/20 text-accent"
                          : "bg-muted text-muted-foreground")
                      }
                    >
                      {u.is_global_admin ? "global_admin" : "user"}
                    </button>
                  </td>
                  <td className="p-2 text-muted-foreground">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="flex min-h-0 flex-col gap-4">
        <div className="flex flex-col">
          <h2 className="mb-2 text-sm font-medium">Providers</h2>
          <ul className="space-y-1 rounded-md border border-border bg-muted/40 p-3">
            {providersQ.data &&
              Object.entries(providersQ.data).map(([name, ok]) => (
                <li key={name} className="flex items-center justify-between">
                  <span className="capitalize">{name}</span>
                  <span
                    className={ok ? "text-green-500" : "text-red-500"}
                  >
                    {ok ? "up" : "down"}
                  </span>
                </li>
              ))}
          </ul>
        </div>

        <div className="flex min-h-0 flex-1 flex-col">
          <h2 className="mb-2 text-sm font-medium">Audit log</h2>
          <ol className="flex-1 overflow-y-auto space-y-1 rounded-md border border-border bg-muted/40 p-3">
            {auditQ.data?.map((a) => (
              <li key={a.id} className="border-s-2 border-accent/40 ps-2">
                <div className="font-mono">{a.action}</div>
                <div className="text-muted-foreground">
                  {new Date(a.created_at).toLocaleString()} · {a.target_type}
                  {a.target_id && <> · {a.target_id.slice(0, 8)}</>}
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>
    </div>
  );
}

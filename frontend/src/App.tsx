import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { AppShell } from "@/components/AppShell";
import { LoginPage } from "@/features/auth/LoginPage";
import { ChatPage } from "@/features/chat/ChatPage";
import { KGPage } from "@/features/kg/KGPage";
import { SandboxPage } from "@/features/sandbox/SandboxPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { AdminPage } from "@/features/admin/AdminPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

type Tab = "chat" | "sandbox" | "kg" | "dashboard" | "settings" | "admin";

function Tabs({
  tab,
  onChange,
  showAdmin,
}: {
  tab: Tab;
  onChange: (t: Tab) => void;
  showAdmin: boolean;
}) {
  const items: { id: Tab; label: string }[] = [
    { id: "chat", label: "Chat" },
    { id: "sandbox", label: "Sandbox" },
    { id: "kg", label: "Knowledge" },
    { id: "dashboard", label: "Dashboards" },
    { id: "settings", label: "Settings" },
    ...(showAdmin ? [{ id: "admin" as Tab, label: "Admin" }] : []),
  ];
  return (
    <nav className="flex gap-1 border-b border-border bg-background px-4">
      {items.map((it) => (
        <button
          key={it.id}
          onClick={() => onChange(it.id)}
          className={
            "border-b-2 px-3 py-2 text-sm " +
            (tab === it.id
              ? "border-accent text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground")
          }
        >
          {it.label}
        </button>
      ))}
    </nav>
  );
}

function Gate() {
  const { user, loading, hydrate } = useAuthStore();
  const [tab, setTab] = useState<Tab>("chat");
  useEffect(() => {
    void hydrate();
  }, [hydrate]);
  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background text-foreground">
        <span className="text-sm text-muted-foreground">Loading…</span>
      </main>
    );
  }
  if (!user) return <LoginPage />;
  return (
    <AppShell>
      <div className="flex h-full flex-col">
        <Tabs tab={tab} onChange={setTab} showAdmin={user.is_global_admin} />
        <div className="flex-1 overflow-hidden">
          {tab === "chat" && <ChatPage />}
          {tab === "sandbox" && <SandboxPage />}
          {tab === "kg" && <KGPage />}
          {tab === "dashboard" && <DashboardPage />}
          {tab === "settings" && <SettingsPage />}
          {tab === "admin" && <AdminPage />}
        </div>
      </div>
    </AppShell>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Gate />
    </QueryClientProvider>
  );
}

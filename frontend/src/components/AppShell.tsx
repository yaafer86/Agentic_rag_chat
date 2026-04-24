import { LogOut } from "lucide-react";
import { useAuthStore } from "@/store/auth";
import { ThemeToggle } from "@/components/ThemeToggle";
import { WorkspacePicker } from "@/features/workspace/WorkspacePicker";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuthStore();
  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <header className="flex items-center gap-4 border-b border-border px-6 py-3">
        <h1 className="text-sm font-semibold tracking-tight">Agentic RAG</h1>
        <div className="flex-1">
          <WorkspacePicker />
        </div>
        {user && (
          <span className="text-xs text-muted-foreground">
            {user.display_name || user.email}
            {user.is_global_admin && (
              <span className="ms-2 rounded-full bg-accent/20 px-2 py-0.5 text-[10px] font-medium text-accent">
                admin
              </span>
            )}
          </span>
        )}
        <ThemeToggle />
        <button
          onClick={logout}
          aria-label="Sign out"
          className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-muted hover:bg-accent/10"
        >
          <LogOut size={16} />
        </button>
      </header>
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}

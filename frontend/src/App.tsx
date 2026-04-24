import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import { AppShell } from "@/components/AppShell";
import { LoginPage } from "@/features/auth/LoginPage";
import { ChatPage } from "@/features/chat/ChatPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

function Gate() {
  const { user, loading, hydrate } = useAuthStore();
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
      <ChatPage />
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

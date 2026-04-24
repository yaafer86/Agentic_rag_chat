import axios, { AxiosError } from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "";

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

export const TOKEN_KEY = "agentic_access_token";
export const REFRESH_KEY = "agentic_refresh_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

api.interceptors.request.use((config) => {
  const tok = getAccessToken();
  if (tok) config.headers.Authorization = `Bearer ${tok}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) return null;
  try {
    const r = await axios.post(`${API_BASE}/api/auth/refresh`, { refresh_token: refresh });
    setTokens(r.data.access_token, r.data.refresh_token);
    return r.data.access_token;
  } catch {
    clearTokens();
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    if (error.response?.status === 401 && !(error.config as any)?._retry) {
      (error.config as any)._retry = true;
      refreshing ||= tryRefresh();
      const newTok = await refreshing;
      refreshing = null;
      if (newTok) {
        (error.config!.headers as any).Authorization = `Bearer ${newTok}`;
        return api.request(error.config!);
      }
    }
    return Promise.reject(error);
  },
);

// ---------- Auth ----------

export async function login(email: string, password: string) {
  const r = await api.post("/api/auth/login", { email, password });
  setTokens(r.data.access_token, r.data.refresh_token);
  return r.data;
}

export async function register(email: string, password: string, display_name: string) {
  await api.post("/api/auth/register", { email, password, display_name });
  return login(email, password);
}

export async function me() {
  const r = await api.get("/api/auth/me");
  return r.data;
}

// ---------- Workspaces ----------

export async function listWorkspaces() {
  const r = await api.get("/api/workspaces");
  return r.data as Array<{ id: string; name: string; slug: string; description: string }>;
}

export async function createWorkspace(name: string, slug: string, description = "") {
  const r = await api.post("/api/workspaces", { name, slug, description });
  return r.data;
}

// ---------- Chat ----------

export type ChatEvent =
  | { event: "thinking"; content: string }
  | { event: "tool_call"; name: string; args?: any }
  | { event: "tool_result"; name: string; count?: number }
  | { event: "chunk"; content: string }
  | { event: "done"; content: string; sources: any[]; meta: any }
  | { event: "error"; message: string };

export function openChatStream(
  workspace_id: string,
  query: string,
  options: { conversation_id?: string; intent?: string; max_results?: number } = {},
): { events: AsyncIterable<ChatEvent>; close: () => void } {
  const token = getAccessToken();
  const params = new URLSearchParams({
    workspace_id,
    q: query,
    intent: options.intent ?? "auto",
    max_results: String(options.max_results ?? 50),
  });
  if (options.conversation_id) params.set("conversation_id", options.conversation_id);

  // EventSource doesn't support custom headers, so we fetch with streaming instead.
  const controller = new AbortController();
  async function* generate() {
    const resp = await fetch(`${API_BASE}/api/chat/stream?${params}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: controller.signal,
    });
    if (!resp.ok || !resp.body) {
      yield { event: "error", message: `stream failed: ${resp.status}` } as ChatEvent;
      return;
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const eventLine = frame.split("\n").find((l) => l.startsWith("event:"));
        const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
        if (!dataLine) continue;
        const kind = eventLine?.replace("event:", "").trim() || "message";
        try {
          const parsed = JSON.parse(dataLine.replace("data:", "").trim());
          yield { event: kind, ...parsed } as ChatEvent;
        } catch {
          // ignore malformed frame
        }
      }
    }
  }
  return { events: generate(), close: () => controller.abort() };
}

export async function chatNonStream(
  workspace_id: string,
  message: string,
  options: { conversation_id?: string; intent?: string; max_results?: number } = {},
) {
  const r = await api.post("/api/chat", {
    workspace_id,
    message,
    conversation_id: options.conversation_id,
    intent: options.intent ?? "auto",
    max_results: options.max_results ?? 50,
    stream_thinking: true,
  });
  return r.data;
}

// ---------- Upload ----------

export async function uploadFile(
  workspace_id: string,
  file: File,
  folder_id?: string,
) {
  const form = new FormData();
  form.append("file", file);
  if (folder_id) form.append("folder_id", folder_id);
  const r = await api.post("/api/upload", form, {
    params: { workspace_id },
    headers: { "Content-Type": "multipart/form-data" },
  });
  return r.data;
}

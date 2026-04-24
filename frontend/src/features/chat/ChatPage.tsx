import { useRef, useState } from "react";
import { Send, Upload } from "lucide-react";
import { openChatStream, uploadFile, type ChatEvent } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";
import { MessageBubble } from "@/components/MessageBubble";
import { ThinkingStream } from "@/components/ThinkingStream";
import { detectDirection } from "@/lib/direction";
import { cn } from "@/lib/cn";

type Turn = {
  role: "user" | "assistant";
  content: string;
  thinking: string[];
  sources?: Array<{ label: string; document_id?: string; score?: number }>;
  streaming?: boolean;
};

export function ChatPage() {
  const { currentId } = useWorkspaceStore();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const uploadRef = useRef<HTMLInputElement>(null);

  const composerDir = detectDirection(input);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!currentId || !input.trim() || streaming) return;
    const userTurn: Turn = { role: "user", content: input, thinking: [] };
    const assistantTurn: Turn = {
      role: "assistant",
      content: "",
      thinking: [],
      streaming: true,
    };
    setTurns((t) => [...t, userTurn, assistantTurn]);
    setInput("");
    setStreaming(true);

    const { events } = openChatStream(currentId, userTurn.content, {
      conversation_id: conversationId,
      intent: "auto",
      max_results: 50,
    });

    try {
      for await (const ev of events) {
        updateLastAssistant((t) => applyEvent(t, ev));
        if (ev.event === "done" || ev.event === "error") break;
      }
    } finally {
      setStreaming(false);
      updateLastAssistant((t) => ({ ...t, streaming: false }));
    }

    function updateLastAssistant(mutator: (t: Turn) => Turn) {
      setTurns((list) => {
        const next = [...list];
        const idx = next.length - 1;
        next[idx] = mutator(next[idx]);
        return next;
      });
    }

    function applyEvent(t: Turn, ev: ChatEvent): Turn {
      switch (ev.event) {
        case "thinking":
          return { ...t, thinking: [...t.thinking, ev.content] };
        case "tool_call":
          return { ...t, thinking: [...t.thinking, `→ ${ev.name}(${JSON.stringify(ev.args ?? {})})`] };
        case "tool_result":
          return { ...t, thinking: [...t.thinking, `← ${ev.name}: ${ev.count ?? 0} result(s)`] };
        case "chunk":
          return { ...t, content: (t.content || "") + ev.content };
        case "done":
          if (!conversationId && (ev.meta as any)?.conversation_id) {
            setConversationId((ev.meta as any).conversation_id);
          }
          return {
            ...t,
            content: ev.content || t.content,
            sources: ev.sources,
          };
        case "error":
          return { ...t, content: `⚠️ ${ev.message}` };
      }
    }
  }

  async function onUpload(file: File) {
    if (!currentId) return;
    try {
      await uploadFile(currentId, file);
      setTurns((t) => [
        ...t,
        {
          role: "assistant",
          content: `Uploaded **${file.name}**. Ingestion runs in the background.`,
          thinking: [],
        },
      ]);
    } catch (e: any) {
      setTurns((t) => [
        ...t,
        { role: "assistant", content: `Upload failed: ${e?.message ?? "unknown error"}`, thinking: [] },
      ]);
    }
  }

  if (!currentId) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Select a workspace to start chatting.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
        {turns.length === 0 && (
          <div className="mt-20 text-center text-sm text-muted-foreground">
            Ask a question, upload a file, or start typing.
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className="space-y-1">
            <MessageBubble role={t.role} content={t.content} sources={t.sources} />
            {t.role === "assistant" && (
              <ThinkingStream
                lines={t.thinking}
                active={!!t.streaming}
                defaultOpen={false}
              />
            )}
          </div>
        ))}
      </div>

      <form
        onSubmit={send}
        className="border-t border-border bg-background px-4 py-3"
      >
        <div className="flex items-end gap-2">
          <input
            ref={uploadRef}
            type="file"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
          />
          <button
            type="button"
            onClick={() => uploadRef.current?.click()}
            className="flex h-10 w-10 items-center justify-center rounded-md border border-border bg-muted hover:bg-accent/10"
            aria-label="Upload file"
            title="Upload file"
          >
            <Upload size={16} />
          </button>

          <textarea
            value={input}
            dir={composerDir}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send(e as unknown as React.FormEvent);
              }
            }}
            rows={1}
            placeholder="Type a message, Shift+Enter for newline…"
            className={cn(
              "min-h-10 flex-1 resize-none rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-accent",
            )}
          />

          <button
            type="submit"
            disabled={!input.trim() || streaming}
            className="flex h-10 items-center gap-2 rounded-md bg-accent px-3 text-sm font-medium text-accent-foreground disabled:opacity-50"
          >
            <Send size={14} />
            Send
          </button>
        </div>
      </form>
    </div>
  );
}

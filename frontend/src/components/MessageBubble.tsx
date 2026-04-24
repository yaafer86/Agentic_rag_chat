import { detectDirection } from "@/lib/direction";
import { cn } from "@/lib/cn";

export type Role = "user" | "assistant" | "system";

export function MessageBubble({
  role,
  content,
  sources,
}: {
  role: Role;
  content: string;
  sources?: Array<{ label: string; document_id?: string; score?: number }>;
}) {
  const dir = detectDirection(content);
  const isUser = role === "user";
  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        dir={dir}
        className={cn(
          "max-w-[85%] rounded-lg px-4 py-3 text-sm shadow-sm",
          isUser
            ? "bg-accent text-accent-foreground"
            : "bg-muted text-foreground border border-border",
        )}
      >
        <div className="whitespace-pre-wrap break-words">{content || (role === "assistant" ? "…" : "")}</div>
        {sources && sources.length > 0 && (
          <div className="mt-2 border-t border-border/50 pt-2 text-xs text-muted-foreground">
            <div className="font-medium mb-1">Sources</div>
            <ul className="space-y-0.5">
              {sources.map((s, i) => (
                <li key={i}>
                  <span className="font-mono">[{s.label}]</span>{" "}
                  <span className="opacity-80">{s.document_id?.slice(0, 8) ?? "—"}</span>
                  {s.score !== undefined && (
                    <span className="opacity-60"> · score {s.score.toFixed(3)}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

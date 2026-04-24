import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";

export function ThinkingStream({
  lines,
  active,
  defaultOpen = false,
}: {
  lines: string[];
  active: boolean;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!active && lines.length === 0) return null;
  return (
    <div className="my-2 rounded-md border border-border bg-muted/60 text-xs text-muted-foreground">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-start hover:bg-muted"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {active && <Loader2 size={14} className="animate-spin" />}
        <span className="font-medium">
          {active ? "Thinking…" : `Thought process (${lines.length} step${lines.length === 1 ? "" : "s"})`}
        </span>
      </button>
      {open && lines.length > 0 && (
        <div className="border-t border-border px-3 py-2">
          <ul className="space-y-1">
            {lines.map((l, i) => (
              <li key={i} className={cn("whitespace-pre-wrap break-words")}>
                · {l}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

import { useState } from "react";
import { Play } from "lucide-react";
import { api } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspace";

type Artifact = { name: string; mime: string; base64: string };

type RunResult = {
  stdout: string;
  stderr: string;
  exit_code: number;
  duration_ms: number;
  plots: string[];
  artifacts: Artifact[];
};

const SAMPLE = `import pandas as pd
import matplotlib.pyplot as plt

df = pd.DataFrame({"x": range(10), "y": [v*v for v in range(10)]})
print(df.head())

df.plot(x="x", y="y", title="Squares")
plt.show()

with open("out/artifacts/report.txt", "w") as f:
    f.write("rows=" + str(len(df)))
`;

export function SandboxPage() {
  const { currentId } = useWorkspaceStore();
  const [code, setCode] = useState(SAMPLE);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!currentId) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.post(
        "/api/sandbox/run",
        { code, timeout_s: 30, memory_mb: 512 },
        { params: { workspace_id: currentId } },
      );
      setResult(r.data as RunResult);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? "failed");
    } finally {
      setRunning(false);
    }
  }

  function download(a: Artifact) {
    const blob = new Blob([Uint8Array.from(atob(a.base64), (c) => c.charCodeAt(0))], {
      type: a.mime,
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = a.name;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (!currentId) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        Select a workspace first.
      </div>
    );
  }

  return (
    <div className="grid h-full grid-cols-2 gap-4 p-4">
      <div className="flex flex-col">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-sm font-medium">Python sandbox</span>
          <button
            onClick={run}
            disabled={running}
            className="ms-auto flex items-center gap-2 rounded-md bg-accent px-3 py-1 text-sm font-medium text-accent-foreground disabled:opacity-50"
          >
            <Play size={14} />
            {running ? "Running…" : "Run"}
          </button>
        </div>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          spellCheck={false}
          className="flex-1 resize-none rounded-md border border-border bg-background p-3 font-mono text-xs outline-none focus:ring-1 focus:ring-accent"
        />
      </div>

      <div className="flex flex-col overflow-hidden">
        <div className="mb-2 flex items-center gap-2 text-sm">
          <span className="font-medium">Output</span>
          {result && (
            <span className="text-xs text-muted-foreground">
              exit {result.exit_code} · {result.duration_ms} ms
            </span>
          )}
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto rounded-md border border-border bg-muted/40 p-3 text-xs">
          {error && <pre className="whitespace-pre-wrap text-red-500">{error}</pre>}
          {result && (
            <>
              {result.stdout && (
                <section>
                  <div className="mb-1 font-medium">stdout</div>
                  <pre className="whitespace-pre-wrap font-mono">{result.stdout}</pre>
                </section>
              )}
              {result.stderr && (
                <section>
                  <div className="mb-1 font-medium text-red-500">stderr</div>
                  <pre className="whitespace-pre-wrap font-mono text-red-500">
                    {result.stderr}
                  </pre>
                </section>
              )}
              {result.plots.length > 0 && (
                <section>
                  <div className="mb-1 font-medium">plots</div>
                  <div className="space-y-2">
                    {result.plots.map((p, i) => (
                      <img
                        key={i}
                        src={`data:image/png;base64,${p}`}
                        alt={`plot ${i + 1}`}
                        className="rounded border border-border"
                      />
                    ))}
                  </div>
                </section>
              )}
              {result.artifacts.length > 0 && (
                <section>
                  <div className="mb-1 font-medium">artifacts</div>
                  <ul className="space-y-1">
                    {result.artifacts.map((a) => (
                      <li key={a.name}>
                        <button
                          onClick={() => download(a)}
                          className="text-accent underline hover:no-underline"
                        >
                          {a.name}
                        </button>
                        <span className="opacity-60"> · {a.mime}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
          {!result && !error && !running && (
            <div className="text-muted-foreground">
              Click Run to execute the code in an isolated container.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

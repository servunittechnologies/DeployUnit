import { useEffect, useMemo, useRef, useState } from "react";
import { Filter, ArrowDownToLine, Activity } from "lucide-react";

const SEV_STYLE = {
  error:   { dot: "bg-signal-failed",  text: "text-signal-failed",  label: "ERR" },
  warning: { dot: "bg-signal-queued",  text: "text-signal-queued",  label: "WARN" },
  build:   { dot: "bg-signal-building",text: "text-signal-building", label: "BUILD" },
  deploy:  { dot: "bg-brand",          text: "text-brand",           label: "DPLY" },
  info:    { dot: "bg-zinc-500",       text: "text-zinc-300",        label: "INFO" },
  debug:   { dot: "bg-zinc-700",       text: "text-zinc-500",        label: "DBG" },
};

const FILTERS = [
  { id: "all",     label: "all" },
  { id: "error",   label: "errors" },
  { id: "warning", label: "warnings" },
  { id: "build",   label: "build" },
  { id: "deploy",  label: "deploy" },
  { id: "info",    label: "info" },
];

/**
 * @param {Array<{text:string, severity:string}>|Array<string>} lines
 * @param title
 * @param height
 * @param live   Whether the deployment is currently streaming
 * @param connected  Whether SSE is connected (for the LIVE pulse indicator)
 */
export default function TerminalLog({
  lines = [],
  title = "build.log",
  height = 280,
  live = false,
  connected = false,
}) {
  const [filter, setFilter] = useState("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef(null);

  // Normalize: accept ["text"] OR [{text,severity}]
  const normalized = useMemo(() => {
    return lines.map((l) => {
      if (typeof l === "string") return { text: l, severity: inferSeverity(l) };
      return { text: l.text || "", severity: l.severity || inferSeverity(l.text || "") };
    });
  }, [lines]);

  const counts = useMemo(() => {
    const out = { all: normalized.length, error: 0, warning: 0, build: 0, deploy: 0, info: 0 };
    for (const l of normalized) {
      if (out[l.severity] != null) out[l.severity] += 1;
    }
    return out;
  }, [normalized]);

  const filtered = useMemo(() => {
    if (filter === "all") return normalized;
    return normalized.filter((l) => l.severity === filter);
  }, [normalized, filter]);

  useEffect(() => {
    if (!autoScroll || !containerRef.current) return;
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [filtered, autoScroll]);

  return (
    <div className="terminal flex flex-col" style={{ minHeight: height }} data-testid="terminal-log">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5 bg-black/60">
        <span className="h-2 w-2 rounded-full bg-signal-failed/70" />
        <span className="h-2 w-2 rounded-full bg-signal-queued/70" />
        <span className="h-2 w-2 rounded-full bg-signal-live/70" />
        <span className="ml-2 text-[10px] uppercase tracking-[0.3em] text-zinc-500">{title}</span>

        {live && (
          <span className="ml-3 inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.25em] font-mono text-brand" data-testid="terminal-live">
            <span className="relative h-1.5 w-1.5 rounded-full bg-brand">
              {connected && <span className="absolute -inset-1 rounded-full bg-brand opacity-50 animate-ping-soft" />}
            </span>
            LIVE
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setAutoScroll((v) => !v)}
            className={`text-[10px] uppercase tracking-wider font-mono inline-flex items-center gap-1 ${autoScroll ? "text-brand" : "text-zinc-500 hover:text-white"}`}
            data-testid="terminal-autoscroll"
          >
            <ArrowDownToLine className="h-3 w-3" />
            {autoScroll ? "follow" : "paused"}
          </button>
        </div>
      </div>

      {/* Filter pills */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-white/5 bg-black/40 overflow-x-auto" data-testid="terminal-filters">
        <Filter className="h-3 w-3 text-zinc-500 mr-1 flex-shrink-0" />
        {FILTERS.map((f) => {
          const c = counts[f.id] ?? 0;
          const muted = c === 0 && f.id !== "all";
          const sev = SEV_STYLE[f.id];
          return (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={`text-[10px] uppercase tracking-wider font-mono px-2 py-0.5 border transition flex-shrink-0 inline-flex items-center gap-1.5 ${
                filter === f.id
                  ? "border-brand text-brand bg-brand/10"
                  : muted
                  ? "border-white/5 text-zinc-700"
                  : "border-white/10 text-zinc-400 hover:border-white/30 hover:text-white"
              }`}
              data-testid={`filter-${f.id}`}
            >
              {sev && <span className={`h-1.5 w-1.5 rounded-full ${sev.dot}`} />}
              {f.label}
              <span className="text-[9px] text-zinc-500">{c}</span>
            </button>
          );
        })}
      </div>

      {/* Scrollback area */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-3 text-xs leading-relaxed font-mono"
        onScroll={(e) => {
          const el = e.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
          if (!atBottom && autoScroll) setAutoScroll(false);
        }}
      >
        {filtered.length === 0 ? (
          <div className="text-zinc-600 text-center py-6">
            {normalized.length === 0
              ? <span><span className="text-brand">$</span> awaiting output…</span>
              : <>No <span className="text-brand">{filter}</span> lines match.</>}
          </div>
        ) : (
          filtered.map((l, i) => {
            const sev = SEV_STYLE[l.severity] || SEV_STYLE.info;
            return (
              <div key={i} className="flex items-start gap-2 group hover:bg-white/[0.02] -mx-3 px-3 py-px" data-testid={`log-line-${i}`}>
                <span className="text-zinc-700 pt-0.5 select-none w-7 text-right flex-shrink-0 text-[10px]">
                  {String(i + 1).padStart(3, " ")}
                </span>
                <span className={`pt-0.5 text-[8px] uppercase font-bold tracking-wider px-1 rounded-sm ${sev.text} flex-shrink-0`}>
                  {sev.label}
                </span>
                <span className={`whitespace-pre-wrap break-all ${sev.text}`}>{l.text}</span>
              </div>
            );
          })
        )}
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-white/5 bg-black/60 text-[10px] font-mono text-zinc-600 flex items-center justify-between">
        <span><Activity className="inline h-3 w-3 mr-1" /> {filtered.length} / {normalized.length} lines</span>
        <span>{counts.error > 0 ? <span className="text-signal-failed">{counts.error} errors</span> : "0 errors"} · {counts.warning} warnings</span>
      </div>
    </div>
  );
}

function inferSeverity(text) {
  const t = (text || "").toLowerCase();
  if (/\[(error|fail|fatal)\]/i.test(text) || /\b(fatal|error|failed|exit code [12]|cannot find|could not)\b/.test(t)) return "error";
  if (/\[(warn|warning)\]/i.test(text) || /\bwarn(ing)?\b|deprecated|⚠/.test(t)) return "warning";
  if (/\[build\]/i.test(text) || /(install|build|nixpacks|compil)/.test(t)) return "build";
  if (/\[(deploy|queue|status)\]/i.test(text) || /(deploy|container|health|starting|started)/.test(t)) return "deploy";
  return "info";
}

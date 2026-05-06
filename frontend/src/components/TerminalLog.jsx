export default function TerminalLog({ lines = [], height = 280, title = "build.log" }) {
  return (
    <div className="terminal flex flex-col" style={{ minHeight: height }} data-testid="terminal-log">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5 bg-black/60">
        <span className="h-2 w-2 rounded-full bg-signal-failed/70" />
        <span className="h-2 w-2 rounded-full bg-signal-queued/70" />
        <span className="h-2 w-2 rounded-full bg-signal-live/70" />
        <span className="ml-2 text-[10px] uppercase tracking-[0.3em] text-zinc-500">{title}</span>
      </div>
      <div className="flex-1 overflow-auto p-4 text-xs leading-relaxed">
        {lines.length === 0 ? (
          <div className="text-zinc-600">$ awaiting output...</div>
        ) : (
          lines.map((l, i) => (
            <div key={i} className="font-mono text-brand/80 whitespace-pre-wrap">
              <span className="text-zinc-600 mr-2">{String(i + 1).padStart(3, "0")}</span>
              {l}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

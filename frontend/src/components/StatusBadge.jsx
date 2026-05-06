const STYLES = {
  live: "text-signal-live bg-signal-live/10 border-signal-live/30 shadow-[0_0_12px_rgba(16,185,129,0.18)]",
  building: "text-signal-building bg-signal-building/10 border-signal-building/30 animate-pulse",
  queued: "text-signal-queued bg-signal-queued/10 border-signal-queued/30 border-dashed",
  failed: "text-signal-failed bg-signal-failed/10 border-signal-failed/30",
  pending: "text-zinc-400 bg-white/5 border-white/15",
  active: "text-signal-live bg-signal-live/10 border-signal-live/30",
  paid: "text-signal-live bg-signal-live/10 border-signal-live/30",
  unpaid: "text-signal-failed bg-signal-failed/10 border-signal-failed/30",
};

const LABELS = {
  live: "live",
  building: "building",
  queued: "queued",
  failed: "failed",
  pending: "pending",
  active: "active",
  paid: "paid",
  unpaid: "unpaid",
};

export default function StatusBadge({ status, className = "" }) {
  const s = (status || "pending").toLowerCase();
  const style = STYLES[s] || STYLES.pending;
  const label = LABELS[s] || status;
  return (
    <span
      className={`inline-flex items-center gap-2 px-2.5 py-0.5 text-[11px] font-mono uppercase tracking-wider border rounded-full ${style} ${className}`}
      data-testid={`status-badge-${s}`}
    >
      <span className="relative h-1.5 w-1.5 rounded-full bg-current">
        {s === "live" && (
          <span className="absolute -inset-1 rounded-full bg-current opacity-50 animate-ping-soft" aria-hidden />
        )}
      </span>
      {label}
    </span>
  );
}

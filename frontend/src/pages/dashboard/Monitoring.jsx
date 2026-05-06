import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import StatusBadge from "../../components/StatusBadge";
import { Activity } from "lucide-react";

function uptimeColor(p) {
  if (p == null) return "text-zinc-500";
  if (p >= 99.5) return "text-signal-live";
  if (p >= 95) return "text-signal-queued";
  return "text-signal-failed";
}

export default function Monitoring() {
  const { active } = useWorkspace();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!active) return;
    setLoading(true);
    api.get("/monitoring/overview", { params: { workspace_id: active.id } })
      .then((r) => setRows(r.data))
      .finally(() => setLoading(false));
  }, [active]);

  return (
    <div className="px-6 py-6" data-testid="monitoring-page">
      <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// monitoring</div>
      <h1 className="font-display text-4xl font-semibold tracking-tighter">Health across all apps</h1>
      <p className="mt-1 text-sm text-zinc-400 mb-8">Uptime + response time over the last 24 hours. Checks run every minute.</p>

      {loading ? (
        <div className="text-zinc-500 font-mono text-sm">Sampling…</div>
      ) : rows.length === 0 ? (
        <div className="border border-dashed border-white/10 p-16 text-center">
          <Activity className="h-10 w-10 text-zinc-600 mx-auto mb-4" />
          <h3 className="font-display text-2xl">No apps to monitor yet</h3>
          <p className="mt-2 text-zinc-400">Deploy an app and we'll start watching it automatically.</p>
        </div>
      ) : (
        <div className="border-t border-l border-white/[0.06]">
          <div className="grid grid-cols-12 px-4 py-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 border-r border-b border-white/[0.06]">
            <div className="col-span-4">App</div>
            <div className="col-span-2">Status</div>
            <div className="col-span-3">Uptime 24h</div>
            <div className="col-span-3">Avg response</div>
          </div>
          {rows.map((r) => (
            <Link to={`/app/apps/${r.app_id}`} key={r.app_id} className="grid grid-cols-12 px-4 py-3 border-r border-b border-white/[0.06] hover:bg-white/[0.02] items-center">
              <div className="col-span-4">
                <div className="font-display text-base">{r.name}</div>
                <div className="text-xs font-mono text-zinc-500 truncate">{(r.primary_url || "").replace(/^https?:\/\//, "")}</div>
              </div>
              <div className="col-span-2"><StatusBadge status={r.status} /></div>
              <div className={`col-span-3 font-mono ${uptimeColor(r.uptime_pct)}`}>{r.uptime_pct != null ? `${r.uptime_pct}%` : "—"}</div>
              <div className="col-span-3 font-mono text-zinc-300">{r.avg_response_ms != null ? `${r.avg_response_ms}ms` : "—"}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

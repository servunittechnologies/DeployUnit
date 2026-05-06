import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import AppCard from "../../components/AppCard";
import StatusBadge from "../../components/StatusBadge";
import { Plus, GitBranch, Activity, Globe, BoxesIcon, Boxes } from "lucide-react";

function StatTile({ label, value, accent }) {
  return (
    <div className="flex-1 p-5 border-r border-b border-white/[0.06]">
      <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono">{label}</div>
      <div className={`mt-2 font-display text-3xl tracking-tighter ${accent || ""}`}>{value}</div>
    </div>
  );
}

export default function Overview() {
  const { active } = useWorkspace();
  const [apps, setApps] = useState([]);
  const [overview, setOverview] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!active) return;
    setLoading(true);
    Promise.all([
      api.get("/apps", { params: { workspace_id: active.id } }),
      api.get("/monitoring/overview", { params: { workspace_id: active.id } }),
    ]).then(([a, m]) => {
      setApps(a.data);
      setOverview(m.data);
    }).finally(() => setLoading(false));
  }, [active]);

  const liveCount = apps.filter((a) => a.status === "live").length;
  const buildingCount = apps.filter((a) => a.status === "building" || a.status === "queued").length;
  const failedCount = apps.filter((a) => a.status === "failed").length;
  const avgUptime = overview.length
    ? Math.round(overview.filter((o) => o.uptime_pct != null).reduce((s, o) => s + (o.uptime_pct || 0), 0) /
        Math.max(overview.filter((o) => o.uptime_pct != null).length, 1) * 100) / 100
    : null;

  return (
    <div data-testid="dashboard-overview">
      <div className="px-6 py-6 border-b border-white/[0.06]">
        <div className="flex items-end justify-between">
          <div>
            <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// {active?.name}</div>
            <h1 className="font-display text-4xl font-semibold tracking-tighter">Apps</h1>
          </div>
          <Link
            to="/app/apps/new"
            className="hidden md:inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition shadow-[0_0_18px_rgba(0,229,255,0.25)]"
            data-testid="overview-new-app"
          >
            <Plus className="h-4 w-4" /> New App
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 border-b border-white/[0.06]">
        <StatTile label="Total apps" value={apps.length} />
        <StatTile label="Live" value={liveCount} accent="text-signal-live" />
        <StatTile label="Building / queued" value={buildingCount} accent="text-signal-building" />
        <StatTile label="Avg uptime 24h" value={avgUptime != null ? `${avgUptime}%` : "—"} accent="text-brand" />
      </div>

      {loading ? (
        <div className="p-10 text-zinc-500 font-mono text-sm">Loading apps…</div>
      ) : apps.length === 0 ? (
        <div className="m-6 border border-dashed border-white/10 p-16 text-center" data-testid="empty-apps">
          <Boxes className="h-10 w-10 text-zinc-600 mx-auto mb-4" />
          <h3 className="font-display text-2xl">No apps yet</h3>
          <p className="mt-2 text-zinc-400">Connect a repo and ship your first deployment in under a minute.</p>
          <Link to="/app/apps/new" className="mt-6 inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90">
            <Plus className="h-4 w-4" /> Deploy your first app
          </Link>
        </div>
      ) : (
        <div className="border-l border-t border-white/[0.06] grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {apps.map((app) => <AppCard key={app.id} app={app} />)}
        </div>
      )}

      {failedCount > 0 && (
        <div className="m-6 p-5 border border-signal-failed/30 bg-signal-failed/5 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-signal-failed">// alert</div>
            <div className="mt-1">{failedCount} app{failedCount > 1 ? "s" : ""} failed to deploy. Check the logs.</div>
          </div>
          <Link to="/app/alerts" className="text-sm font-mono text-signal-failed underline">view alerts</Link>
        </div>
      )}
    </div>
  );
}

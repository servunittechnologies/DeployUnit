/**
 * Agency Fleet view — multi-client dashboard with problem-first sorting.
 *
 * Sales pitch: "Manage 50 sites like 1." Bureaus see every workspace they
 * own/co-own with KPIs and apps that bubble broken/down to the top so the
 * worst stuff catches your eye in <1 second.
 *
 * Gated to Agency plans (plan.fleet_view == true). Free/Pro users see a
 * paywall with a Compare-plans CTA.
 */
import { useEffect, useState, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { api, getApiErrorMessage } from "../../lib/api";
import StatusBadge from "../../components/StatusBadge";
import {
  Layers, AlertTriangle, CheckCircle2, ExternalLink,
  RefreshCw, Zap, Search, Coins, Building2, ArrowUpRight, Lock,
} from "lucide-react";
import { toast } from "sonner";

function eur(n) {
  return new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n || 0);
}

export default function Fleet() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/fleet/overview");
      setData(r.data);
    } catch (e) {
      toast.error(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    if (!data?.workspaces) return [];
    const term = q.trim().toLowerCase();
    if (!term) return data.workspaces;
    return data.workspaces
      .map((w) => {
        const ws_match = w.name.toLowerCase().includes(term);
        const apps = (w.apps || []).filter(
          (a) => a.name.toLowerCase().includes(term) || (a.slug || "").toLowerCase().includes(term),
        );
        if (ws_match || apps.length) return { ...w, apps: ws_match ? w.apps : apps };
        return null;
      })
      .filter(Boolean);
  }, [data, q]);

  const runBulkRedeploy = async () => {
    if (!window.confirm(`Redeploy every broken app across ${data.rollup.workspaces} workspace${data.rollup.workspaces === 1 ? "" : "s"}? Capped at 50 per call.`)) return;
    setBulkBusy(true);
    try {
      const r = await api.post("/fleet/bulk-redeploy");
      toast.success(`Queued ${r.data.queued} redeploy${r.data.queued === 1 ? "" : "s"}`);
      setTimeout(load, 2500);
    } catch (e) {
      toast.error(getApiErrorMessage(e));
    } finally { setBulkBusy(false); }
  };

  if (loading && !data) {
    return <div className="p-6 text-sm font-mono text-zinc-500">Loading workspaces…</div>;
  }
  if (!data) return null;

  const r = data.rollup;
  const wsCount = data.workspaces.length;
  const healthPct = r.apps_total ? Math.round((r.apps_live / r.apps_total) * 100) : 100;

  return (
    <div className="px-6 py-6 space-y-8" data-testid="fleet-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// workspaces</div>
          <h1 className="font-display text-4xl font-semibold tracking-tighter">
            {wsCount === 0 ? "Create a workspace to get started." : wsCount === 1 ? "Your workspace at a glance." : "All your workspaces."}
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            {wsCount <= 1
              ? "Apps sorted with broken ones at the top so the worst stuff catches your eye in <1 second."
              : "Sorted by where you're bleeding — broken apps first."} Refreshed at {new Date(data.generated_at || Date.now()).toLocaleTimeString()}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-white/10 hover:border-brand/50 text-xs font-mono"
            data-testid="fleet-refresh"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> refresh
          </button>
          {r.apps_broken > 0 && (
            <button
              onClick={runBulkRedeploy}
              disabled={bulkBusy}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-signal-failed/15 border border-signal-failed/40 text-signal-failed hover:bg-signal-failed/25 text-sm font-medium disabled:opacity-50"
              data-testid="fleet-bulk-redeploy"
            >
              <Zap className={`h-3.5 w-3.5 ${bulkBusy ? "animate-pulse" : ""}`} /> Redeploy {r.apps_broken} broken
            </button>
          )}
        </div>
      </div>

      {/* Rollup KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-px bg-white/[0.06] border border-white/[0.06]" data-testid="fleet-rollup">
        <Kpi icon={<Building2 className="h-4 w-4" />} label="Workspaces" value={r.workspaces} />
        <Kpi icon={<Layers className="h-4 w-4" />} label="Apps total" value={r.apps_total} />
        <Kpi icon={<AlertTriangle className="h-4 w-4 text-signal-failed" />} label="Broken" value={r.apps_broken} tone={r.apps_broken > 0 ? "danger" : "muted"} />
        <Kpi icon={<CheckCircle2 className="h-4 w-4 text-signal-live" />} label="Live" value={`${r.apps_live} (${healthPct}%)`} tone="live" />
        <Kpi icon={<Coins className="h-4 w-4 text-brand" />} label="Monthly recurring" value={eur(r.monthly_eur)} tone="brand" />
      </div>

      {/* Search */}
      <div className="flex items-center gap-2 border border-white/10 px-3 py-2 max-w-sm">
        <Search className="h-3.5 w-3.5 text-zinc-500" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="filter workspaces or apps…"
          className="flex-1 bg-transparent text-sm font-mono focus:outline-none"
          data-testid="fleet-search"
        />
      </div>

      {/* Workspaces */}
      <div className="space-y-4">
        {filtered.length === 0 && q && (
          <div className="text-sm font-mono text-zinc-500">No workspaces or apps match "{q}".</div>
        )}
        {filtered.map((ws) => (
          <WorkspaceCard key={ws.id} ws={ws} />
        ))}
      </div>
    </div>
  );
}

function Kpi({ icon, label, value, tone = "" }) {
  const toneClass = {
    danger: "text-signal-failed",
    live: "text-signal-live",
    brand: "text-brand",
    muted: "text-zinc-500",
  }[tone] || "text-zinc-200";
  return (
    <div className="bg-background p-4">
      <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500">
        {icon}
        {label}
      </div>
      <div className={`mt-2 font-display text-2xl tracking-tighter ${toneClass}`}>{value}</div>
    </div>
  );
}

function WorkspaceCard({ ws }) {
  const [open, setOpen] = useState(ws.kpi.apps_broken > 0); // expand when broken
  const pain = ws.kpi.apps_broken;
  const ringClass = pain > 0 ? "ring-1 ring-signal-failed/40" : "";

  return (
    <section
      className={`border border-white/[0.08] bg-[#0a0a0a] ${ringClass}`}
      data-testid={`fleet-ws-${ws.id}`}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-4 p-5 flex-wrap hover:bg-white/[0.02] transition-colors text-left"
        data-testid={`fleet-ws-toggle-${ws.id}`}
      >
        <div className="flex items-center gap-3 min-w-[200px]">
          <Building2 className="h-4 w-4 text-zinc-500" />
          <div>
            <div className="text-sm font-medium">{ws.name}</div>
            <div className="text-[11px] font-mono text-zinc-500 mt-0.5">
              {ws.type} · {ws.plan.name} · €{ws.plan.price}/mo · {ws.credits_balance} cr
            </div>
          </div>
        </div>
        <div className="flex items-center gap-5 text-xs font-mono">
          <span className="text-zinc-500"><span className="text-zinc-300">{ws.kpi.apps_total}</span> apps</span>
          {pain > 0 ? (
            <span className="text-signal-failed inline-flex items-center gap-1"><AlertTriangle className="h-3 w-3" /> {pain} broken</span>
          ) : (
            <span className="text-signal-live inline-flex items-center gap-1"><CheckCircle2 className="h-3 w-3" /> all live</span>
          )}
          <ArrowUpRight className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
        </div>
      </button>

      {open && (
        <div className="border-t border-white/[0.06]" data-testid={`fleet-ws-apps-${ws.id}`}>
          {ws.apps.length === 0 && (
            <div className="p-5 text-xs font-mono text-zinc-500">No apps in this workspace yet.</div>
          )}
          {ws.apps.map((app) => (
            <AppRow key={app.id} app={app} />
          ))}
        </div>
      )}
    </section>
  );
}

function AppRow({ app }) {
  const isDown = app.health === "down";
  const isFailed = ["failed", "error"].includes((app.status || "").toLowerCase());
  const rowTone = (isDown || isFailed) ? "bg-signal-failed/[0.04]" : "";
  return (
    <Link
      to={`/app/apps/${app.id}`}
      className={`grid grid-cols-12 gap-4 items-center px-5 py-3 border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.03] transition-colors ${rowTone}`}
      data-testid={`fleet-app-${app.id}`}
    >
      <div className="col-span-4 flex items-center gap-2 min-w-0">
        {(isDown || isFailed) && <AlertTriangle className="h-3 w-3 text-signal-failed shrink-0" />}
        <div className="truncate">
          <div className="text-sm truncate">{app.name}</div>
          <div className="text-[10px] font-mono text-zinc-500 truncate">{app.branch} · {app.framework || "node"}</div>
        </div>
      </div>
      <div className="col-span-2"><StatusBadge status={app.status} /></div>
      <div className="col-span-2 text-xs font-mono text-zinc-500">
        {app.health === "ok" ? <span className="text-signal-live">● up</span> : app.health === "down" ? <span className="text-signal-failed">● down</span> : "—"}
        {app.latency_ms != null && <span className="ml-1 text-zinc-400">{app.latency_ms}ms</span>}
      </div>
      <div className="col-span-3 truncate">
        {app.primary_url ? (
          <span className="text-xs font-mono text-brand inline-flex items-center gap-1 truncate">
            {app.primary_url.replace(/^https?:\/\//, "")}
            <ExternalLink className="h-3 w-3 shrink-0" />
          </span>
        ) : (
          <span className="text-xs font-mono text-zinc-500">no domain yet</span>
        )}
      </div>
      <div className="col-span-1 text-right text-[11px] font-mono text-zinc-500">
        {app.last_deploy_at ? new Date(app.last_deploy_at).toLocaleDateString() : "—"}
      </div>
    </Link>
  );
}

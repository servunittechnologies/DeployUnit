import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Activity, Cpu, MemoryStick, HardDrive, Clock, Zap, GitCommit, AlertTriangle, TrendingUp } from "lucide-react";
import AppMetricsCharts from "./AppMetricsCharts";
import InfoTip from "./InfoTip";

const WINDOWS = [
  { id: "1h",  label: "Last hour"  },
  { id: "24h", label: "Last 24h"   },
  { id: "7d",  label: "Last 7 days" },
  { id: "30d", label: "Last 30 days" },
];

const STATUS_COLOR = {
  live:     "#10b981",
  running:  "#10b981",
  building: "#f59e0b",
  queued:   "#f59e0b",
  failed:   "#ef4444",
  down:     "#ef4444",
  unknown:  "#52525b",
};

function fmtMs(v) {
  if (v == null) return "—";
  if (v < 1000) return `${v} ms`;
  return `${(v / 1000).toFixed(2)} s`;
}

function fmtMemory(mb) {
  if (mb >= 1024) return `${(mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)} GB`;
  return `${mb} MB`;
}

function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}


/**
 * The Analytics / Monitoring section for one app. Renders the existing
 * monitoring data (uptime / response time / status timeline) plus the new
 * resource allocation panel.
 */
export default function AppAnalyticsPanel({ appId }) {
  const [window, setWindow] = useState("24h");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    api.get(`/apps/${appId}/analytics?window=${window}`).then((r) => setData(r.data)).finally(() => setLoading(false));
    const t = setInterval(() => {
      api.get(`/apps/${appId}/analytics?window=${window}`).then((r) => setData(r.data)).catch(() => {});
    }, 30000);
    return () => clearInterval(t);
  }, [appId, window]);

  if (loading && !data) return <div className="p-10 font-mono text-sm text-zinc-500" data-testid="analytics-loading">Loading analytics…</div>;
  if (!data) return null;

  const s = data.summary || {};
  const r = data.resources;

  return (
    <div className="p-6 space-y-6" data-testid="analytics-panel">
      {/* Header + window switcher */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-brand" />
            <h2 className="font-display text-xl">Usage & monitoring</h2>
          </div>
          <p className="text-xs font-mono text-zinc-500 mt-1">
            Live HTTP probes every 60s · resource allocation reflects container limits enforced on the build engine.
          </p>
        </div>
        <div className="flex gap-1 border border-white/10" role="tablist">
          {WINDOWS.map((w) => (
            <button
              key={w.id}
              onClick={() => setWindow(w.id)}
              className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors ${
                window === w.id ? "bg-brand text-brand-fg" : "text-zinc-400 hover:text-white"
              }`}
              data-testid={`analytics-window-${w.id}`}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {/* Top KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.06] border border-white/[0.06]">
        <KpiTile
          icon={Activity} label="Uptime"
          value={s.uptime_pct != null ? `${s.uptime_pct}%` : "—"}
          hint={`${s.samples || 0} probes in window`}
          color={(s.uptime_pct ?? 100) >= 99 ? "text-signal-live" : (s.uptime_pct ?? 100) >= 95 ? "text-signal-queued" : "text-signal-failed"}
        />
        <KpiTile
          icon={Clock} label="Avg response"
          value={fmtMs(s.avg_response_ms)}
          hint={`p95: ${fmtMs(s.p95_response_ms)}`}
        />
        <KpiTile
          icon={GitCommit} label="Deployments"
          value={`${s.deployments || 0}`}
          hint={`${s.build_minutes || 0} min built`}
        />
        <KpiTile
          icon={Zap} label="Status now"
          value={data.status || "?"}
          hint={data.primary_url ? "serving" : "no URL"}
          color={data.status === "live" ? "text-signal-live" : data.status === "failed" ? "text-signal-failed" : "text-zinc-300"}
        />
      </div>

      {/* Live container metrics from the agent */}
      <section data-testid="metrics-section">
        <AppMetricsCharts appId={appId} onInstallAgent={() => navigate("/app/admin?tab=integrations")} />
      </section>

      {/* Response time chart */}
      <section className="border border-white/[0.06]">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">// response time</div>
            <div className="text-sm text-zinc-300 mt-0.5">milliseconds per check</div>
          </div>
          {s.p95_response_ms && (
            <div className="text-xs font-mono text-zinc-500">peak p95: {fmtMs(s.p95_response_ms)}</div>
          )}
        </div>
        <div className="p-4">
          <ResponseChart series={data.series?.response_ms || []} testId="chart-response" />
        </div>
      </section>

      {/* Uptime + status timeline */}
      <section className="border border-white/[0.06]">
        <div className="px-4 py-3 border-b border-white/[0.06]">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">// status timeline</div>
          <div className="text-sm text-zinc-300 mt-0.5">healthy / down / building windows in this period</div>
        </div>
        <div className="p-4">
          <StatusTimelineBar
            timeline={data.status_timeline || []}
            since={data.since}
            now={data.now}
            testId="timeline"
          />
          <div className="mt-3 flex items-center gap-4 text-[10px] font-mono uppercase tracking-wider text-zinc-500">
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-3 inline-block bg-signal-live" /> live</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-3 inline-block bg-signal-queued" /> building</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-3 inline-block bg-signal-failed" /> failed / down</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-3 inline-block bg-zinc-700" /> unknown</span>
          </div>
        </div>
      </section>

      {/* Resource allocation */}
      {r && (
        <section className="border border-white/[0.06]">
          <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">// allocated resources</div>
              <div className="text-sm text-zinc-300 mt-0.5">enforced on the container at deploy time</div>
            </div>
            <a href="#" onClick={(e) => { e.preventDefault(); document.querySelector('[data-testid="tab-resources"]')?.click(); }}
               className="text-xs font-mono text-brand hover:underline">manage →</a>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-white/[0.06]">
            <ResourceAllocTile icon={Cpu} label="CPU" used={`${r.effective.cpu_vcpu.toFixed(2)} vCPU`} addon={r.addons.cpu_vcpu > 0 ? `+${r.addons.cpu_vcpu}` : null} />
            <ResourceAllocTile icon={MemoryStick} label="Memory" used={fmtMemory(r.effective.memory_mb)} addon={r.addons.memory_mb > 0 ? `+${r.addons.memory_mb} MB` : null} />
            <ResourceAllocTile icon={HardDrive} label="Storage" used={fmtMemory(r.effective.storage_mb)} addon={r.addons.storage_mb > 0 ? `+${r.addons.storage_mb / 1024} GB` : null} />
          </div>
          {r.monthly_cost_credits > 0 && (
            <div className="px-4 py-2 text-xs font-mono text-zinc-500 border-t border-white/[0.06]">
              addon cost: <span className="text-brand">{r.monthly_cost_credits} cr/mo</span>
              {r.addons_active_since && ` · active since ${fmtTime(r.addons_active_since)}`}
            </div>
          )}
        </section>
      )}

      {/* Deployment breakdown */}
      {s.deploys_by_status && (
        <section className="border border-white/[0.06] p-4">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-3">// deployments in window</div>
          <div className="flex items-center gap-2 flex-wrap">
            {Object.entries(s.deploys_by_status).map(([st, n]) => n > 0 ? (
              <span key={st} className="inline-flex items-center gap-1.5 px-2 py-1 border border-white/10 text-xs font-mono">
                <span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLOR[st] || STATUS_COLOR.unknown }} />
                {st}: {n}
              </span>
            ) : null)}
            <span className="text-xs font-mono text-zinc-500 ml-2">{s.build_minutes || 0} min total build time</span>
          </div>
        </section>
      )}
    </div>
  );
}


function KpiTile({ icon: Icon, label, value, hint, color = "text-zinc-100" }) {
  return (
    <div className="bg-background p-4">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">
        <Icon className="h-3 w-3 text-brand" /> {label}
      </div>
      <div className={`font-display text-2xl mt-2 tracking-tight ${color}`}>{value}</div>
      <div className="text-[10px] font-mono text-zinc-500 mt-1">{hint}</div>
    </div>
  );
}

function ResourceAllocTile({ icon: Icon, label, used, addon }) {
  return (
    <div className="bg-background p-4">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">
        <Icon className="h-3 w-3 text-brand" /> {label}
      </div>
      <div className="font-display text-xl mt-1.5 tracking-tight">{used}</div>
      {addon ? (
        <div className="text-[10px] font-mono text-brand mt-0.5">addon {addon}</div>
      ) : (
        <div className="text-[10px] font-mono text-zinc-500 mt-0.5">plan default only</div>
      )}
    </div>
  );
}

/**
 * SVG line chart for response time. Uses the bucketed series straight from
 * the API; null values become gaps in the line.
 */
function ResponseChart({ series, testId }) {
  if (!series.length) {
    return <div className="h-32 grid place-items-center text-xs font-mono text-zinc-600">No probe data in this window yet.</div>;
  }
  const W = 800;
  const H = 140;
  const PAD = 24;
  const values = series.map((s) => s.avg_ms).filter((v) => v != null);
  const max = Math.max(1, ...values);
  const min = 0;
  const step = (W - 2 * PAD) / Math.max(1, series.length - 1);

  const points = series.map((s, i) => {
    if (s.avg_ms == null) return null;
    const x = PAD + i * step;
    const y = H - PAD - ((s.avg_ms - min) / (max - min)) * (H - 2 * PAD);
    return { x, y, val: s.avg_ms, t: s.t };
  });
  const segments = [];
  let cur = [];
  points.forEach((p) => {
    if (p) cur.push(p);
    else if (cur.length) { segments.push(cur); cur = []; }
  });
  if (cur.length) segments.push(cur);

  return (
    <div data-testid={testId}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-32">
        {/* y-axis label */}
        <text x={4} y={14} fontSize="9" fill="#52525b" fontFamily="monospace">{Math.round(max)} ms</text>
        <text x={4} y={H - 8} fontSize="9" fill="#52525b" fontFamily="monospace">0 ms</text>
        <line x1={PAD} y1={H - PAD} x2={W - 4} y2={H - PAD} stroke="rgba(255,255,255,0.08)" />
        {/* line segments (handles null gaps) */}
        {segments.map((seg, i) => (
          <polyline
            key={i}
            points={seg.map((p) => `${p.x},${p.y}`).join(" ")}
            stroke="#00e5ff" fill="none" strokeWidth="1.5"
          />
        ))}
        {/* dots */}
        {points.filter(Boolean).map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={1.5} fill="#00e5ff">
            <title>{p.val} ms @ {fmtTime(p.t)}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

/**
 * Render the status_timeline ranges as horizontal coloured stripes spanning
 * the [since, now] window. Visually like GitHub Actions / Vercel status bar.
 */
function StatusTimelineBar({ timeline, since, now, testId }) {
  if (!timeline.length || !since || !now) {
    return <div className="h-10 grid place-items-center text-xs font-mono text-zinc-600">No status data yet in this window.</div>;
  }
  const sinceTs = new Date(since).getTime();
  const nowTs = new Date(now).getTime();
  const total = Math.max(1, nowTs - sinceTs);
  return (
    <div className="relative h-8 w-full flex border border-white/10 overflow-hidden" data-testid={testId}>
      {timeline.map((r, i) => {
        const fromTs = new Date(r.from).getTime();
        const toTs = new Date(r.to).getTime();
        const left = Math.max(0, fromTs - sinceTs);
        const width = Math.max(0, toTs - fromTs);
        const pct = (width / total) * 100;
        return (
          <div
            key={i}
            className="h-full"
            style={{ width: `${pct}%`, background: STATUS_COLOR[r.status] || STATUS_COLOR.unknown }}
            title={`${r.status} · ${fmtTime(r.from)} → ${fmtTime(r.to)}`}
            data-testid={`timeline-segment-${r.status}`}
          />
        );
      })}
    </div>
  );
}


/**
 * Account-wide rollup — shown on the Overview homepage so the user sees
 * total resources / credit burn / build minutes consumed.
 */
export function AccountAnalyticsPanel() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/account/analytics?window=30d").then((r) => setData(r.data)).catch(() => setData(null));
  }, []);

  if (!data) return null;
  const t = data.totals || {};
  const c = data.credits || {};
  const burnKinds = Object.entries(c.burn_by_kind || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="border border-white/[0.06]" data-testid="account-analytics">
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">// last 30 days · account-wide</div>
          <div className="text-sm text-zinc-300 mt-0.5">What you're using across every Workspace you own</div>
        </div>
        <TrendingUp className="h-4 w-4 text-brand" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.06]">
        <KpiTile icon={Activity} label="Apps live" value={`${t.apps_live || 0}`} hint={`of ${t.apps_total || 0} total`} />
        <KpiTile icon={Cpu}      label="CPU"        value={`${t.cpu_allocated_vcpu || 0} vCPU`} hint="allocated total" />
        <KpiTile icon={MemoryStick} label="Memory"  value={fmtMemory(t.memory_allocated_mb || 0)}  hint="allocated total" />
        <KpiTile icon={HardDrive} label="Storage"   value={fmtMemory(t.storage_allocated_mb || 0)} hint="allocated total" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 flex items-center">
            Deployments
            <InfoTip>
              How many times this app was built &amp; pushed in the selected window.
              Includes manual redeploys and auto-deploys from GitHub pushes.
            </InfoTip>
          </div>
          <div className="font-display text-2xl mt-1">{t.deployments_in_window || 0}</div>
          <div className="text-[10px] font-mono text-zinc-500">{t.build_minutes_in_window || 0} build minutes</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 flex items-center">
            Credit burn
            <InfoTip>
              Credits this app consumed in the selected window. Burn comes from{" "}
              <b className="text-zinc-200">SMS alerts</b>, <b className="text-zinc-200">build overages</b> (builds longer than your plan's free minutes),
              and <b className="text-zinc-200">resource overages</b> (CPU/RAM/storage above your plan's quota).
              Resource cost is shown separately as "Resource cost / month".
            </InfoTip>
          </div>
          <div className="font-display text-2xl mt-1 text-signal-failed">{c.burn_total || 0} <span className="text-xs text-zinc-500 font-mono">cr</span></div>
          <div className="text-[10px] font-mono text-zinc-500">{burnKinds.length} {burnKinds.length === 1 ? "category" : "categories"} · see breakdown below</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 flex items-center">
            Resource cost / month
            <InfoTip>
              The monthly credit cost of CPU + memory + storage this app is allocated, regardless of usage.
              This is what you'd pay even if no traffic hit the app.
            </InfoTip>
          </div>
          <div className="font-display text-2xl mt-1 text-brand">{t.monthly_resource_cost_credits || 0} <span className="text-xs text-zinc-500 font-mono">cr</span></div>
          <div className="text-[10px] font-mono text-zinc-500">recurring add-ons</div>
        </div>
      </div>
      {burnKinds.length > 0 && (
        <div className="px-4 py-3 border-t border-white/[0.06]">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2">Burn by category</div>
          <div className="space-y-1.5">
            {burnKinds.map(([k, v]) => {
              const pct = (c.burn_total || 0) > 0 ? (v / c.burn_total) * 100 : 0;
              return (
                <div key={k} className="flex items-center gap-3 text-xs font-mono">
                  <div className="w-32 text-zinc-400 truncate">{k}</div>
                  <div className="flex-1 h-2 bg-white/[0.05] overflow-hidden">
                    <div className="h-full bg-signal-failed/60" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="w-20 text-right text-zinc-300">{v} cr</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

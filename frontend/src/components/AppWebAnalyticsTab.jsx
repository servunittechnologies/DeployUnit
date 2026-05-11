import { useEffect, useMemo, useState } from "react";
import { api, getApiErrorMessage } from "../lib/api";
import {
  Activity, BarChart3, Eye, Gauge, Globe2, Lock, Loader2, Map,
  Monitor, RefreshCcw, Smartphone, Sparkles, Tablet, Terminal, Users, Zap,
  Copy as CopyIcon, Check,
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, ResponsiveContainer, Tooltip,
  XAxis, YAxis, CartesianGrid, LineChart, Line,
} from "recharts";
import { toast } from "sonner";

const SUB_TABS = [
  { id: "visitors", label: "Visitors", icon: Users },
  { id: "speed", label: "Speed Insights", icon: Zap, gated: "pagespeed" },
  { id: "heatmaps", label: "Heatmaps", icon: Activity, gated: "heatmaps" },
  { id: "setup", label: "Setup", icon: Terminal },
];

const WINDOWS = [
  { id: "24h", label: "24h" },
  { id: "7d", label: "7d" },
  { id: "30d", label: "30d" },
  { id: "90d", label: "90d" },
];

function fmtNum(n) {
  if (n == null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return String(n);
}

function fmtMs(ms) {
  if (ms == null) return "—";
  if (ms >= 1000) return (ms / 1000).toFixed(2) + "s";
  return Math.round(ms) + "ms";
}

function scoreColor(s) {
  if (s == null) return "text-zinc-500";
  if (s >= 90) return "text-signal-success";
  if (s >= 50) return "text-signal-queued";
  return "text-signal-failed";
}

function ScoreCircle({ score, size = 64, label }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const pct = (score ?? 0) / 100;
  return (
    <div className="flex flex-col items-center" data-testid={`pagespeed-score-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="currentColor"
                className="text-white/[0.06]" strokeWidth="4" fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke="currentColor"
                className={scoreColor(score)} strokeWidth="4" fill="none"
                strokeDasharray={c} strokeDashoffset={c * (1 - pct)}
                strokeLinecap="round" transform={`rotate(-90 ${size / 2} ${size / 2})`} />
        <text x="50%" y="52%" textAnchor="middle" dominantBaseline="middle"
              className={`fill-current ${scoreColor(score)} font-mono`} fontSize={size * 0.32}>
          {score ?? "—"}
        </text>
      </svg>
      <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mt-1.5">{label}</div>
    </div>
  );
}

function KPI({ label, value, hint }) {
  return (
    <div className="border border-white/[0.06] p-4 bg-elevated/30">
      <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500">{label}</div>
      <div className="font-display text-2xl tracking-tight mt-1.5">{value}</div>
      {hint && <div className="text-[11px] font-mono text-zinc-500 mt-1">{hint}</div>}
    </div>
  );
}

function PlanLockNotice({ requiredPlan, label }) {
  return (
    <div className="p-10 text-center border border-dashed border-white/10 bg-elevated/30" data-testid="analytics-plan-locked">
      <Lock className="h-8 w-8 text-zinc-500 mx-auto mb-3" />
      <div className="font-display text-lg">{label} requires the {requiredPlan} plan</div>
      <div className="text-sm text-zinc-400 mt-2 max-w-md mx-auto">
        Upgrade your account to unlock {label.toLowerCase()}.
      </div>
      <a href="/dashboard/account/billing"
         className="inline-block mt-4 px-4 py-2 bg-brand text-brand-fg text-sm font-medium hover:bg-brand/90"
         data-testid="analytics-upgrade-link">
        View plans →
      </a>
    </div>
  );
}

function CopyBlock({ text, testId }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
      toast.success("Copied");
    } catch { toast.error("Copy failed"); }
  };
  return (
    <div className="flex items-stretch gap-2">
      <pre className="flex-1 bg-black/40 px-3 py-2 text-xs font-mono text-zinc-200 overflow-x-auto whitespace-pre-wrap break-all border border-white/[0.04]">
        {text}
      </pre>
      <button
        onClick={copy}
        className="px-3 py-2 border border-white/15 hover:border-brand text-xs font-mono inline-flex items-center gap-1.5"
        data-testid={testId}
      >
        {copied ? <Check className="h-3 w-3 text-signal-success" /> : <CopyIcon className="h-3 w-3" />}
        {copied ? "copied" : "copy"}
      </button>
    </div>
  );
}

// ─────────────────────── Visitors ───────────────────────
function VisitorsPane({ appId }) {
  const [window, setWindow] = useState("7d");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get(`/apps/${appId}/web-analytics`, { params: { window } });
      setData(r.data);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [appId, window]);

  if (loading && !data) return <div className="p-10 text-center text-zinc-500"><Loader2 className="h-5 w-5 animate-spin inline mr-2" /> Loading analytics…</div>;

  const totals = data?.totals || {};
  const series = (data?.series || []).map((s) => ({ ...s, label: s.bucket?.slice(5) }));

  return (
    <div className="space-y-6" data-testid="analytics-visitors">
      <div className="flex items-center justify-between">
        <div className="inline-flex border border-white/[0.06]">
          {WINDOWS.map((w) => (
            <button key={w.id} onClick={() => setWindow(w.id)}
              data-testid={`analytics-window-${w.id}`}
              className={`px-3 py-1.5 text-xs font-mono border-r border-white/[0.06] last:border-r-0 ${window === w.id ? "bg-brand/15 text-brand" : "text-zinc-400 hover:text-zinc-200"}`}>
              {w.label}
            </button>
          ))}
        </div>
        <button onClick={load} className="text-xs font-mono text-zinc-400 hover:text-brand inline-flex items-center gap-1.5">
          <RefreshCcw className="h-3 w-3" /> refresh
        </button>
      </div>

      {!data?.have_data ? (
        <div className="p-10 text-center border border-dashed border-white/10 bg-elevated/30" data-testid="analytics-no-data">
          <BarChart3 className="h-8 w-8 text-zinc-500 mx-auto mb-3" />
          <div className="font-display text-lg">No pageviews yet</div>
          <div className="text-sm text-zinc-400 mt-2 max-w-md mx-auto">
            Add the tracking snippet to your site (see Setup tab) and visit a page to see live analytics here.
          </div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPI label="Pageviews" value={fmtNum(totals.pageviews)} />
            <KPI label="Unique visitors" value={fmtNum(totals.uniques)} />
            <KPI label="Views / visitor" value={totals.views_per_visitor?.toFixed?.(2) ?? "—"} />
            <KPI label="Top country" value={data.top_countries?.[0]?.key ?? "—"}
                 hint={data.top_countries?.[0] ? `${fmtNum(data.top_countries[0].n)} views` : null} />
          </div>

          <div className="border border-white/[0.06] p-4">
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-3">Traffic over time</div>
            <div style={{ width: "100%", height: 220 }}>
              <ResponsiveContainer>
                <AreaChart data={series}>
                  <CartesianGrid stroke="#ffffff10" vertical={false} />
                  <XAxis dataKey="label" stroke="#71717a" fontSize={11} />
                  <YAxis stroke="#71717a" fontSize={11} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: "#0a0a0a", border: "1px solid #ffffff20", fontSize: 12 }} />
                  <Area type="monotone" dataKey="pv" name="Pageviews" stroke="#3ab2ff" fill="#3ab2ff22" />
                  <Area type="monotone" dataKey="uniques" name="Visitors" stroke="#22c55e" fill="#22c55e22" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <TopList title="Top pages" rows={data.top_pages} icon={Eye} testId="top-pages" />
            <TopList title="Top referrers" rows={data.top_referrers} icon={Globe2} testId="top-referrers"
                     emptyLabel="No external referrers yet" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <DeviceBreakdown rows={data.devices} />
            <TopList title="Browsers" rows={data.browsers} testId="browsers" />
            <TopList title="Top countries" rows={data.top_countries} testId="top-countries" icon={Map} />
          </div>
        </>
      )}
    </div>
  );
}

function TopList({ title, rows, icon: Icon, testId, emptyLabel = "—" }) {
  const total = (rows || []).reduce((a, b) => a + (b.n || 0), 0) || 1;
  return (
    <div className="border border-white/[0.06]" data-testid={`analytics-list-${testId}`}>
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
        {Icon && <Icon className="h-3.5 w-3.5 text-zinc-500" />}
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-400">{title}</div>
      </div>
      {(!rows || rows.length === 0) && <div className="p-4 text-xs font-mono text-zinc-500">{emptyLabel}</div>}
      {rows && rows.map((r) => {
        const pct = ((r.n / total) * 100).toFixed(1);
        return (
          <div key={r.key} className="relative px-4 py-2 border-b border-white/[0.06] last:border-b-0">
            <div className="absolute inset-y-0 left-0 bg-brand/8" style={{ width: `${pct}%` }} />
            <div className="relative flex items-center justify-between text-xs font-mono">
              <span className="truncate text-zinc-200">{r.key}</span>
              <span className="text-zinc-500 ml-2 shrink-0">{fmtNum(r.n)} · {pct}%</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DeviceBreakdown({ rows }) {
  const total = (rows || []).reduce((a, b) => a + (b.n || 0), 0) || 1;
  const byKey = Object.fromEntries((rows || []).map((r) => [r.key, r.n]));
  const dev = [
    { key: "desktop", icon: Monitor },
    { key: "mobile", icon: Smartphone },
    { key: "tablet", icon: Tablet },
  ];
  return (
    <div className="border border-white/[0.06]" data-testid="analytics-list-devices">
      <div className="px-4 py-3 border-b border-white/[0.06]">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-400">Devices</div>
      </div>
      <div className="p-4 space-y-3">
        {dev.map((d) => {
          const n = byKey[d.key] || 0;
          const pct = ((n / total) * 100).toFixed(0);
          return (
            <div key={d.key} className="flex items-center gap-3 text-xs font-mono">
              <d.icon className="h-3.5 w-3.5 text-zinc-500" />
              <div className="flex-1 capitalize">{d.key}</div>
              <div className="w-24 h-1.5 bg-white/[0.06]"><div className="h-full bg-brand" style={{ width: `${pct}%` }} /></div>
              <div className="text-zinc-500 w-12 text-right">{pct}%</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────── Speed Insights ───────────────────────
function SpeedPane({ appId, features }) {
  const [data, setData] = useState(null);
  const [hist, setHist] = useState([]);
  const [running, setRunning] = useState(false);
  const [strategy, setStrategy] = useState("mobile");

  const load = async () => {
    try {
      const [latest, history] = await Promise.all([
        api.get(`/apps/${appId}/pagespeed/latest`),
        api.get(`/apps/${appId}/pagespeed/history`, { params: { days: 30 } }),
      ]);
      setData(latest.data);
      setHist(history.data?.rows || []);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };
  useEffect(() => { if (features?.pagespeed) load(); /* eslint-disable-next-line */ }, [appId, features?.pagespeed]);

  const run0 = data?.run;
  const variant = run0?.[strategy];
  const scores = variant?.scores || {};
  const lab = variant?.lab_metrics || {};
  const field = variant?.field_cwv || {};

  const histSeries = useMemo(() => hist.map((r) => ({
    label: r.ran_at?.slice(5, 10),
    perf: r?.[strategy]?.scores?.performance ?? null,
    a11y: r?.[strategy]?.scores?.accessibility ?? null,
    seo: r?.[strategy]?.scores?.seo ?? null,
    bp: r?.[strategy]?.scores?.best_practices ?? null,
  })), [hist, strategy]);

  if (!features?.pagespeed) return <PlanLockNotice requiredPlan="Pro" label="Speed Insights" />;

  const run = async () => {
    setRunning(true);
    try {
      const r = await api.post(`/apps/${appId}/pagespeed/run`);
      setData({ have_data: true, run: r.data });
      toast.success("Audit complete");
      load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setRunning(false); }
  };

  return (
    <div className="space-y-6" data-testid="analytics-speed">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex border border-white/[0.06]">
          {["mobile", "desktop"].map((s) => (
            <button key={s} onClick={() => setStrategy(s)}
              data-testid={`pagespeed-strategy-${s}`}
              className={`px-3 py-1.5 text-xs font-mono border-r border-white/[0.06] last:border-r-0 capitalize ${strategy === s ? "bg-brand/15 text-brand" : "text-zinc-400 hover:text-zinc-200"}`}>
              {s}
            </button>
          ))}
        </div>
        <button onClick={run} disabled={running}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg text-sm font-medium hover:bg-brand/90 disabled:opacity-50"
          data-testid="pagespeed-run-now">
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {running ? "Auditing…" : "Run audit"}
        </button>
      </div>

      {!data?.have_data ? (
        <div className="p-10 text-center border border-dashed border-white/10 bg-elevated/30" data-testid="pagespeed-no-data">
          <Gauge className="h-8 w-8 text-zinc-500 mx-auto mb-3" />
          <div className="font-display text-lg">No audits yet</div>
          <div className="text-sm text-zinc-400 mt-2 max-w-md mx-auto">
            Click "Run audit" to grade this app's performance, accessibility, best-practices and SEO via Google Lighthouse.
            Daily audits run automatically after the first one.
          </div>
        </div>
      ) : (
        <>
          <div className="border border-white/[0.06] p-6">
            <div className="flex items-baseline justify-between mb-4">
              <div>
                <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Lighthouse scores · {strategy}</div>
                <div className="text-xs font-mono text-zinc-500 mt-1">{variant?.final_url || run0?.url}</div>
              </div>
              <div className="text-[10px] font-mono text-zinc-500">
                last run: {run0?.ran_at ? new Date(run0.ran_at).toLocaleString() : "—"}
              </div>
            </div>
            <div className="flex flex-wrap gap-8 items-center justify-around">
              <ScoreCircle score={scores.performance} label="Performance" />
              <ScoreCircle score={scores.accessibility} label="Accessibility" />
              <ScoreCircle score={scores.best_practices} label="Best Practices" />
              <ScoreCircle score={scores.seo} label="SEO" />
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <KPI label="LCP" value={fmtMs(lab.lcp_ms)} hint={field.lcp ? `field p75: ${fmtMs(field.lcp.p75)}` : "lab"} />
            <KPI label="FCP" value={fmtMs(lab.fcp_ms)} hint="lab" />
            <KPI label="CLS" value={lab.cls != null ? lab.cls.toFixed(3) : "—"} hint={field.cls ? `field p75: ${field.cls.p75}` : "lab"} />
            <KPI label="TBT" value={fmtMs(lab.tbt_ms)} hint="lab" />
          </div>

          {histSeries.length > 1 && (
            <div className="border border-white/[0.06] p-4">
              <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-3">30-day score trend · {strategy}</div>
              <div style={{ width: "100%", height: 220 }}>
                <ResponsiveContainer>
                  <LineChart data={histSeries}>
                    <CartesianGrid stroke="#ffffff10" vertical={false} />
                    <XAxis dataKey="label" stroke="#71717a" fontSize={11} />
                    <YAxis domain={[0, 100]} stroke="#71717a" fontSize={11} />
                    <Tooltip contentStyle={{ background: "#0a0a0a", border: "1px solid #ffffff20", fontSize: 12 }} />
                    <Line type="monotone" dataKey="perf" name="Performance" stroke="#3ab2ff" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="a11y" name="Accessibility" stroke="#22c55e" dot={false} />
                    <Line type="monotone" dataKey="bp" name="Best Practices" stroke="#eab308" dot={false} />
                    <Line type="monotone" dataKey="seo" name="SEO" stroke="#a855f7" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─────────────────────── Heatmaps ───────────────────────
function HeatmapsPane({ features, config }) {
  if (!features?.heatmaps) return <PlanLockNotice requiredPlan="Pro" label="Heatmaps" />;

  const active = !!config?.heatmaps_active;
  const platformReady = !!config?.platform_clarity_configured;

  return (
    <div className="space-y-6" data-testid="analytics-heatmaps">
      <div className="border border-white/[0.06] p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Activity className="h-4 w-4 text-brand" />
              <div className="font-display text-lg">Heatmaps & session recordings</div>
              {active && (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.25em] bg-signal-success/10 text-signal-success border border-signal-success/30">
                  <span className="h-1.5 w-1.5 bg-signal-success rounded-full animate-pulse" /> active
                </span>
              )}
            </div>
            <div className="text-sm text-zinc-400 max-w-2xl">
              See exactly where visitors click, how far they scroll, and replay real session recordings.
              Recordings are anonymous, GDPR-friendly, and start the moment your tracker is live — no setup required from your side.
            </div>
          </div>
        </div>

        {!platformReady ? (
          <div className="mt-6 bg-signal-queued/10 border border-signal-queued/30 p-4 text-sm" data-testid="heatmaps-not-configured">
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-signal-queued mb-1">
              ⚠ heatmaps not yet enabled on this platform
            </div>
            <div className="text-zinc-400">
              The platform administrator hasn't completed the one-time setup yet. Reach out — once they enable it,
              heatmaps light up automatically on every Pro+ app, including this one.
            </div>
          </div>
        ) : !active ? (
          <div className="mt-6 bg-elevated/40 border border-white/[0.06] p-4 text-sm" data-testid="heatmaps-not-active">
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-1">// status</div>
            <div className="text-zinc-400">
              Heatmaps are enabled platform-wide but this app's tracker hasn't reported yet. Visit the Setup tab,
              copy the snippet, paste it into your <code className="bg-black/40 px-1.5">&lt;head&gt;</code> and redeploy.
            </div>
          </div>
        ) : (
          <>
            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3">
              <KPI label="Status" value="Recording" hint="auto-injected via DeployHub" />
              <KPI label="Privacy" value="Anonymized" hint="IPs masked · GDPR friendly" />
              <KPI label="Retention" value="30 days" hint="rolling window" />
            </div>
            {config?.clarity_deeplink && (
              <div className="mt-6">
                <a
                  href={config.clarity_deeplink}
                  target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg text-sm font-medium hover:bg-brand/90"
                  data-testid="heatmaps-open-dashboard"
                >
                  Open recordings dashboard ↗
                </a>
                <div className="mt-2 text-[11px] font-mono text-zinc-500">
                  Pre-filtered to this app's host. Access is managed by your platform administrator —
                  reach out if you'd like a viewer login.
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ─────────────────────── Setup ───────────────────────
function SetupPane({ appId, config, refreshConfig }) {
  if (!config) return null;

  // Framework-specific guidance — we let users pick the one matching their stack.
  const headHTML = config.snippet;
  const nextLayout = `// app/layout.tsx (App Router)
import Script from 'next/script'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {children}
        <Script
          src="${config.tracker_url}"
          data-site="${config.site_id}"
          data-endpoint="${config.collect_url}"${config.clarity_project_id ? `
          data-clarity="${config.clarity_project_id}"` : ""}
          strategy="afterInteractive"
        />
      </body>
    </html>
  )
}`;

  return (
    <div className="space-y-6" data-testid="analytics-setup">
      <div className="border border-white/[0.06] p-6">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-brand mb-2">// step 1 · install</div>
        <div className="font-display text-xl tracking-tight mb-1">Drop this in your &lt;head&gt;</div>
        <div className="text-sm text-zinc-400 mb-4">
          The tracker is ~1 KB, cookie-less, and auto-tracks SPA navigation, outbound clicks and Clarity heatmaps.
        </div>
        <CopyBlock text={headHTML} testId="analytics-snippet-copy-html" />

        <div className="mt-6 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2">// Next.js (App Router)</div>
        <CopyBlock text={nextLayout} testId="analytics-snippet-copy-next" />
      </div>

      <div className="border border-white/[0.06] p-6">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-brand mb-2">// step 2 · deploy + verify</div>
        <ol className="space-y-2 text-sm text-zinc-300 list-decimal pl-5">
          <li>Commit + push your change — DeployHub will redeploy automatically.</li>
          <li>Visit your site at <a href={config.primary_url || "#"} target="_blank" rel="noreferrer" className="text-brand hover:underline">{config.primary_url || "your URL"}</a>.</li>
          <li>Come back to the <strong>Visitors</strong> tab — first pageviews appear within ~10 seconds.</li>
        </ol>
      </div>

      <div className="border border-white/[0.06] p-6">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2">// site identifiers</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
          <div>
            <div className="text-zinc-500 mb-1">site id</div>
            <div className="bg-black/40 border border-white/[0.04] px-3 py-2 text-zinc-200 select-all">{config.site_id}</div>
          </div>
          <div>
            <div className="text-zinc-500 mb-1">tracker url</div>
            <div className="bg-black/40 border border-white/[0.04] px-3 py-2 text-zinc-200 select-all break-all">{config.tracker_url}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────── Root tab ───────────────────────
export default function AppWebAnalyticsTab({ appId }) {
  const [sub, setSub] = useState("visitors");
  const [config, setConfig] = useState(null);

  const refreshConfig = async () => {
    try {
      const r = await api.get(`/apps/${appId}/web-analytics/config`);
      setConfig(r.data);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };
  useEffect(() => { refreshConfig(); /* eslint-disable-next-line */ }, [appId]);

  const features = config?.features || {};

  return (
    <div className="p-6 space-y-6" data-testid="analytics-tab">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="font-display text-2xl tracking-tight">Web analytics</h2>
          <p className="text-sm text-zinc-400 mt-1">
            Privacy-first pageviews, Google PageSpeed audits, and Microsoft Clarity heatmaps — all in one place.
          </p>
        </div>
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">
          plan · <span className="text-zinc-300">{config?.plan_id || "—"}</span>
        </div>
      </div>

      <div className="flex border-b border-white/[0.06]">
        {SUB_TABS.map((t) => {
          const locked = t.gated && !features[t.gated];
          return (
            <button
              key={t.id}
              onClick={() => setSub(t.id)}
              data-testid={`analytics-subtab-${t.id}`}
              className={`px-4 py-2.5 text-sm font-mono border-b-2 inline-flex items-center gap-2 -mb-px transition-colors
                ${sub === t.id ? "border-brand text-brand" : "border-transparent text-zinc-400 hover:text-zinc-200"}`}
            >
              <t.icon className="h-3.5 w-3.5" /> {t.label}
              {locked && <Lock className="h-3 w-3 text-zinc-500" />}
            </button>
          );
        })}
      </div>

      {sub === "visitors" && <VisitorsPane appId={appId} />}
      {sub === "speed" && <SpeedPane appId={appId} features={features} />}
      {sub === "heatmaps" && <HeatmapsPane features={features} config={config} />}
      {sub === "setup" && <SetupPane appId={appId} config={config} refreshConfig={refreshConfig} />}
    </div>
  );
}

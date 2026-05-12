import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity, AlertTriangle, Check, CheckCircle2, ChevronRight, Clock,
  Server, ShieldCheck, XCircle, RefreshCcw, Loader2,
} from "lucide-react";
import Logo from "../components/Logo";
import { api } from "../lib/api";
import useSeo from "../hooks/useSeo";

/* ─────────────────────── Atoms ─────────────────────── */

const STATE_STYLES = {
  operational: { dot: "bg-emerald-400", text: "text-emerald-400", label: "Operational",      bd: "border-emerald-500/30" },
  degraded:    { dot: "bg-yellow-400",  text: "text-yellow-400",  label: "Degraded",         bd: "border-yellow-500/30" },
  down:        { dot: "bg-red-400",     text: "text-red-400",     label: "Outage",           bd: "border-red-500/30" },
  unknown:     { dot: "bg-zinc-500",    text: "text-zinc-400",    label: "Awaiting check",   bd: "border-zinc-700" },
};

function StatusPill({ state }) {
  const s = STATE_STYLES[state] || STATE_STYLES.unknown;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.3em] border ${s.bd} ${s.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot} animate-pulse`} />
      {s.label}
    </span>
  );
}

function OverallBanner({ state, checkedAt }) {
  const s = STATE_STYLES[state] || STATE_STYLES.unknown;
  const Icon = state === "operational" ? CheckCircle2 : state === "down" ? XCircle : AlertTriangle;
  const headline = {
    operational: "All systems operational",
    degraded:    "Some systems are degraded",
    down:        "We're investigating an outage",
    unknown:     "Awaiting first check",
  }[state] || "Status unknown";
  return (
    <div className={`border ${s.bd} bg-zinc-950/40 p-6 md:p-8 mb-10`} data-testid="status-banner">
      <div className="flex items-start gap-4">
        <div className={`p-2 border ${s.bd}`}>
          <Icon className={`h-6 w-6 ${s.text}`} strokeWidth={1.5} />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="font-display text-2xl md:text-3xl font-bold tracking-tight text-white">{headline}</h1>
            <StatusPill state={state} />
          </div>
          <div className="mt-2 text-xs font-mono text-zinc-500">
            last checked · {checkedAt ? new Date(checkedAt).toLocaleString() : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────── 90-day uptime histogram ─────────────────────── */

function UptimeBars({ days, history }) {
  // Build N-day window aligned to today.
  const buckets = useMemo(() => {
    const map = new Map((history || []).map((r) => [r.day, r]));
    const out = [];
    const today = new Date();
    today.setUTCHours(0, 0, 0, 0);
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setUTCDate(today.getUTCDate() - i);
      const key = d.toISOString().slice(0, 10);
      const row = map.get(key);
      if (!row || !row.total) {
        out.push({ key, pct: null, total: 0, ok: 0 });
      } else {
        out.push({ key, pct: (row.okc / row.total) * 100, total: row.total, ok: row.okc });
      }
    }
    return out;
  }, [days, history]);
  return (
    <div className="flex items-end gap-px h-7" data-testid="uptime-bars">
      {buckets.map((b) => {
        let cls = "bg-zinc-800";
        if (b.pct === null) cls = "bg-zinc-900";
        else if (b.pct >= 99.5) cls = "bg-emerald-500/80";
        else if (b.pct >= 95)   cls = "bg-yellow-500/80";
        else                    cls = "bg-red-500/80";
        return (
          <div
            key={b.key}
            className={`flex-1 ${cls} hover:opacity-80 transition-opacity`}
            title={b.pct === null ? `${b.key}: no data` : `${b.key}: ${b.pct.toFixed(2)}% (${b.ok}/${b.total})`}
          />
        );
      })}
    </div>
  );
}

function uptimePct(history) {
  const totals = (history || []).reduce(
    (acc, r) => ({ total: acc.total + (r.total || 0), ok: acc.ok + (r.okc || 0) }),
    { total: 0, ok: 0 },
  );
  if (!totals.total) return null;
  return (totals.ok / totals.total) * 100;
}

/* ─────────────────────── Component card ─────────────────────── */

function ComponentRow({ c, history }) {
  const uptime = uptimePct(history);
  const s = STATE_STYLES[c.state] || STATE_STYLES.unknown;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.3 }}
      className="border border-zinc-800 bg-zinc-950/30 p-5 hover:border-cyan-500/30 transition-colors"
      data-testid={`status-component-${c.id}`}
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3 min-w-0">
          <span className={`mt-1.5 h-2 w-2 rounded-full ${s.dot} shrink-0 shadow-[0_0_8px_2px_currentColor] ${s.text}`} />
          <div className="min-w-0">
            <div className="font-display text-base font-semibold text-white truncate">{c.name}</div>
            <div className="text-xs text-zinc-500 mt-0.5">{c.desc}</div>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {c.latency_ms != null && (
            <span className="text-[11px] font-mono text-zinc-500 tabular-nums hidden sm:inline">{Math.round(c.latency_ms)}ms</span>
          )}
          <StatusPill state={c.state} />
        </div>
      </div>
      <div className="mt-4">
        <UptimeBars days={90} history={history} />
        <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-zinc-500">
          <span>90 days ago</span>
          <span className="text-zinc-400 tabular-nums">{uptime != null ? uptime.toFixed(2) : "—"}% uptime</span>
          <span>today</span>
        </div>
      </div>
    </motion.div>
  );
}

/* ─────────────────────── Incidents ─────────────────────── */

function IncidentList({ title, items, empty, sev }) {
  if (!items || items.length === 0) {
    return (
      <div className="border border-dashed border-zinc-800 p-6 text-center text-xs font-mono text-zinc-500" data-testid={`incidents-empty-${sev}`}>
        {empty}
      </div>
    );
  }
  return (
    <div className="space-y-3" data-testid={`incidents-list-${sev}`}>
      <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500">{title}</div>
      {items.map((it) => (
        <div key={it.id} className="border border-zinc-800 bg-zinc-950/30 p-4">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className={`uppercase text-[9px] tracking-[0.25em] px-1.5 py-0.5 border ${it.severity === "major" ? "text-red-400 border-red-500/40" : "text-yellow-400 border-yellow-500/40"}`}>
                {it.severity}
              </span>
              <span className="text-zinc-400">{it.component_id}</span>
            </div>
            <div className="text-[11px] font-mono text-zinc-500 tabular-nums">
              {new Date(it.started_at).toLocaleString()}
              {it.resolved_at && <span> · resolved {new Date(it.resolved_at).toLocaleTimeString()}</span>}
            </div>
          </div>
          <div className="text-sm text-zinc-300">{it.summary}</div>
        </div>
      ))}
    </div>
  );
}

/* ─────────────────────── Page ─────────────────────── */

export default function Status() {
  useSeo({
    title: "System status — DeployUnit",
    description: "Real-time status of the DeployUnit platform: build engine, DNS, SSL, payments, notifications.",
    path: "/status",
  });
  const [data, setData] = useState(null);
  const [history, setHistory] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    setRefreshing(true);
    try {
      const [s, h] = await Promise.all([
        api.get("/status"),
        api.get("/status/history", { params: { days: 90 } }),
      ]);
      setData(s.data);
      setHistory(h.data?.history || {});
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
    // eslint-disable-next-line
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-black text-white flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />
      </div>
    );
  }

  // Group components by their "group" field
  const groups = (data?.components || []).reduce((acc, c) => {
    (acc[c.group] = acc[c.group] || []).push(c);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-black text-white" data-testid="status-page">
      {/* Top bar */}
      <header className="border-b border-zinc-900">
        <div className="max-w-5xl mx-auto px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5" data-testid="status-home-link">
            <Logo className="h-6 w-auto" />
          </Link>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={load}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-mono uppercase tracking-[0.3em] border border-zinc-800 hover:border-cyan-500/40 text-zinc-400 hover:text-cyan-400 transition-colors disabled:opacity-50"
              data-testid="status-refresh"
            >
              <RefreshCcw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} />
              {refreshing ? "refreshing" : "refresh"}
            </button>
            <Link
              to="/"
              className="hidden sm:inline-flex items-center gap-1 text-xs font-mono text-zinc-400 hover:text-cyan-400 transition-colors"
              data-testid="status-back-home"
            >
              back to deployunit <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 lg:px-8 py-10">
        <div className="mb-8">
          <div className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.3em] bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 mb-3">
            <Activity className="h-3 w-3" /> system status
          </div>
          <p className="text-zinc-400 text-sm max-w-2xl">
            Live health of every DeployUnit component and third-party dependency. Pinged every 60 seconds.
            Page refreshes automatically every 30 seconds.
          </p>
        </div>

        <OverallBanner state={data?.overall_state} checkedAt={data?.checked_at} />

        {Object.entries(groups).map(([group, items]) => (
          <section key={group} className="mb-10">
            <div className="flex items-center gap-3 mb-4">
              <Server className="h-3.5 w-3.5 text-zinc-500" />
              <h2 className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500">{group}</h2>
              <div className="flex-1 h-px bg-zinc-900" />
              <span className="text-[10px] font-mono text-zinc-600">{items.length}</span>
            </div>
            <div className="space-y-3">
              {items.map((c) => (
                <ComponentRow key={c.id} c={c} history={history[c.id] || []} />
              ))}
            </div>
          </section>
        ))}

        <section className="mt-12">
          <div className="flex items-center gap-3 mb-4">
            <AlertTriangle className="h-3.5 w-3.5 text-zinc-500" />
            <h2 className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500">Incidents</h2>
            <div className="flex-1 h-px bg-zinc-900" />
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <IncidentList
                title="Active"
                items={data?.open_incidents}
                empty="No active incidents — everything is humming."
                sev="open"
              />
            </div>
            <div>
              <IncidentList
                title="Recently resolved"
                items={data?.recent_incidents}
                empty="No recent incidents in the last 30 days."
                sev="resolved"
              />
            </div>
          </div>
        </section>

        <footer className="mt-16 pt-6 border-t border-zinc-900 flex items-center justify-between text-[11px] font-mono text-zinc-600 flex-wrap gap-2">
          <span className="inline-flex items-center gap-1.5">
            <Clock className="h-3 w-3" /> Probed every 60s · last 90 days · auto-refresh 30s
          </span>
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck className="h-3 w-3" /> Operated by ServUnit Technologies BV
          </span>
        </footer>
      </main>
    </div>
  );
}

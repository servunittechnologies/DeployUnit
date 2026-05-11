import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Cpu, MemoryStick, HardDrive, Network, AlertOctagon, Activity } from "lucide-react";

const WINDOWS = [
  { id: "1h",  label: "1H"  },
  { id: "24h", label: "24H" },
  { id: "7d",  label: "7D" },
  { id: "30d", label: "30D" },
];

function fmtBytes(b) {
  if (!b) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return `${b.toFixed(b < 10 ? 2 : 1)} ${u[i]}`;
}
function fmtMb(mb) {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb} MB`;
}
function fmtPct(p) { return `${(p ?? 0).toFixed(1)}%`; }
function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/**
 * Show REAL container metrics (CPU/mem/net/disk) collected by the DeployUnit
 * metrics agent. Falls back to an "Install agent" CTA when no data is
 * flowing yet.
 */
export default function AppMetricsCharts({ appId, onInstallAgent }) {
  const [window, setWindow] = useState("24h");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    api.get(`/apps/${appId}/metrics?window=${window}`)
      .then((r) => setData(r.data)).finally(() => setLoading(false));
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, [appId, window]);

  if (loading && !data) {
    return <div className="p-6 font-mono text-sm text-zinc-500" data-testid="metrics-loading">Loading container metrics…</div>;
  }
  if (!data || !data.have_data) {
    return (
      <div className="border border-signal-queued/30 bg-signal-queued/[0.04] p-5" data-testid="metrics-no-data">
        <div className="flex items-start gap-3">
          <AlertOctagon className="h-5 w-5 text-signal-queued flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-signal-queued mb-1">// metrics agent not reporting</div>
            <div className="text-sm text-zinc-200">
              Live container CPU/memory/disk/network stats arrive once you install the DeployUnit metrics agent on your build engine VPS.
            </div>
            <div className="text-xs text-zinc-500 mt-1">
              Without the agent we only show what's measurable from outside the container (HTTP uptime, response time, deployments, build minutes).
            </div>
            <button
              onClick={() => onInstallAgent ? onInstallAgent() : (window.location.href = "/app/admin#integrations")}
              className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 bg-brand text-brand-fg text-xs font-mono uppercase tracking-wider hover:bg-brand/90"
              data-testid="metrics-install-cta"
            >
              <Activity className="h-3 w-3" /> Install agent
            </button>
          </div>
        </div>
      </div>
    );
  }

  const latest = data.latest || {};
  const samples = data.samples || [];
  const cpuSeries = samples.map((s) => ({ t: s.sampled_at, v: s.cpu_pct }));
  const memSeries = samples.map((s) => ({ t: s.sampled_at, v: s.mem_pct }));
  // Network: convert cumulative counters to per-sample rate (B/s)
  const netSeries = computeRate(samples, "net_rx_bytes");
  const netTxSeries = computeRate(samples, "net_tx_bytes");
  const diskReadSeries = computeRate(samples, "disk_read_bytes");
  const diskWriteSeries = computeRate(samples, "disk_write_bytes");

  // Totals over window (last - first cumulative bytes)
  const totalRx = samples.length >= 2 ? Math.max(0, samples[samples.length - 1].net_rx_bytes - samples[0].net_rx_bytes) : (latest.net_rx_bytes || 0);
  const totalTx = samples.length >= 2 ? Math.max(0, samples[samples.length - 1].net_tx_bytes - samples[0].net_tx_bytes) : (latest.net_tx_bytes || 0);

  return (
    <div className="space-y-4" data-testid="metrics-charts">
      {/* Header + window picker */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-brand" />
            <h3 className="font-display text-lg">Container metrics</h3>
            <span className="text-[10px] font-mono text-zinc-500 ml-2">{samples.length} samples · last @ {fmtTime(latest.sampled_at)}</span>
          </div>
          <p className="text-xs font-mono text-zinc-500 mt-0.5">Reported by DeployUnit agent every 30s. Auto-refresh.</p>
        </div>
        <div className="flex gap-1 border border-white/10">
          {WINDOWS.map((w) => (
            <button
              key={w.id} onClick={() => setWindow(w.id)}
              className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors ${
                window === w.id ? "bg-brand text-brand-fg" : "text-zinc-400 hover:text-white"
              }`}
              data-testid={`metrics-window-${w.id}`}
            >{w.label}</button>
          ))}
        </div>
      </div>

      {/* Top KPIs (now) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.06] border border-white/[0.06]">
        <MetricTile icon={Cpu}         label="CPU now"    value={fmtPct(latest.cpu_pct)}      hint={cpuColor(latest.cpu_pct)} />
        <MetricTile icon={MemoryStick} label="Memory now" value={fmtPct(latest.mem_pct)}      hint={`${fmtMb(latest.mem_used_mb)} / ${fmtMb(latest.mem_limit_mb)}`} />
        <MetricTile icon={Network}     label={`Net in (${window})`}  value={fmtBytes(totalRx)}  hint={`tx: ${fmtBytes(totalTx)}`} />
        <MetricTile icon={HardDrive}   label="Disk I/O now" value={fmtBytes(latest.disk_read_bytes + latest.disk_write_bytes)} hint={`read+write cumulative`} />
      </div>

      {/* Sparkline rows */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <ChartCard title="CPU %" max={100} series={cpuSeries} color="#00e5ff" testId="chart-cpu" />
        <ChartCard title="Memory %" max={100} series={memSeries} color="#a78bfa" testId="chart-mem" />
        <ChartCard title="Network in (B/s)" series={netSeries} color="#10b981" testId="chart-net-in" />
        <ChartCard title="Network out (B/s)" series={netTxSeries} color="#f59e0b" testId="chart-net-out" />
        <ChartCard title="Disk read (B/s)" series={diskReadSeries} color="#60a5fa" testId="chart-disk-read" />
        <ChartCard title="Disk write (B/s)" series={diskWriteSeries} color="#fb7185" testId="chart-disk-write" />
      </div>
    </div>
  );
}

function cpuColor(p) {
  if (p == null) return "";
  if (p < 50) return "healthy";
  if (p < 80) return "warming up";
  return "near limit";
}

function MetricTile({ icon: Icon, label, value, hint }) {
  return (
    <div className="bg-background p-4">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">
        <Icon className="h-3 w-3 text-brand" /> {label}
      </div>
      <div className="font-display text-2xl mt-1.5 tracking-tight">{value}</div>
      <div className="text-[10px] font-mono text-zinc-500 mt-0.5 truncate">{hint}</div>
    </div>
  );
}

/**
 * Convert cumulative counter samples to per-second rate samples.
 * If sample[n].value < sample[n-1].value (container restart resets counter)
 * we treat that as zero, not a negative rate.
 */
function computeRate(samples, key) {
  const out = [];
  for (let i = 1; i < samples.length; i++) {
    const cur = samples[i];
    const prev = samples[i - 1];
    const dt = (new Date(cur.sampled_at).getTime() - new Date(prev.sampled_at).getTime()) / 1000;
    if (dt <= 0) continue;
    const dv = (cur[key] || 0) - (prev[key] || 0);
    out.push({ t: cur.sampled_at, v: dv > 0 ? dv / dt : 0 });
  }
  return out;
}

function ChartCard({ title, series, color, max, testId }) {
  if (!series.length) {
    return (
      <div className="border border-white/[0.06] p-3">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-1">{title}</div>
        <div className="h-20 grid place-items-center text-xs font-mono text-zinc-600">waiting for data…</div>
      </div>
    );
  }
  const W = 400; const H = 80; const PAD = 8;
  const values = series.map((s) => s.v).filter((v) => v != null);
  const ymax = max != null ? max : Math.max(1, ...values);
  const step = (W - 2 * PAD) / Math.max(1, series.length - 1);
  const points = series.map((s, i) => {
    const x = PAD + i * step;
    const y = H - PAD - ((s.v || 0) / ymax) * (H - 2 * PAD);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const last = series[series.length - 1]?.v;
  const display = max === 100 ? `${(last ?? 0).toFixed(1)}%` : fmtBytes(last);
  return (
    <div className="border border-white/[0.06] p-3" data-testid={testId}>
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">{title}</div>
        <div className="text-xs font-mono text-zinc-300">{display}</div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-20">
        <polyline points={points} stroke={color} fill="none" strokeWidth="1.5" />
        <polyline points={`${PAD},${H - PAD} ${points} ${PAD + (series.length - 1) * step},${H - PAD}`} fill={color} opacity="0.1" />
      </svg>
    </div>
  );
}

import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api, getApiErrorMessage } from "../../lib/api";
import StatusBadge from "../../components/StatusBadge";
import TerminalLog from "../../components/TerminalLog";
import { ChevronLeft, RotateCw, RefreshCcw, Trash2, Globe, GitBranch, ExternalLink, Plus, X } from "lucide-react";

const TABS = ["overview", "deployments", "domains", "env", "monitoring", "settings"];

function timeAgo(iso) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function AppDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState("overview");
  const [app, setApp] = useState(null);
  const [deployments, setDeployments] = useState([]);
  const [domains, setDomains] = useState([]);
  const [envVars, setEnvVars] = useState({});
  const [envText, setEnvText] = useState("");
  const [monitoring, setMonitoring] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [domainInput, setDomainInput] = useState("");

  const load = useCallback(async () => {
    const [a, d, dom, e, m] = await Promise.all([
      api.get(`/apps/${id}`),
      api.get(`/apps/${id}/deployments`),
      api.get("/domains", { params: { workspace_id: "x" } }).catch(() => ({ data: [] })),
      api.get(`/apps/${id}/env`),
      api.get(`/apps/${id}/monitoring`),
    ]);
    setApp(a.data);
    setDeployments(d.data);
    setEnvVars(e.data.env_vars || {});
    setEnvText(Object.entries(e.data.env_vars || {}).map(([k, v]) => `${k}=${v}`).join("\n"));
    setMonitoring(m.data);
    // get app-scoped domains
    const ws = a.data.workspace_id;
    const domsRes = await api.get("/domains", { params: { workspace_id: ws } });
    setDomains(domsRes.data.filter((x) => x.app_id === id));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // Poll while building
  useEffect(() => {
    if (!app) return;
    if (app.status === "building" || app.status === "queued") {
      const i = setInterval(load, 5000);
      return () => clearInterval(i);
    }
  }, [app, load]);

  const redeploy = async () => {
    setBusy(true);
    try { await api.post(`/apps/${id}/redeploy`); await load(); }
    finally { setBusy(false); }
  };
  const restart = async () => {
    setBusy(true);
    try { await api.post(`/apps/${id}/restart`); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    if (!window.confirm("Delete this app? This cannot be undone.")) return;
    await api.delete(`/apps/${id}`);
    navigate("/app");
  };

  const saveEnv = async () => {
    const next = {};
    envText.split(/\r?\n/).forEach((line) => {
      const i = line.indexOf("=");
      if (i > 0) next[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    });
    await api.put(`/apps/${id}/env`, { env_vars: next });
    setEnvVars(next);
  };

  const addDomain = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/domains", { app_id: id, domain: domainInput.trim() });
      setDomainInput("");
      load();
    } catch (e) { setError(getApiErrorMessage(e)); }
  };
  const verifyDomain = async (did) => { await api.post(`/domains/${did}/verify`); load(); };
  const removeDomain = async (did) => { await api.delete(`/domains/${did}`); load(); };

  if (!app) return <div className="p-6 text-zinc-500 font-mono text-sm">Loading app…</div>;

  const latestDeploy = deployments[0];

  return (
    <div data-testid="app-detail">
      <div className="px-6 py-6 border-b border-white/[0.06]">
        <Link to="/app" className="text-xs font-mono text-zinc-500 hover:text-white inline-flex items-center gap-1">
          <ChevronLeft className="h-3 w-3" /> dashboard
        </Link>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-display text-4xl font-semibold tracking-tighter">{app.name}</h1>
              <StatusBadge status={app.status} />
            </div>
            <div className="mt-2 flex items-center gap-4 text-xs font-mono text-zinc-500">
              <span className="inline-flex items-center gap-1.5"><GitBranch className="h-3 w-3" /> {app.branch}</span>
              <span>{app.framework}</span>
              {app.primary_url && (
                <a href={app.primary_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand hover:underline">
                  {app.primary_url.replace(/^https?:\/\//, "")} <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={redeploy} disabled={busy} className="inline-flex items-center gap-2 px-3 py-2 border border-white/15 hover:border-brand hover:text-brand text-sm" data-testid="app-redeploy">
              <RotateCw className="h-4 w-4" /> Redeploy
            </button>
            <button onClick={restart} disabled={busy} className="inline-flex items-center gap-2 px-3 py-2 border border-white/15 hover:border-white/40 text-sm" data-testid="app-restart">
              <RefreshCcw className="h-4 w-4" /> Restart
            </button>
            <button onClick={remove} className="inline-flex items-center gap-2 px-3 py-2 border border-signal-failed/30 text-signal-failed hover:bg-signal-failed/10 text-sm" data-testid="app-delete">
              <Trash2 className="h-4 w-4" /> Delete
            </button>
          </div>
        </div>
        <div className="mt-6 flex gap-1 border-b border-white/[0.06] -mb-6">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-3 text-xs uppercase font-mono tracking-[0.25em] border-b-2 transition ${tab === t ? "border-brand text-brand" : "border-transparent text-zinc-500 hover:text-white"}`}
              data-testid={`tab-${t}`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {tab === "overview" && (
        <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-px bg-white/[0.06] border border-white/[0.06]">
          <div className="bg-background p-5 lg:col-span-2">
            <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500 mb-2">// latest deployment</div>
            <TerminalLog
              title={latestDeploy ? `${latestDeploy.status}.log` : "no.log"}
              lines={latestDeploy?.logs || []}
              height={320}
            />
          </div>
          <div className="bg-background p-5 space-y-4">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Repository</div>
              <div className="text-sm font-mono break-all">{app.repo_url}</div>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Last deploy</div>
              <div className="text-sm">{timeAgo(app.last_deploy_at)}</div>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Uptime 24h</div>
              <div className="text-sm">{monitoring?.uptime_pct != null ? `${monitoring.uptime_pct}%` : "collecting…"}</div>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Avg response</div>
              <div className="text-sm">{monitoring?.avg_response_ms != null ? `${monitoring.avg_response_ms}ms` : "—"}</div>
            </div>
          </div>
        </div>
      )}

      {tab === "deployments" && (
        <div className="p-6">
          <div className="border-t border-l border-white/[0.06]">
            {deployments.map((d) => (
              <div key={d.id} className="flex items-center justify-between p-4 border-r border-b border-white/[0.06]" data-testid={`deployment-${d.id}`}>
                <div className="flex items-center gap-4">
                  <StatusBadge status={d.status} />
                  <div>
                    <div className="text-sm">{d.commit_message || "Deployment"}</div>
                    <div className="text-xs font-mono text-zinc-500">{timeAgo(d.started_at)} · {d.branch}</div>
                  </div>
                </div>
                <button
                  onClick={() => api.get(`/deployments/${d.id}/logs`).then((r) => alert(r.data.logs.join("\n")))}
                  className="text-xs font-mono text-zinc-400 hover:text-brand"
                >
                  view logs
                </button>
              </div>
            ))}
            {deployments.length === 0 && <div className="p-10 text-zinc-500 text-sm">No deployments yet.</div>}
          </div>
        </div>
      )}

      {tab === "domains" && (
        <div className="p-6 max-w-3xl">
          <form onSubmit={addDomain} className="flex gap-2 mb-6">
            <input
              value={domainInput} onChange={(e) => setDomainInput(e.target.value)}
              placeholder="app.yourdomain.com"
              className="flex-1 bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
              data-testid="domain-input"
            />
            <button type="submit" className="px-4 py-2 bg-brand text-brand-fg font-medium" data-testid="domain-add">
              <Plus className="h-4 w-4 inline" /> Link
            </button>
          </form>
          {error && <div className="mb-4 text-signal-failed text-sm">{error}</div>}
          <div className="border-t border-l border-white/[0.06]">
            {domains.map((d) => (
              <div key={d.id} className="flex items-center justify-between p-4 border-r border-b border-white/[0.06]">
                <div>
                  <div className="font-mono text-sm">{d.domain}</div>
                  <div className="mt-1 flex items-center gap-2 text-xs font-mono text-zinc-500">
                    <StatusBadge status={d.dns_verified ? "live" : "pending"} />
                    SSL: {d.ssl_status}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {!d.dns_verified && (
                    <button onClick={() => verifyDomain(d.id)} className="text-xs font-mono text-brand hover:underline" data-testid={`domain-verify-${d.id}`}>verify dns</button>
                  )}
                  <button onClick={() => removeDomain(d.id)} className="text-xs font-mono text-signal-failed hover:underline">remove</button>
                </div>
              </div>
            ))}
            {domains.length === 0 && <div className="p-10 text-zinc-500 text-sm">No custom domains yet.</div>}
          </div>
          <div className="mt-6 p-4 border border-white/10 bg-black/30 font-mono text-xs leading-6 text-zinc-400">
            <div className="text-brand">// dns instructions</div>
            <div>type:&nbsp;&nbsp;&nbsp;&nbsp;A</div>
            <div>name:&nbsp;&nbsp;&nbsp;&nbsp;your-subdomain</div>
            <div>value:&nbsp;&nbsp;&nbsp;149.12.246.205</div>
            <div className="mt-2">After adding the record, click "verify dns".</div>
          </div>
        </div>
      )}

      {tab === "env" && (
        <div className="p-6 max-w-3xl">
          <div className="text-xs text-zinc-400 mb-2">One per line · KEY=value</div>
          <textarea
            value={envText}
            onChange={(e) => setEnvText(e.target.value)}
            rows={12}
            className="w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="env-textarea"
          />
          <div className="mt-3 flex gap-3">
            <button onClick={saveEnv} className="px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90" data-testid="env-save">Save & sync</button>
            <span className="text-xs text-zinc-500 font-mono py-2">{Object.keys(envVars).length} variables stored</span>
          </div>
        </div>
      )}

      {tab === "monitoring" && (
        <div className="p-6 max-w-4xl">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.06] border border-white/[0.06]">
            <div className="bg-background p-5">
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Uptime 24h</div>
              <div className="mt-2 font-display text-3xl text-signal-live">{monitoring?.uptime_pct != null ? `${monitoring.uptime_pct}%` : "—"}</div>
            </div>
            <div className="bg-background p-5">
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Avg response</div>
              <div className="mt-2 font-display text-3xl">{monitoring?.avg_response_ms != null ? `${monitoring.avg_response_ms}ms` : "—"}</div>
            </div>
            <div className="bg-background p-5">
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Samples</div>
              <div className="mt-2 font-display text-3xl">{monitoring?.samples || 0}</div>
            </div>
            <div className="bg-background p-5">
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Status</div>
              <div className="mt-2"><StatusBadge status={app.status} /></div>
            </div>
          </div>
          <div className="mt-6 border border-white/[0.06] p-4">
            <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500 mb-2">Recent checks</div>
            <div className="flex gap-1 flex-wrap" data-testid="checks-strip">
              {(monitoring?.results || []).slice(0, 60).map((r) => (
                <span
                  key={r.id}
                  title={`${r.timestamp} · ${r.status_code || "ERR"} · ${r.response_time_ms || "?"}ms`}
                  className={`h-6 w-1.5 ${r.ok ? "bg-signal-live/70" : "bg-signal-failed/70"}`}
                />
              ))}
              {(!monitoring?.results || monitoring.results.length === 0) && <span className="text-xs text-zinc-500">No checks yet — they run every minute.</span>}
            </div>
          </div>
        </div>
      )}

      {tab === "settings" && (
        <div className="p-6 max-w-2xl space-y-6">
          <div className="border border-white/10 p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Build command</div>
            <div className="mt-1 font-mono text-sm text-zinc-300">{app.build_command || "auto-detected"}</div>
          </div>
          <div className="border border-white/10 p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Start command</div>
            <div className="mt-1 font-mono text-sm text-zinc-300">{app.start_command || "auto-detected"}</div>
          </div>
          <div className="border border-signal-failed/30 p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-signal-failed">Danger zone</div>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-sm">Permanently delete this app and its history.</span>
              <button onClick={remove} className="px-3 py-1.5 text-sm border border-signal-failed/40 text-signal-failed hover:bg-signal-failed/10">Delete app</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

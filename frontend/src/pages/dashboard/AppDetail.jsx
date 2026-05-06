import { useEffect, useState, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api, getApiErrorMessage } from "../../lib/api";
import StatusBadge from "../../components/StatusBadge";
import TerminalLog from "../../components/TerminalLog";
import EnvVarsEditor from "../../components/EnvVarsEditor";
import DeployModal from "../../components/DeployModal";
import DeploymentStatus from "../../components/DeploymentStatus";
import SitePreview from "../../components/SitePreview";
import BuildErrorPanel from "../../components/BuildErrorPanel";
import AddDomainWizard from "../../components/AddDomainWizard";
import useDeploymentStream from "../../hooks/useDeploymentStream";
import {
  ChevronLeft, RotateCw, RefreshCcw, Trash2, GitBranch, GitCommit,
  ExternalLink, Plus, Save, Loader2, Rocket, ShieldCheck, Undo2,
} from "lucide-react";
import { toast } from "sonner";

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

function fmtDuration(start, end) {
  if (!start) return "—";
  const a = new Date(start).getTime();
  const b = end ? new Date(end).getTime() : Date.now();
  const sec = Math.max(0, Math.round((b - a) / 1000));
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

function SettingsForm({ app, onSaved }) {
  const [name, setName] = useState(app.name || "");
  const [branch, setBranch] = useState(app.branch || "main");
  const [build, setBuild] = useState(app.build_command || "");
  const [start, setStart] = useState(app.start_command || "");
  const [auto, setAuto] = useState(app.auto_deploy !== false);
  const [tier, setTier] = useState(app.tier || "development");
  const [protectedBranches, setProtectedBranches] = useState((app.protected_branches || ["main"]).join(", "));
  const [saving, setSaving] = useState(false);

  const protectedList = protectedBranches.split(",").map((s) => s.trim()).filter(Boolean);
  const initialProtected = (app.protected_branches || ["main"]).join(",");

  const dirty =
    name !== (app.name || "") ||
    branch !== (app.branch || "main") ||
    build !== (app.build_command || "") ||
    start !== (app.start_command || "") ||
    auto !== (app.auto_deploy !== false) ||
    tier !== (app.tier || "development") ||
    protectedList.join(",") !== initialProtected;

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await api.patch(`/apps/${app.id}`, {
        name, branch, build_command: build, start_command: start, auto_deploy: auto,
        tier, protected_branches: protectedList.length ? protectedList : ["main"],
      });
      toast.success("Settings saved");
      onSaved?.(res.data);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally { setSaving(false); }
  };

  return (
    <form onSubmit={save} className="space-y-5 max-w-2xl" data-testid="settings-form">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">App name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required minLength={1} maxLength={80}
            className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="settings-name-input"
          />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 inline-flex items-center gap-1">
            <GitBranch className="h-3 w-3" /> Default branch
          </label>
          <input value={branch} onChange={(e) => setBranch(e.target.value)}
            className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="settings-branch-input"
          />
          <div className="text-[11px] text-zinc-500 mt-1 font-mono">Used when no specific branch is picked at deploy time.</div>
        </div>
      </div>

      <div>
        <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Build command</label>
        <input value={build} onChange={(e) => setBuild(e.target.value)}
          placeholder="yarn build (auto-detected if empty)"
          className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
          data-testid="settings-build-input"
        />
      </div>
      <div>
        <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Start command</label>
        <input value={start} onChange={(e) => setStart(e.target.value)}
          placeholder="yarn start (auto-detected if empty)"
          className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
          data-testid="settings-start-input"
        />
      </div>

      <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
        <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} data-testid="settings-auto-deploy" />
        Auto-deploy on every push to <span className="font-mono text-brand">{branch}</span>
      </label>

      {/* Tier + branch protection */}
      <div className="border border-white/10 p-4 bg-elevated/30 space-y-3">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">
          <ShieldCheck className="h-3 w-3 text-brand" /> Branch protection
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-mono text-zinc-400">Environment tier</label>
            <select value={tier} onChange={(e) => setTier(e.target.value)}
              className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
              data-testid="settings-tier-select"
            >
              <option value="development">Development — anyone can deploy any branch</option>
              <option value="production">Production — only protected branches allowed</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-mono text-zinc-400">Allowed branches (CSV)</label>
            <input value={protectedBranches} onChange={(e) => setProtectedBranches(e.target.value)}
              placeholder="main, release"
              disabled={tier !== "production"}
              className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none disabled:opacity-50"
              data-testid="settings-protected-input"
            />
          </div>
        </div>
        <div className="text-[11px] font-mono text-zinc-500">
          {tier === "production"
            ? `Production tier: deploys + rollbacks are blocked unless the branch is one of [${protectedList.join(", ") || "main"}].`
            : "Development tier: any branch can be deployed."}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button type="submit" disabled={!dirty || saving}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50"
          data-testid="settings-save-btn"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save changes
        </button>
        {dirty && <span className="text-xs font-mono text-signal-queued">unsaved changes</span>}
      </div>
    </form>
  );
}

export default function AppDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState("overview");
  const [app, setApp] = useState(null);
  const [deployments, setDeployments] = useState([]);
  const [domains, setDomains] = useState([]);
  const [envVars, setEnvVars] = useState({});
  const [monitoring, setMonitoring] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [domainWizardOpen, setDomainWizardOpen] = useState(false);
  const [deployOpen, setDeployOpen] = useState(false);

  const load = useCallback(async () => {
    const [a, d, e, m] = await Promise.all([
      api.get(`/apps/${id}`),
      api.get(`/apps/${id}/deployments`),
      api.get(`/apps/${id}/env`),
      api.get(`/apps/${id}/monitoring`),
    ]);
    setApp(a.data);
    setDeployments(d.data);
    setEnvVars(e.data.env_vars || {});
    setMonitoring(m.data);
    const ws = a.data.workspace_id;
    const domsRes = await api.get("/domains", { params: { workspace_id: ws } });
    setDomains(domsRes.data.filter((x) => x.app_id === id));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!app) return;
    if (app.status === "building" || app.status === "queued") {
      const i = setInterval(load, 5000);
      return () => clearInterval(i);
    }
  }, [app, load]);

  const restart = async () => {
    setBusy(true);
    try { await api.post(`/apps/${id}/restart`); toast.success("App restart triggered"); }
    catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    if (!window.confirm("Delete this app? This cannot be undone.")) return;
    await api.delete(`/apps/${id}`);
    navigate("/app");
  };

  const rollback = async (deploymentId) => {
    if (!window.confirm("Rollback to this deployment? A new deploy will be triggered with that branch and commit.")) return;
    try {
      const { data } = await api.post(`/apps/${id}/rollback/${deploymentId}`);
      toast.success(`Rollback queued · ${data.branch}${data.commit_sha ? ` @ ${data.commit_sha.slice(0, 7)}` : ""}`);
      load();
    } catch (e) {
      toast.error(getApiErrorMessage(e));
    }
  };

  const saveEnv = async (next) => {
    await api.put(`/apps/${id}/env`, { env_vars: next });
    setEnvVars(next);
  };

  const verifyDomain = async (did) => { await api.post(`/domains/${did}/verify`); load(); };
  const removeDomain = async (did) => { await api.delete(`/domains/${did}`); load(); };

  // Live SSE stream while the latest deployment is in-flight
  const latestDeploy0 = deployments[0];
  const isInFlight = !!latestDeploy0 && (latestDeploy0.status === "queued" || latestDeploy0.status === "building");
  const initialLines = latestDeploy0?.parsed_logs || (latestDeploy0?.logs || []).map((t) => ({ text: t, severity: "info" }));
  const stream = useDeploymentStream(latestDeploy0?.id, {
    active: isInFlight,
    initialLines,
    onStatusChange: () => load(),
  });

  if (!app) return <div className="p-6 text-zinc-500 font-mono text-sm">Loading app…</div>;

  const latestDeploy = latestDeploy0;
  const liveLines = isInFlight ? stream.lines : initialLines;

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
            <button onClick={() => setDeployOpen(true)} disabled={busy}
              className="inline-flex items-center gap-2 px-3 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition shadow-[0_0_18px_rgba(0,229,255,0.25)] text-sm"
              data-testid="app-deploy-cta"
            >
              <Rocket className="h-4 w-4" /> Deploy
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
        <div className="p-6 space-y-6">
          <DeploymentStatus app={app} latest={latestDeploy} history={deployments} onRedeploy={() => setDeployOpen(true)} />

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            <div className="lg:col-span-3">
              <SitePreview appId={id} monitoring={monitoring} />
            </div>
            <div className="lg:col-span-2 border border-white/[0.06] bg-background p-5">
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500 mb-2">// build log</div>
              <TerminalLog
                title={latestDeploy ? `${latestDeploy.status}.log` : "no.log"}
                lines={liveLines}
                height={420}
                live={isInFlight}
                connected={stream.connected}
              />
            </div>
          </div>

          {latestDeploy?.status === "failed" && (
            <BuildErrorPanel deployment={latestDeploy} onRetry={() => setDeployOpen(true)} />
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.06] border border-white/[0.06]">
            <div className="bg-background p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Repository</div>
              <div className="text-sm font-mono break-all mt-1 truncate">{app.repo_url.replace(/^https?:\/\//, "")}</div>
            </div>
            <div className="bg-background p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Last deploy</div>
              <div className="text-sm mt-1">{timeAgo(app.last_deploy_at)}</div>
            </div>
            <div className="bg-background p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Tier</div>
              <div className="text-sm mt-1 inline-flex items-center gap-1.5 capitalize">
                {app.tier === "production" ? <ShieldCheck className="h-3 w-3 text-brand" /> : null}
                {app.tier || "development"}
              </div>
            </div>
            <div className="bg-background p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">Auto-deploy</div>
              <div className="text-sm mt-1">{app.auto_deploy === false ? "off" : `on · ${app.branch}`}</div>
            </div>
          </div>
        </div>
      )}

      {tab === "deployments" && (
        <div className="p-6">
          <div className="border-t border-l border-white/[0.06]">
            <div className="grid grid-cols-12 px-4 py-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 border-r border-b border-white/[0.06]">
              <div className="col-span-2">Status</div>
              <div className="col-span-2">Commit</div>
              <div className="col-span-3">Branch / message</div>
              <div className="col-span-2">Duration</div>
              <div className="col-span-2">Started</div>
              <div className="col-span-1 text-right">Actions</div>
            </div>
            {deployments.map((d, idx) => {
              const isCurrent = idx === 0 && (d.status === "live" || d.status === "building" || d.status === "queued");
              const inFlight = d.status === "queued" || d.status === "building";
              const canRollback = !isCurrent && !inFlight;
              return (
                <div key={d.id} className="grid grid-cols-12 px-4 py-3 border-r border-b border-white/[0.06] items-center text-sm" data-testid={`deployment-${d.id}`}>
                  <div className="col-span-2"><StatusBadge status={d.status} /></div>
                  <div className="col-span-2 font-mono text-xs flex items-center gap-1.5">
                    <GitCommit className="h-3 w-3 text-brand" />
                    {d.commit_sha ? d.commit_sha.slice(0, 7) : "HEAD"}
                  </div>
                  <div className="col-span-3">
                    <div className="text-xs font-mono text-zinc-400 inline-flex items-center gap-1.5">
                      <GitBranch className="h-3 w-3" /> {d.branch || app.branch}
                    </div>
                    <div className="text-xs text-zinc-500 truncate">{d.commit_message}</div>
                  </div>
                  <div className="col-span-2 font-mono text-xs">{fmtDuration(d.started_at, d.finished_at)}</div>
                  <div className="col-span-2 text-xs font-mono text-zinc-500">{timeAgo(d.started_at)}</div>
                  <div className="col-span-1 text-right">
                    {canRollback ? (
                      <button
                        onClick={() => rollback(d.id)}
                        className="inline-flex items-center gap-1 px-2 py-1 border border-white/15 hover:border-brand hover:text-brand text-[11px] font-mono uppercase tracking-wider"
                        data-testid={`rollback-${d.id}`}
                        title="Rollback to this deployment"
                      >
                        <Undo2 className="h-3 w-3" /> rollback
                      </button>
                    ) : isCurrent ? (
                      <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand">// current</span>
                    ) : (
                      <span className="text-[10px] font-mono text-zinc-600">—</span>
                    )}
                  </div>
                </div>
              );
            })}
            {deployments.length === 0 && <div className="p-10 text-zinc-500 text-sm">No deployments yet.</div>}
          </div>
        </div>
      )}

      {tab === "domains" && (
        <div className="p-6 max-w-3xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="font-display text-xl tracking-tight">Custom domains</div>
              <div className="text-xs font-mono text-zinc-500 mt-1">Each domain gets its own Let's Encrypt certificate automatically.</div>
            </div>
            <button
              onClick={() => setDomainWizardOpen(true)}
              className="magnetic-btn inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90"
              data-testid="domain-add"
            >
              <Plus className="h-4 w-4" /> Add domain
            </button>
          </div>
          {error && <div className="mb-4 text-signal-failed text-sm">{error}</div>}
          <div className="border-t border-l border-white/[0.06]">
            {domains.map((d) => (
              <div key={d.id} className="flex items-center justify-between p-4 border-r border-b border-white/[0.06]">
                <div>
                  <a href={`https://${d.domain}`} target="_blank" rel="noreferrer" className="font-mono text-sm hover:text-brand">{d.domain}</a>
                  <div className="mt-1 flex items-center gap-2 text-xs font-mono text-zinc-500">
                    <StatusBadge status={d.dns_verified ? "live" : "pending"} />
                    SSL: {d.ssl_status}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {!d.dns_verified && (
                    <button onClick={() => verifyDomain(d.id)} className="text-xs font-mono text-brand hover:underline" data-testid={`domain-verify-${d.id}`}>check dns</button>
                  )}
                  <button onClick={() => removeDomain(d.id)} className="text-xs font-mono text-signal-failed hover:underline">remove</button>
                </div>
              </div>
            ))}
            {domains.length === 0 && <div className="p-10 text-zinc-500 text-sm text-center">No custom domains yet. Click "Add domain" to get started.</div>}
          </div>
          <AddDomainWizard
            open={domainWizardOpen}
            onClose={() => setDomainWizardOpen(false)}
            onCreated={load}
            presetAppId={id}
          />
        </div>
      )}

      {tab === "env" && (
        <div className="p-6 max-w-3xl">
          <EnvVarsEditor envVars={envVars} onSave={saveEnv} />
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
        <div className="p-6">
          <SettingsForm app={app} onSaved={(updated) => setApp(updated)} />
          <div className="mt-10 max-w-2xl border border-signal-failed/30 p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-signal-failed">Danger zone</div>
            <div className="mt-2 flex items-center justify-between gap-4">
              <span className="text-sm">Permanently delete this app and its history.</span>
              <button onClick={remove} className="px-3 py-1.5 text-sm border border-signal-failed/40 text-signal-failed hover:bg-signal-failed/10" data-testid="settings-delete-app">
                Delete app
              </button>
            </div>
          </div>
        </div>
      )}

      <DeployModal app={app} open={deployOpen} onClose={() => setDeployOpen(false)} onDeployed={() => load()} />
    </div>
  );
}

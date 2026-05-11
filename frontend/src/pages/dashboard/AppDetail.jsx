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
import AppResourcesTab from "../../components/AppResourcesTab";
import AppAnalyticsPanel from "../../components/AppAnalyticsPanel";
import AppWebAnalyticsTab from "../../components/AppWebAnalyticsTab";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import AddDomainWizard from "../../components/AddDomainWizard";
import useDeploymentStream from "../../hooks/useDeploymentStream";
import {
  ChevronLeft, RotateCw, RefreshCcw, Trash2, GitBranch, GitCommit,
  ExternalLink, Plus, Save, Loader2, Rocket, ShieldCheck, Undo2,
  Webhook, Copy, Eye, EyeOff, RefreshCw, Clock, GitPullRequest,
  Boxes, ArrowRightLeft, ChevronDown, ChevronRight, Terminal, AlertOctagon,
  PauseCircle, PlayCircle,
} from "lucide-react";
import { toast } from "sonner";

const TABS = ["overview", "deployments", "console", "domains", "env", "resources", "monitoring", "analytics", "settings"];

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

/**
 * One row in the Deployments tab — collapsed by default, expand to show
 * the full build log + failure summary. This is the "build logs history per
 * deployment" feature: every past deploy is replayable.
 */
function DeploymentRow({ deployment: d, appBranch, isCurrent, canRollback, onRollback, onReinstall, onRetry }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  const expand = async () => {
    const next = !open;
    setOpen(next);
    if (next && !detail) {
      setLoading(true);
      try {
        const r = await api.get(`/deployments/${d.id}/logs`);
        setDetail(r.data);
      } catch (e) {
        setDetail({ logs: [`Failed to load logs: ${e.message}`], parsed_logs: [], status: d.status });
      } finally { setLoading(false); }
    }
  };

  return (
    <div className="border-r border-b border-white/[0.06]">
      <button
        onClick={expand}
        className="w-full grid grid-cols-12 px-4 py-3 items-center text-sm text-left hover:bg-white/[0.02] transition-colors"
        data-testid={`deployment-${d.id}`}
      >
        <div className="col-span-2 inline-flex items-center gap-2">
          {open ? <ChevronDown className="h-3 w-3 text-zinc-500" /> : <ChevronRight className="h-3 w-3 text-zinc-500" />}
          <StatusBadge status={d.status} />
        </div>
        <div className="col-span-2 font-mono text-xs flex items-center gap-1.5">
          <GitCommit className="h-3 w-3 text-brand" />
          {d.commit_sha ? d.commit_sha.slice(0, 7) : "HEAD"}
        </div>
        <div className="col-span-3 min-w-0 pr-3">
          <div className="text-xs font-mono text-zinc-400 inline-flex items-center gap-1.5">
            <GitBranch className="h-3 w-3" /> {d.branch || appBranch}
            {d.trigger && d.trigger !== "?" && (
              <span className="ml-2 text-[10px] text-zinc-500 uppercase tracking-wider">· {d.trigger}</span>
            )}
          </div>
          <div className="text-xs text-zinc-500 truncate">{d.commit_message}</div>
        </div>
        <div className="col-span-2 font-mono text-xs">{fmtDuration(d.started_at, d.finished_at)}</div>
        <div className="col-span-2 text-xs font-mono text-zinc-500">{timeAgo(d.started_at)}</div>
        <div className="col-span-1 text-right">
          {canRollback ? (
            <span
              onClick={(e) => { e.stopPropagation(); onRollback(); }}
              className="inline-flex items-center gap-1 px-2 py-1 border border-white/15 hover:border-brand hover:text-brand text-[11px] font-mono uppercase tracking-wider cursor-pointer"
              data-testid={`rollback-${d.id}`}
              title="Rollback to this deployment"
            >
              <Undo2 className="h-3 w-3" /> rollback
            </span>
          ) : isCurrent ? (
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-brand">// current</span>
          ) : (
            <span className="text-[10px] font-mono text-zinc-600">—</span>
          )}
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4 bg-elevated/20 border-t border-white/[0.04]" data-testid={`deployment-${d.id}-expanded`}>
          {loading && <div className="py-4 text-xs font-mono text-zinc-500">Loading logs…</div>}
          {detail && (
            <>
              {detail.status === "failed" && (
                <div className="my-3">
                  <BuildErrorPanel deployment={detail} onRetry={onRetry} onReinstall={onReinstall} />
                </div>
              )}
              <div className="mt-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">// build log · {detail.logs?.length || 0} lines</div>
                  <a
                    href={`/api/deployments/${d.id}/logs`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[10px] uppercase tracking-[0.2em] font-mono text-zinc-500 hover:text-brand inline-flex items-center gap-1"
                  >
                    raw json <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
                <TerminalLog
                  title={`${detail.status}.log`}
                  lines={detail.parsed_logs && detail.parsed_logs.length ? detail.parsed_logs : (detail.logs || []).map((t) => ({ text: t, severity: "info" }))}
                  height={420}
                />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Console (runtime) logs tab — fetches container stdout/stderr from the
 * build engine on a 5s poll. Shows a "Reinstall" CTA when the app is gone
 * on the build engine instead of an opaque "no logs" message.
 */
function ConsoleLogsTab({ appId, appStatus, onReinstall }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [paused, setPaused] = useState(false);
  const [linesToLoad, setLinesToLoad] = useState(200);

  const fetchLogs = useCallback(async () => {
    try {
      const r = await api.get(`/apps/${appId}/console-logs`, { params: { lines: linesToLoad } });
      setData(r.data);
      setError("");
    } catch (e) {
      setError(getApiErrorMessage(e));
    }
  }, [appId, linesToLoad]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);
  useEffect(() => {
    if (paused) return;
    const i = setInterval(fetchLogs, 5000);
    return () => clearInterval(i);
  }, [paused, fetchLogs]);

  const lines = (data?.lines || []).map((t) => ({
    text: t,
    severity: /\b(error|exception|failed|fatal)\b/i.test(t) ? "error"
      : /\b(warn(ing)?)\b/i.test(t) ? "warn"
      : "info",
  }));

  const banner = !data?.available && data?.reason ? (
    <div className="border border-signal-queued/30 bg-signal-queued/[0.04] p-4 mb-4">
      <div className="flex items-start gap-3">
        <AlertOctagon className="h-5 w-5 text-signal-queued flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-signal-queued mb-1">
            // {(data.reason || "").replaceAll("_", " ")}
          </div>
          <div className="text-sm text-zinc-200">
            {data.message || "Console logs aren't available for this app right now."}
          </div>
          {data.reason === "build_engine_missing" && onReinstall && (
            <button
              onClick={onReinstall}
              className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 bg-brand text-brand-fg text-xs font-mono uppercase tracking-wider hover:bg-brand/90"
              data-testid="console-reinstall"
            >
              <RefreshCw className="h-3 w-3" /> Reinstall on build engine
            </button>
          )}
        </div>
      </div>
    </div>
  ) : null;

  return (
    <div className="p-6 space-y-3" data-testid="console-tab">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-brand" />
            <h2 className="font-display text-xl">Runtime console</h2>
          </div>
          <p className="text-xs font-mono text-zinc-500 mt-1">
            Live container stdout/stderr from the build engine — auto-refresh every 5s.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={linesToLoad}
            onChange={(e) => setLinesToLoad(Number(e.target.value))}
            className="bg-black border border-white/10 px-2 py-1.5 text-xs font-mono focus:border-brand outline-none"
            data-testid="console-lines-select"
          >
            <option value={100} className="bg-black">100 lines</option>
            <option value={200} className="bg-black">200 lines</option>
            <option value={500} className="bg-black">500 lines</option>
            <option value={1000} className="bg-black">1000 lines</option>
          </select>
          <button
            onClick={() => setPaused((p) => !p)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-white/15 hover:border-brand text-xs font-mono uppercase tracking-wider"
            data-testid="console-pause"
          >
            {paused ? <><PlayCircle className="h-3 w-3" /> resume</> : <><PauseCircle className="h-3 w-3" /> pause</>}
          </button>
          <button
            onClick={fetchLogs}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-white/15 hover:border-brand text-xs font-mono uppercase tracking-wider"
            data-testid="console-refresh"
          >
            <RefreshCw className="h-3 w-3" /> refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="border border-signal-failed/30 bg-signal-failed/[0.06] p-3 text-sm text-signal-failed">
          {error}
        </div>
      )}

      {banner}

      <TerminalLog
        title={data?.available ? `console.log · ${appStatus} · ${data.count || lines.length} lines` : "console.log"}
        lines={lines.length ? lines : data?.available === false ? [] : [{ text: "Loading runtime logs...", severity: "info" }]}
        height={620}
        live={!paused && !!data?.available}
        connected={!paused && !!data?.available}
      />
    </div>
  );
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

  const reinstall = async () => {
    if (!window.confirm(
      "Reinstall on the build engine?\n\nThis will recreate the application from scratch using your repo URL and branch. " +
      "It's the fix when the build-engine app got deleted out-of-band. Your app's settings stay intact."
    )) return;
    setBusy(true);
    try {
      const r = await api.post(`/apps/${id}/reinstall`);
      toast.success(`Reinstall queued — deployment ${(r.data?.id || "").slice(0, 8)}`);
      load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
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
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="font-display text-4xl font-semibold tracking-tighter">{app.name}</h1>
              <StatusBadge status={app.status} />
              <EnvBadge env={app.environment} paired={!!app.paired_app_id} />
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
            <BuildErrorPanel deployment={latestDeploy} onRetry={() => setDeployOpen(true)} onReinstall={reinstall} />
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
          <div className="text-xs font-mono text-zinc-500 mb-4">
            Click any row to expand the full build log. Failed deployments show the parsed error summary at the top.
          </div>
          <div className="border-t border-l border-white/[0.06]">
            <div className="grid grid-cols-12 px-4 py-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 border-r border-b border-white/[0.06]">
              <div className="col-span-2">Status</div>
              <div className="col-span-2">Commit</div>
              <div className="col-span-3">Branch / message</div>
              <div className="col-span-2">Duration</div>
              <div className="col-span-2">Started</div>
              <div className="col-span-1 text-right">Actions</div>
            </div>
            {deployments.map((d, idx) => (
              <DeploymentRow
                key={d.id}
                deployment={d}
                appBranch={app.branch}
                isCurrent={idx === 0 && (d.status === "live" || d.status === "building" || d.status === "queued")}
                canRollback={!(idx === 0) && d.status !== "queued" && d.status !== "building"}
                onRollback={() => rollback(d.id)}
                onReinstall={reinstall}
                onRetry={() => setDeployOpen(true)}
                appId={id}
              />
            ))}
            {deployments.length === 0 && <div className="p-10 text-zinc-500 text-sm">No deployments yet.</div>}
          </div>
        </div>
      )}

      {tab === "console" && (
        <ConsoleLogsTab appId={id} appStatus={app.status} onReinstall={reinstall} />
      )}

      {tab === "analytics" && (
        <AppWebAnalyticsTab appId={id} />
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

      {tab === "resources" && (
        <AppResourcesTab appId={id} />
      )}

      {tab === "monitoring" && (
        <AppAnalyticsPanel appId={id} />
      )}

      {tab === "settings" && (
        <div className="p-6 space-y-10">
          <SettingsForm app={app} onSaved={(updated) => setApp(updated)} />
          <EnvironmentPairSection app={app} onChange={load} />
          <WebhookSection appId={app.id} />
          <CronJobsSection appId={app.id} />
          <PRPreviewsSection appId={app.id} />
          <MoveAppSection app={app} />
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

/* ─────────────────────── GitHub Webhook section ─────────────────────── */
function WebhookSection({ appId }) {
  const [data, setData] = useState(null);
  const [showSecret, setShowSecret] = useState(false);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/apps/${appId}/webhook`);
      setData(r.data);
    } catch (e) { /* ignore */ }
  }, [appId]);
  useEffect(() => { load(); }, [load]);

  const copy = (txt, label) => {
    navigator.clipboard.writeText(txt || "");
    toast.success(`${label} copied`);
  };

  const toggle = async () => {
    setBusy("toggle");
    try {
      const r = await api.post(`/apps/${appId}/webhook/toggle`);
      setData((d) => ({ ...d, enabled: r.data.enabled }));
      toast.success(`Auto-deploy ${r.data.enabled ? "enabled" : "disabled"}`);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(""); }
  };

  const rotate = async () => {
    if (!window.confirm("Rotate the webhook secret? The old one will stop working immediately and the new one will be re-registered with GitHub.")) return;
    setBusy("rotate");
    try {
      const r = await api.post(`/apps/${appId}/webhook/rotate`);
      setData((d) => ({ ...d, secret: r.data.secret }));
      toast.success("Secret rotated · re-registering with GitHub…");
      // GitHub re-registration runs in background; reload after a beat.
      setTimeout(load, 1800);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(""); }
  };

  const registerNow = async () => {
    setBusy("register");
    try {
      const r = await api.post(`/apps/${appId}/webhook/register`);
      if (r.data.registered) {
        toast.success("Webhook registered with GitHub");
      } else {
        toast.error(`Could not register: ${r.data.reason}. Add it manually below.`);
      }
      load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(""); }
  };

  if (!data) return null;
  const maskedSecret = data.secret ? (showSecret ? data.secret : "•".repeat(Math.min(data.secret.length, 32))) : "—";

  return (
    <section className="max-w-3xl border border-white/[0.06] p-6 space-y-5" data-testid="webhook-section">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <Webhook className="h-4 w-4 text-brand" />
            <h2 className="font-display text-xl">Auto-deploy on push</h2>
          </div>
          <p className="text-xs text-zinc-500 mt-1">
            Every push to <span className="text-brand font-mono">{data.branch}</span> triggers a fresh deployment.
          </p>
        </div>
        <button
          onClick={toggle}
          disabled={busy === "toggle"}
          className={`h-7 w-14 relative rounded-full transition-colors ${data.enabled ? "bg-brand" : "bg-white/[0.1]"} disabled:opacity-50`}
          data-testid="webhook-toggle"
          aria-pressed={data.enabled}
          aria-label={`Auto-deploy ${data.enabled ? "on" : "off"}`}
        >
          <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-black transition-all ${data.enabled ? "left-[30px]" : "left-0.5"}`} />
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-1">Webhook URL</div>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-black border border-white/10 px-3 py-2 text-xs text-brand truncate font-mono" data-testid="webhook-url">{data.url}</code>
            <button onClick={() => copy(data.url, "URL")} className="px-2.5 py-2 border border-white/10 hover:border-brand/70 hover:text-brand">
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-1">Secret (HMAC-SHA256)</div>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-black border border-white/10 px-3 py-2 text-xs text-zinc-300 truncate font-mono" data-testid="webhook-secret">{maskedSecret}</code>
            <button onClick={() => setShowSecret((v) => !v)} className="px-2.5 py-2 border border-white/10 hover:border-brand/70 hover:text-brand" data-testid="webhook-secret-toggle">
              {showSecret ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
            <button onClick={() => copy(data.secret, "Secret")} disabled={!data.secret} className="px-2.5 py-2 border border-white/10 hover:border-brand/70 hover:text-brand disabled:opacity-40">
              <Copy className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4 flex-wrap pt-2 border-t border-white/[0.04]">
        <div className="text-xs font-mono text-zinc-500">
          {data.auto_registered ? (
            <span className="text-signal-live">✓ Registered with GitHub (hook #{data.github_hook_id})</span>
          ) : (
            <span>Not auto-registered. <button onClick={registerNow} disabled={busy === "register"} className="text-brand hover:underline" data-testid="webhook-register-now">register now</button> or add it manually in your repo's <code className="text-zinc-300">Settings → Webhooks</code>.</span>
          )}
        </div>
        <button
          onClick={rotate}
          disabled={busy === "rotate"}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-white/10 hover:border-brand/50 disabled:opacity-50"
          data-testid="webhook-rotate"
        >
          <RefreshCw className={`h-3 w-3 ${busy === "rotate" ? "animate-spin" : ""}`} /> rotate secret
        </button>
      </div>

      <details className="text-[11px] text-zinc-500 font-mono">
        <summary className="cursor-pointer hover:text-zinc-300">Manual setup instructions</summary>
        <ol className="mt-3 space-y-1.5 list-decimal list-inside leading-relaxed">
          <li>Open your repo on GitHub → <span className="text-zinc-300">Settings → Webhooks → Add webhook</span></li>
          <li>Payload URL: <code className="text-brand">{data.url}</code></li>
          <li>Content type: <code className="text-zinc-300">application/json</code></li>
          <li>Secret: paste the value above</li>
          <li>Events: <code className="text-zinc-300">Just the push event</code></li>
          <li>Save. GitHub will send a ping — we'll reply <code className="text-zinc-300">pong</code> on success.</li>
        </ol>
      </details>
    </section>
  );
}

/* ─────────────────────── Cron Jobs section ─────────────────────── */
function CronJobsSection({ appId }) {
  const [data, setData] = useState({ jobs: [], supports_build_engine_sync: false });
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // null = closed, "new" = creating, {id} = editing existing
  const [form, setForm] = useState({ name: "", command: "", schedule: "0 3 * * *", enabled: true });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(`/apps/${appId}/cron`);
      setData(r.data);
    } catch (e) { /* ignore */ }
    finally { setLoading(false); }
  }, [appId]);
  useEffect(() => { load(); }, [load]);

  const startNew = () => { setForm({ name: "", command: "", schedule: "0 3 * * *", enabled: true }); setEditing("new"); };
  const startEdit = (j) => { setForm({ name: j.name, command: j.command, schedule: j.schedule, enabled: j.enabled }); setEditing(j.id); };

  const save = async () => {
    if (!form.name.trim() || !form.command.trim() || !form.schedule.trim()) { toast.error("All fields required"); return; }
    setBusy(true);
    try {
      if (editing === "new") {
        await api.post(`/apps/${appId}/cron`, form);
        toast.success("Cron job created");
      } else {
        await api.put(`/apps/${appId}/cron/${editing}`, form);
        toast.success("Cron job updated");
      }
      setEditing(null);
      load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const remove = async (id, name) => {
    if (!window.confirm(`Delete cron job "${name}"?`)) return;
    try {
      await api.delete(`/apps/${appId}/cron/${id}`);
      toast.success("Cron job deleted");
      load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };

  return (
    <section className="max-w-3xl border border-white/[0.06] p-6 space-y-5" data-testid="cron-section">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-brand" />
            <h2 className="font-display text-xl">Scheduled jobs</h2>
          </div>
          <p className="text-xs text-zinc-500 mt-1">
            Run commands on a schedule inside your app's container. {data.supports_build_engine_sync ? "Synced with build engine." : "Will sync to build engine on next deploy."}
          </p>
        </div>
        {editing === null && (
          <button onClick={startNew} className="inline-flex items-center gap-2 px-3 py-2 border border-white/10 hover:border-brand/50 text-xs font-mono" data-testid="cron-new">
            <Plus className="h-3 w-3" /> New cron
          </button>
        )}
      </div>

      {editing !== null && (
        <div className="border border-brand/30 p-4 space-y-3" data-testid="cron-form">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Job name" className="bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none" data-testid="cron-form-name" />
            <input value={form.schedule} onChange={(e) => setForm({ ...form, schedule: e.target.value })} placeholder="0 3 * * *" className="bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none" data-testid="cron-form-schedule" />
          </div>
          <textarea value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })} placeholder="node scripts/cleanup.js" rows={2} className="w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none" data-testid="cron-form-command" />
          <div className="text-[10px] font-mono text-zinc-600">
            Format: 5-field cron. Try <code className="text-brand">0 3 * * *</code> (3am daily), <code className="text-brand">*/15 * * * *</code> (every 15 min), <code className="text-brand">0 0 * * 0</code> (Sunday midnight).
          </div>
          <div className="flex items-center gap-2">
            <button onClick={save} disabled={busy} className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50" data-testid="cron-form-save">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save
            </button>
            <button onClick={() => setEditing(null)} className="px-3 py-2 border border-white/10 text-xs font-mono">cancel</button>
          </div>
        </div>
      )}

      {data.jobs.length === 0 && !loading && editing === null && (
        <div className="text-xs font-mono text-zinc-500 py-4">No scheduled jobs yet.</div>
      )}

      {data.jobs.length > 0 && (
        <div className="border border-white/[0.06] divide-y divide-white/[0.04]">
          {data.jobs.map((j) => (
            <div key={j.id} className="grid grid-cols-[1fr_140px_auto] gap-4 items-center px-4 py-3" data-testid={`cron-row-${j.id}`}>
              <div>
                <div className="text-sm">{j.name}</div>
                <code className="text-[11px] font-mono text-zinc-500 truncate block">{j.command}</code>
              </div>
              <code className="text-xs font-mono text-brand">{j.schedule}</code>
              <div className="flex items-center gap-1">
                <button onClick={() => startEdit(j)} className="px-2 py-1.5 text-xs border border-white/10 hover:border-brand/50" data-testid={`cron-edit-${j.id}`}>edit</button>
                <button onClick={() => remove(j.id, j.name)} className="px-2 py-1.5 text-xs border border-white/10 text-signal-failed hover:bg-signal-failed/10" data-testid={`cron-delete-${j.id}`}>
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ─────────────────────── PR Previews section ─────────────────────── */
function PRPreviewsSection({ appId }) {
  const [previews, setPreviews] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get(`/apps/${appId}/pr-previews`);
      setPreviews(r.data.previews || []);
    } catch (e) { /* ignore */ }
    finally { setLoading(false); }
  }, [appId]);
  useEffect(() => { load(); }, [load]);

  const teardown = async (id, pr) => {
    if (!window.confirm(`Tear down preview for PR #${pr}? The child app + DNS record will be deleted.`)) return;
    try {
      await api.delete(`/apps/${appId}/pr-previews/${id}`);
      toast.success("Preview torn down");
      load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };

  return (
    <section className="max-w-3xl border border-white/[0.06] p-6 space-y-4" data-testid="pr-previews-section">
      <div>
        <div className="flex items-center gap-2">
          <GitPullRequest className="h-4 w-4 text-brand" />
          <h2 className="font-display text-xl">PR Preview deploys</h2>
        </div>
        <p className="text-xs text-zinc-500 mt-1">
          Open a pull request on GitHub and we'll automatically build a preview at a unique URL.
          The preview is torn down when the PR is closed or merged.
          {previews.length === 0 && <span> Webhooks must be connected for this to work.</span>}
        </p>
      </div>

      {previews.length === 0 && !loading && (
        <div className="text-xs font-mono text-zinc-500 py-4">No active previews. Open a PR and refresh.</div>
      )}

      {previews.length > 0 && (
        <div className="border border-white/[0.06] divide-y divide-white/[0.04]">
          {previews.map((p) => (
            <div key={p.id} className="grid grid-cols-[60px_1fr_140px_auto] gap-4 items-center px-4 py-3" data-testid={`pr-row-${p.pr_number}`}>
              <div className="text-sm font-mono text-brand">#{p.pr_number}</div>
              <div>
                <div className="text-xs font-mono">{p.branch}</div>
                {p.primary_url && (
                  <a href={p.primary_url} target="_blank" rel="noreferrer" className="text-[11px] font-mono text-brand inline-flex items-center gap-1 mt-0.5 hover:underline">
                    {p.primary_url.replace(/^https?:\/\//, "")} <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
              <div className={`text-xs font-mono ${
                p.status === "building" ? "text-signal-queued" :
                p.status === "closed" ? "text-zinc-500" : "text-signal-live"
              }`}>● {p.status}</div>
              <div className="flex items-center gap-1">
                {p.status !== "closed" && (
                  <button onClick={() => teardown(p.id, p.pr_number)} className="px-2 py-1.5 text-xs border border-white/10 text-signal-failed hover:bg-signal-failed/10" data-testid={`pr-teardown-${p.pr_number}`}>
                    <Trash2 className="h-3 w-3" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}


/* ─────────────────────── Environment badge ─────────────────────── */
function EnvBadge({ env, paired }) {
  const isProd = (env || "production") === "production";
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.25em] border ${
        isProd ? "border-signal-live/40 text-signal-live" : "border-signal-queued/40 text-signal-queued"
      }`}
      title={paired ? "Linked to a counterpart" : "Not yet paired"}
      data-testid={`env-badge-${env || "production"}`}
    >
      {isProd ? "production" : "staging"}{paired ? " · linked" : ""}
    </span>
  );
}

/* ─────────────────────── Staging ↔ Production pair section ─────────────────────── */
function EnvironmentPairSection({ app, onChange }) {
  const [candidates, setCandidates] = useState([]);
  const [peer, setPeer] = useState(null);
  const [picking, setPicking] = useState(false);
  const [busy, setBusy] = useState("");
  const myEnv = app.environment || "production";
  const peerEnvLabel = myEnv === "production" ? "staging" : "production";

  const loadPeer = useCallback(async () => {
    if (!app.paired_app_id) { setPeer(null); return; }
    try {
      const r = await api.get(`/apps/${app.paired_app_id}`);
      setPeer(r.data);
    } catch (e) { setPeer({ id: app.paired_app_id, name: "(missing)", _stale: true }); }
  }, [app.paired_app_id]);

  const loadCandidates = useCallback(async () => {
    try {
      const r = await api.get(`/apps/${app.id}/pair-candidates`);
      setCandidates(r.data.candidates || []);
    } catch (e) { setCandidates([]); }
  }, [app.id]);

  useEffect(() => { loadPeer(); }, [loadPeer]);

  const startPick = async () => {
    await loadCandidates();
    setPicking(true);
  };

  const pair = async (peerId) => {
    setBusy("pair");
    try {
      await api.post(`/apps/${app.id}/pair`, { peer_app_id: peerId });
      toast.success("Linked");
      setPicking(false);
      onChange();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(""); }
  };

  const unpair = async () => {
    if (!window.confirm("Unlink this app from its counterpart? Promote will no longer work until you link again.")) return;
    setBusy("unpair");
    try {
      await api.post(`/apps/${app.id}/unpair`);
      toast.success("Unlinked");
      setPeer(null);
      onChange();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(""); }
  };

  const promote = async () => {
    if (!peer) return;
    const direction = `${app.name} (${myEnv}) → ${peer.name} (${peer.environment})`;
    if (!window.confirm(`Promote? This copies env vars + branch from "${app.name}" to "${peer.name}" and triggers a deploy on ${peer.name}.\n\nDirection: ${direction}`)) return;
    setBusy("promote");
    try {
      const r = await api.post(`/apps/${app.id}/promote`);
      toast.success(`Promoted → ${r.data.to.name} (deployment queued)`);
      onChange();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(""); }
  };

  return (
    <section className="max-w-3xl border border-white/[0.06] p-6 space-y-5" data-testid="env-pair-section">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-brand" />
            <h2 className="font-display text-xl">Staging & production</h2>
          </div>
          <p className="text-xs text-zinc-500 mt-1">
            Link a {peerEnvLabel} counterpart so you can promote env vars + the branch in one click after QA.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {peer && !peer._stale && (
            <button onClick={promote} disabled={busy === "promote"} className="inline-flex items-center gap-2 px-3 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50 text-sm" data-testid="env-promote">
              <Rocket className="h-3.5 w-3.5" /> Promote {myEnv} → {peer.environment}
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* This app */}
        <div className="border border-white/[0.08] p-4">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">This app</div>
          <div className="mt-2 flex items-center gap-2"><EnvBadge env={myEnv} paired /></div>
          <div className="text-sm mt-1 font-medium">{app.name}</div>
          <div className="text-[11px] font-mono text-zinc-500 mt-0.5">{app.branch}</div>
        </div>

        {/* Peer */}
        <div className="border border-white/[0.08] p-4 relative">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">{peerEnvLabel} counterpart</div>
          {peer && !peer._stale ? (
            <div className="mt-2">
              <div className="flex items-center gap-2"><EnvBadge env={peer.environment} paired /></div>
              <Link to={`/app/apps/${peer.id}`} className="text-sm mt-1 font-medium hover:text-brand block" data-testid="env-peer-link">{peer.name}</Link>
              <div className="text-[11px] font-mono text-zinc-500 mt-0.5">{peer.branch} · {peer.framework}</div>
              <button onClick={unpair} disabled={busy === "unpair"} className="mt-3 text-[11px] font-mono text-signal-failed hover:underline" data-testid="env-unpair">unlink</button>
            </div>
          ) : (
            <div className="mt-2">
              {!picking ? (
                <button onClick={startPick} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-brand/40 text-brand hover:bg-brand/10" data-testid="env-pair-open">
                  <Plus className="h-3 w-3" /> Link a {peerEnvLabel} app
                </button>
              ) : candidates.length === 0 ? (
                <div className="text-xs font-mono text-zinc-500">
                  No {peerEnvLabel} apps in this workspace. Create one first (set environment={peerEnvLabel} on app creation).
                </div>
              ) : (
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {candidates.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => pair(c.id)}
                      disabled={busy === "pair"}
                      className="w-full text-left px-3 py-2 border border-white/[0.06] hover:border-brand/50 text-xs font-mono"
                      data-testid={`env-pair-candidate-${c.id}`}
                    >
                      <div className="text-zinc-200">{c.name}</div>
                      <div className="text-zinc-500 text-[10px]">{c.branch} · {c.status || "queued"}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}


/* ─────────────────────── Move app between workspaces ─────────────────────── */
function MoveAppSection({ app }) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const { refresh: refreshWorkspaces, setActive } = useWorkspace();
  const nav = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get(`/apps/${app.id}/move-candidates`);
      setCandidates(r.data.candidates || []);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setLoading(false); }
  };

  const startMove = async () => { setOpen(true); await load(); };

  const move = async () => {
    if (!target) { toast.error("Pick a destination workspace"); return; }
    const tgt = candidates.find((c) => c.id === target);
    if (!tgt) return;
    if (!tgt.has_room) { toast.error("Destination workspace is at its plan limit"); return; }
    if (!window.confirm(`Move "${app.name}" to "${tgt.name}"?\n\nDeployments, domains, cron jobs and PR previews will follow.\nIf this app is paired with a staging/production peer in the source workspace, the link will be broken.\n\nThe build-engine resource itself stays in place — only ownership in DeployHub moves.`)) return;
    setBusy(true);
    try {
      const r = await api.post(`/apps/${app.id}/move`, { target_workspace_id: target });
      toast.success(`Moved to ${tgt.name}${r.data.unpaired ? " · staging/prod link removed" : ""}`);
      // Switch active workspace to destination so the user lands in the right context after refresh.
      await refreshWorkspaces();
      if (setActive) setActive(tgt.id);
      // Reload so all queries refetch under the new workspace.
      setTimeout(() => nav(`/app/apps/${app.id}`, { replace: true }), 400);
      setTimeout(() => window.location.reload(), 800);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <section className="max-w-3xl border border-white/[0.06] p-6 space-y-4" data-testid="move-app-section">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <Boxes className="h-4 w-4 text-brand" />
            <h2 className="font-display text-xl">Move to another workspace</h2>
          </div>
          <p className="text-xs text-zinc-500 mt-1">
            Re-parent this app to a different workspace or agency-client fleet. Deployments, domains, cron jobs and PR previews follow along.
          </p>
        </div>
        {!open && (
          <button onClick={startMove} className="inline-flex items-center gap-2 px-3 py-2 border border-white/10 hover:border-brand/50 text-xs font-mono" data-testid="move-app-open">
            <ArrowRightLeft className="h-3 w-3" /> Move…
          </button>
        )}
      </div>

      {open && (
        <div className="space-y-3">
          {loading && <div className="text-xs font-mono text-zinc-500">Loading workspaces…</div>}
          {!loading && candidates.length === 0 && (
            <div className="text-xs font-mono text-zinc-500">
              No other workspaces available. Create a second workspace first.
            </div>
          )}
          {candidates.length > 0 && (
            <div className="space-y-1.5">
              {candidates.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setTarget(c.id)}
                  disabled={!c.has_room}
                  className={`w-full text-left px-3 py-2.5 border transition-colors ${
                    target === c.id ? "border-brand bg-brand/5" :
                    c.has_room ? "border-white/[0.08] hover:border-white/30" : "border-white/[0.06] opacity-50 cursor-not-allowed"
                  }`}
                  data-testid={`move-app-candidate-${c.id}`}
                >
                  <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div>
                      <div className="text-sm">{c.name}</div>
                      <div className="text-[11px] font-mono text-zinc-500 mt-0.5">{c.type} · {c.plan}</div>
                    </div>
                    <div className="text-[11px] font-mono">
                      {c.has_room ? (
                        <span className="text-zinc-400">{c.apps_used}{c.apps_limit ? `/${c.apps_limit}` : ""} apps</span>
                      ) : (
                        <span className="text-signal-failed">at limit ({c.apps_used}/{c.apps_limit})</span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
          <div className="flex items-center gap-2 pt-2">
            <button onClick={move} disabled={busy || !target} className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-40 text-sm" data-testid="move-app-confirm">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRightLeft className="h-3.5 w-3.5" />} Move app
            </button>
            <button onClick={() => { setOpen(false); setTarget(""); }} className="px-3 py-2 border border-white/10 text-xs font-mono">cancel</button>
          </div>
        </div>
      )}
    </section>
  );
}


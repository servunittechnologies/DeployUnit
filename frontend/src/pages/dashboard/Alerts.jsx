import { useEffect, useState } from "react";
import { api, getApiErrorMessage } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import { BellRing, Plus, Trash2, X } from "lucide-react";

const TYPES = [
  { id: "app_down", label: "App is down", thresholdLabel: "consecutive failures", placeholder: "1" },
  { id: "slow_response", label: "Slow response", thresholdLabel: "ms", placeholder: "1500" },
  { id: "deployment_failure", label: "Deployment failed", thresholdLabel: "—", placeholder: "0" },
];

export default function Alerts() {
  const { active } = useWorkspace();
  const [rules, setRules] = useState([]);
  const [apps, setApps] = useState([]);
  const [open, setOpen] = useState(false);
  const [type, setType] = useState("app_down");
  const [threshold, setThreshold] = useState(1);
  const [appId, setAppId] = useState("");
  const [error, setError] = useState("");

  const load = () => {
    if (!active) return;
    Promise.all([
      api.get("/alerts", { params: { workspace_id: active.id } }),
      api.get("/apps", { params: { workspace_id: active.id } }),
    ]).then(([r, a]) => { setRules(r.data); setApps(a.data); });
  };
  useEffect(load, [active]);

  const create = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/alerts", {
        workspace_id: active.id,
        app_id: appId || null,
        type, threshold: parseInt(threshold) || 0,
        cooldown_seconds: 600,
        channels: ["in_app"],
        enabled: true,
      });
      setOpen(false);
      load();
    } catch (e) { setError(getApiErrorMessage(e)); }
  };

  const toggle = async (r) => { await api.patch(`/alerts/${r.id}`, { enabled: !r.enabled }); load(); };
  const remove = async (r) => { await api.delete(`/alerts/${r.id}`); load(); };
  const appName = (id) => apps.find((a) => a.id === id)?.name || "All apps";

  return (
    <div className="px-6 py-6" data-testid="alerts-page">
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// alerts</div>
          <h1 className="font-display text-4xl font-semibold tracking-tighter">Alert rules</h1>
          <p className="mt-1 text-sm text-zinc-400">Get notified when something breaks. Rules trigger in-app notifications.</p>
        </div>
        <button
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90"
          data-testid="alert-new"
        >
          <Plus className="h-4 w-4" /> New rule
        </button>
      </div>

      {rules.length === 0 ? (
        <div className="border border-dashed border-white/10 p-16 text-center">
          <BellRing className="h-10 w-10 text-zinc-600 mx-auto mb-4" />
          <h3 className="font-display text-2xl">No alert rules yet</h3>
          <p className="mt-2 text-zinc-400">Create a rule to be notified the moment something breaks.</p>
        </div>
      ) : (
        <div className="border-t border-l border-white/[0.06]">
          {rules.map((r) => (
            <div key={r.id} className="flex items-center justify-between p-4 border-r border-b border-white/[0.06]" data-testid={`alert-row-${r.id}`}>
              <div className="flex items-center gap-3">
                <span className={`h-2 w-2 rounded-full ${r.enabled ? "bg-signal-live animate-ping-soft" : "bg-zinc-600"}`} />
                <div>
                  <div className="text-sm">
                    <strong>{TYPES.find((t) => t.id === r.type)?.label || r.type}</strong>
                    {r.threshold ? <span className="text-zinc-500 font-mono"> · threshold {r.threshold}</span> : null}
                  </div>
                  <div className="text-xs font-mono text-zinc-500">scope: {appName(r.app_id)}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button onClick={() => toggle(r)} className="text-xs font-mono text-zinc-400 hover:text-brand">
                  {r.enabled ? "disable" : "enable"}
                </button>
                <button onClick={() => remove(r)} className="text-xs font-mono text-signal-failed hover:underline inline-flex items-center gap-1">
                  <Trash2 className="h-3 w-3" /> delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {open && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-elevated border border-white/10 max-w-md w-full p-6 relative animate-rise">
            <button onClick={() => setOpen(false)} className="absolute top-3 right-3 text-zinc-500 hover:text-white"><X className="h-4 w-4" /></button>
            <h3 className="font-display text-2xl">New alert rule</h3>
            <form onSubmit={create} className="mt-5 space-y-4">
              <div>
                <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Type</label>
                <select value={type} onChange={(e) => setType(e.target.value)} className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none" data-testid="alert-type-select">
                  {TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Threshold ({TYPES.find((t) => t.id === type)?.thresholdLabel})</label>
                <input
                  type="number" value={threshold} onChange={(e) => setThreshold(e.target.value)}
                  className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                  placeholder={TYPES.find((t) => t.id === type)?.placeholder}
                  data-testid="alert-threshold-input"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Apply to</label>
                <select value={appId} onChange={(e) => setAppId(e.target.value)} className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none" data-testid="alert-app-select">
                  <option value="">All apps in this workspace</option>
                  {apps.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </div>
              {error && <div className="text-signal-failed text-sm">{error}</div>}
              <div className="flex gap-2">
                <button type="submit" className="flex-1 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90" data-testid="alert-create-submit">Create</button>
                <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 border border-white/15">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

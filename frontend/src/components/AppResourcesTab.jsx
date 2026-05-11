import { useEffect, useState } from "react";
import { api, getApiErrorMessage } from "../lib/api";
import { Cpu, MemoryStick, HardDrive, Coins, Save, AlertCircle, Plus, Minus, Database, Link2, Trash2, Eye, EyeOff, Copy } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";

/**
 * The "Resources" tab on an app — manages CPU/memory/storage sliders +
 * credit cost, plus database attachments.
 */
export default function AppResourcesTab({ appId }) {
  const [data, setData] = useState(null);
  const [conns, setConns] = useState(null);
  const [saving, setSaving] = useState(false);
  const [extra, setExtra] = useState({ cpu_vcpu: 0, memory_mb: 0, storage_mb: 0 });

  const load = async () => {
    try {
      const [r, c] = await Promise.all([
        api.get(`/apps/${appId}/resources`),
        api.get(`/apps/${appId}/connections`),
      ]);
      setData(r.data);
      setExtra({
        cpu_vcpu: r.data.addons.cpu_vcpu || 0,
        memory_mb: r.data.addons.memory_mb || 0,
        storage_mb: r.data.addons.storage_mb || 0,
      });
      setConns(c.data);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [appId]);

  if (!data) return <div className="px-6 py-10 text-sm font-mono text-zinc-500" data-testid="resources-loading">Loading resources…</div>;

  const p = data.pricing;
  const eff = data.effective;
  const def = data.plan_default;
  // Live preview cost
  const cpuUnits = Math.ceil((extra.cpu_vcpu || 0) / p.cpu_unit_vcpu);
  const memUnits = Math.ceil((extra.memory_mb || 0) / p.memory_unit_mb);
  const storageUnits = Math.ceil((extra.storage_mb || 0) / p.storage_unit_mb);
  const newMonthlyCost = cpuUnits * p.cpu_credits_per_unit
    + memUnits * p.memory_credits_per_unit
    + storageUnits * p.storage_credits_per_unit;
  const delta = newMonthlyCost - (data.monthly_cost_credits || 0);
  const isUpgrade = delta > 0;
  const isDowngrade = delta < 0;

  const save = async () => {
    if (isUpgrade && !window.confirm(
      `Upgrade resources?\n\nThis will charge ${delta} credits/month (pro-rated for the rest of the period). New limits take effect on the next deploy.`
    )) return;
    setSaving(true);
    try {
      await api.put(`/apps/${appId}/resources`, {
        extra_cpu_vcpu: extra.cpu_vcpu,
        extra_memory_mb: extra.memory_mb,
        extra_storage_mb: extra.storage_mb,
      });
      toast.success(isUpgrade ? `Upgraded — ${delta} cr charged` : isDowngrade ? `Downgraded — ${-delta} cr refunded` : "Saved");
      await load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setSaving(false); }
  };

  return (
    <div className="p-6 space-y-8" data-testid="resources-tab">
      {/* ─── Resources ─── */}
      <section className="space-y-4">
        <div>
          <h2 className="font-display text-xl">Resources & limits</h2>
          <p className="text-xs font-mono text-zinc-500 mt-1">
            CPU, memory and storage enforced on the build engine at container level.
            Plan defaults are free; upgrades cost credits per month.
          </p>
        </div>

        {/* Current snapshot */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-white/[0.06] border border-white/[0.06]">
          <ResourceTile icon={Cpu}        label="CPU"     value={`${eff.cpu_vcpu.toFixed(2)} vCPU`}    hint={`plan default: ${def.cpu_vcpu} · addon: +${data.addons.cpu_vcpu}`} />
          <ResourceTile icon={MemoryStick} label="Memory" value={`${eff.memory_mb} MB`}                 hint={`plan default: ${def.memory_mb} MB · addon: +${data.addons.memory_mb}`} />
          <ResourceTile icon={HardDrive}   label="Storage" value={fmtStorage(eff.storage_mb)}           hint={`plan default: ${fmtStorage(def.storage_mb)} · addon: +${fmtStorage(data.addons.storage_mb)}`} />
        </div>

        {/* Sliders */}
        <div className="border border-white/[0.06] bg-elevated/30 p-5 space-y-5">
          <SliderRow
            icon={Cpu} label="CPU upgrade"
            unitLabel="vCPU" unitSize={p.cpu_unit_vcpu}
            unitCost={p.cpu_credits_per_unit}
            value={extra.cpu_vcpu}
            onChange={(v) => setExtra({ ...extra, cpu_vcpu: v })}
            min={0} max={8} step={p.cpu_unit_vcpu}
            fmtValue={(v) => `+${v.toFixed(2)} vCPU`}
            testId="slider-cpu"
          />
          <SliderRow
            icon={MemoryStick} label="Memory upgrade"
            unitLabel="MB" unitSize={p.memory_unit_mb}
            unitCost={p.memory_credits_per_unit}
            value={extra.memory_mb}
            onChange={(v) => setExtra({ ...extra, memory_mb: Math.round(v) })}
            min={0} max={8192} step={p.memory_unit_mb}
            fmtValue={(v) => `+${v} MB`}
            testId="slider-memory"
          />
          <SliderRow
            icon={HardDrive} label="Storage upgrade"
            unitLabel="MB" unitSize={p.storage_unit_mb}
            unitCost={p.storage_credits_per_unit}
            value={extra.storage_mb}
            onChange={(v) => setExtra({ ...extra, storage_mb: Math.round(v) })}
            min={0} max={102400} step={p.storage_unit_mb}
            fmtValue={(v) => fmtStorage(v, true)}
            testId="slider-storage"
          />

          <div className="flex items-end justify-between gap-4 flex-wrap pt-2 border-t border-white/[0.04]">
            <div>
              <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">New monthly cost</div>
              <div className="font-display text-3xl mt-1 text-brand inline-flex items-center gap-2">
                <Coins className="h-6 w-6" /> {newMonthlyCost} <span className="text-xs text-zinc-500 font-mono">cr/mo</span>
              </div>
              {data.monthly_cost_credits !== newMonthlyCost && (
                <div className={`text-xs font-mono mt-1 ${isUpgrade ? "text-signal-queued" : "text-signal-live"}`}>
                  {isUpgrade ? `+${delta}` : delta} cr vs. current ({data.monthly_cost_credits} cr/mo)
                </div>
              )}
            </div>
            <button
              onClick={save}
              disabled={saving || delta === 0}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-40"
              data-testid="resources-save"
            >
              <Save className="h-4 w-4" /> {saving ? "saving…" : isUpgrade ? `Upgrade · charge ${delta} cr` : isDowngrade ? `Downgrade · refund ${-delta} cr` : "No change"}
            </button>
          </div>
          {data.addons_active_since && (
            <div className="text-[11px] font-mono text-zinc-500">
              Addons active since {new Date(data.addons_active_since).toLocaleString()} · next billing on the 30-day mark.
            </div>
          )}
        </div>
      </section>

      {/* ─── Databases ─── */}
      {conns && <AttachedDatabases appId={appId} conns={conns} reload={load} />}
    </div>
  );
}

function ResourceTile({ icon: Icon, label, value, hint }) {
  return (
    <div className="bg-background p-4">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">
        <Icon className="h-3 w-3 text-brand" /> {label}
      </div>
      <div className="font-display text-2xl mt-2 tracking-tight">{value}</div>
      <div className="text-[10px] font-mono text-zinc-500 mt-1">{hint}</div>
    </div>
  );
}

function SliderRow({ icon: Icon, label, unitLabel, unitSize, unitCost, value, onChange, min, max, step, fmtValue, testId }) {
  const units = Math.ceil((value || 0) / unitSize);
  const cost = units * unitCost;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-zinc-300">
          <Icon className="h-4 w-4 text-brand" /> {label}
          <span className="text-[10px] font-mono text-zinc-500 ml-2">
            {unitCost} cr/mo per {unitLabel === "MB" && unitSize >= 1024
              ? `${unitSize / 1024} GB`
              : unitLabel === "MB"
                ? `${unitSize} MB`
                : unitLabel.toLowerCase().includes("vcpu")
                  ? `${unitSize} vCPU`
                  : `${unitSize} ${unitLabel}`}
          </span>
        </div>
        <div className="text-sm font-mono text-zinc-100" data-testid={`${testId}-value`}>{fmtValue(value)}</div>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={() => onChange(Math.max(min, value - step))} className="h-7 w-7 border border-white/10 hover:border-brand text-zinc-400 hover:text-brand inline-flex items-center justify-center"><Minus className="h-3 w-3" /></button>
        <input
          type="range" min={min} max={max} step={step} value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 accent-brand"
          data-testid={testId}
        />
        <button onClick={() => onChange(Math.min(max, value + step))} className="h-7 w-7 border border-white/10 hover:border-brand text-zinc-400 hover:text-brand inline-flex items-center justify-center"><Plus className="h-3 w-3" /></button>
      </div>
      <div className="text-[10px] font-mono text-zinc-500 text-right">
        cost: {cost} cr/mo
      </div>
    </div>
  );
}

function fmtStorage(mb, short = false) {
  if (mb >= 1024) return `${(mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)} GB`;
  return short ? `${mb} MB` : `${mb} MB`;
}

function AttachedDatabases({ appId, conns, reload }) {
  const [picking, setPicking] = useState(false);
  const [dbId, setDbId] = useState("");
  const [envName, setEnvName] = useState("DATABASE_URL");
  const [showSecret, setShowSecret] = useState({});

  const attach = async () => {
    if (!dbId) { toast.error("Pick a database"); return; }
    try {
      await api.post(`/apps/${appId}/connections`, { db_id: dbId, env_var_name: envName });
      toast.success(`Attached as ${envName}`);
      setPicking(false); setDbId(""); setEnvName("DATABASE_URL");
      reload();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };
  const detach = async (connId, env) => {
    if (!window.confirm(`Detach ${env} from this app? The env var will be removed on next deploy.`)) return;
    try {
      await api.delete(`/apps/${appId}/connections/${connId}`);
      toast.success("Detached");
      reload();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };

  return (
    <section className="space-y-4" data-testid="db-connections">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="font-display text-xl">Database connections</h2>
          <p className="text-xs font-mono text-zinc-500 mt-1">
            Attached databases are injected as env vars on every deploy.
            The connection string is masked in the UI — copy to clipboard to reveal.
          </p>
        </div>
        <button
          onClick={() => setPicking(true)}
          className="inline-flex items-center gap-2 px-3 py-1.5 border border-white/15 hover:border-brand hover:text-brand text-xs font-mono uppercase tracking-wider"
          data-testid="attach-db-open"
        >
          <Plus className="h-3 w-3" /> Attach database
        </button>
      </div>

      {picking && (
        <div className="border border-brand/30 bg-brand/[0.04] p-4 space-y-3" data-testid="attach-db-form">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Database</label>
              <select
                value={dbId} onChange={(e) => setDbId(e.target.value)}
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                data-testid="attach-db-select"
              >
                <option value="" className="bg-black">— Pick a database —</option>
                {(conns.available_databases || []).map((db) => (
                  <option key={db.id} value={db.id} className="bg-black">{db.name} ({db.engine})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Env var name</label>
              <input
                value={envName}
                onChange={(e) => setEnvName(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_"))}
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                data-testid="attach-db-envname"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={attach} className="px-4 py-2 bg-brand text-brand-fg font-medium" data-testid="attach-db-confirm">
              <Link2 className="h-4 w-4 inline mr-1" /> Attach
            </button>
            <button onClick={() => setPicking(false)} className="px-4 py-2 border border-white/10 text-zinc-400 hover:text-white text-sm">Cancel</button>
          </div>
        </div>
      )}

      {(!conns.connections || conns.connections.length === 0) ? (
        <div className="text-xs font-mono text-zinc-600 py-6 border border-dashed border-white/[0.06] text-center">
          No databases attached. {(conns.available_databases || []).length > 0
            ? "Click 'Attach database' above to wire one in."
            : <>No databases in this workspace yet. <Link to="/app/databases" className="text-brand hover:underline">Create one</Link>.</>}
        </div>
      ) : (
        <div className="border border-white/[0.06] divide-y divide-white/[0.06]">
          {conns.connections.map((c) => (
            <div key={c.id} className="grid grid-cols-12 gap-3 px-4 py-3 items-center text-sm" data-testid={`db-conn-${c.id}`}>
              <div className="col-span-1 text-zinc-500"><Database className="h-4 w-4" /></div>
              <div className="col-span-3">
                <div className="font-medium">{c.database?.name || "(deleted)"}</div>
                <div className="text-[10px] font-mono text-zinc-500">{c.database?.engine}</div>
              </div>
              <div className="col-span-3 font-mono text-xs">
                <div className="text-[10px] uppercase tracking-wider text-zinc-500">env var</div>
                <code className="text-brand">{c.env_var_name}</code>
              </div>
              <div className="col-span-4 font-mono text-[11px] text-zinc-400 truncate">
                {showSecret[c.id] ? c.database?.connection_string : c.database?.connection_string_masked}
              </div>
              <div className="col-span-1 text-right">
                <div className="inline-flex gap-1">
                  <button
                    onClick={() => setShowSecret((s) => ({ ...s, [c.id]: !s[c.id] }))}
                    className="h-7 w-7 border border-white/10 hover:border-brand inline-flex items-center justify-center"
                    title={showSecret[c.id] ? "Hide" : "Reveal"}
                    data-testid={`db-conn-reveal-${c.id}`}
                  >
                    {showSecret[c.id] ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                  </button>
                  <button
                    onClick={() => { navigator.clipboard.writeText(c.database?.connection_string || ""); toast.success("Copied"); }}
                    className="h-7 w-7 border border-white/10 hover:border-brand inline-flex items-center justify-center"
                    title="Copy connection string"
                    data-testid={`db-conn-copy-${c.id}`}
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                  <button
                    onClick={() => detach(c.id, c.env_var_name)}
                    className="h-7 w-7 border border-signal-failed/30 text-signal-failed hover:bg-signal-failed/10 inline-flex items-center justify-center"
                    title="Detach"
                    data-testid={`db-conn-detach-${c.id}`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/**
 * Managed Databases — Postgres / Redis / MySQL / MariaDB / MongoDB.
 * Lifecycle is fully delegated to the build engine; we just expose a thin
 * UI for create / start / stop / reveal-connection / delete.
 */
import { useEffect, useState, useCallback } from "react";
import { api, getApiErrorMessage } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import {
  Database, Plus, Play, Square, Trash2, Eye, EyeOff,
  Copy, Loader2, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

const TYPE_ICON = "🗄️";

function DatabaseRow({ db, onChange }) {
  const [busy, setBusy] = useState("");
  const [conn, setConn] = useState(null);
  const [reveal, setReveal] = useState(false);

  const fetchConn = async () => {
    if (conn) { setReveal((v) => !v); return; }
    setBusy("reveal");
    try {
      const r = await api.post(`/databases/${db.id}/reveal`);
      if (r.data.connection_string) { setConn(r.data.connection_string); setReveal(true); }
      else toast.error(r.data.reason || "no connection string yet");
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(""); }
  };

  const act = async (verb) => {
    setBusy(verb);
    try {
      await api.post(`/databases/${db.id}/${verb}`);
      onChange();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(""); }
  };

  const remove = async () => {
    if (!window.confirm(`Delete "${db.name}"? This destroys the data permanently.`)) return;
    setBusy("delete");
    try {
      await api.delete(`/databases/${db.id}`);
      toast.success("Database deleted");
      onChange();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };

  const masked = conn ? (reveal ? conn : "•".repeat(Math.min(conn.length, 36))) : "—";

  return (
    <div className="grid grid-cols-[1fr_140px_120px_140px_auto] gap-4 items-center px-5 py-3 border-b border-white/[0.04] last:border-b-0" data-testid={`db-row-${db.id}`}>
      <div>
        <div className="text-sm flex items-center gap-2">
          <span className="text-xl">{TYPE_ICON}</span>
          {db.name}
        </div>
        <div className="text-[11px] font-mono text-zinc-500">{db.type} · v{db.version}</div>
      </div>
      <div>
        <span className={`text-xs font-mono inline-flex items-center gap-1.5 ${
          db.status === "running" ? "text-signal-live" :
          db.status === "provisioning" ? "text-signal-queued" :
          db.status === "stopped" ? "text-zinc-500" : "text-signal-failed"
        }`}>
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {db.status}
        </span>
      </div>
      <div className="text-[11px] font-mono text-zinc-500">
        {db.connection_string_set ? "configured" : "not provisioned"}
      </div>
      <div className="flex items-center gap-1">
        {db.connection_string_set && (
          <>
            <code className="hidden lg:inline-block text-[10px] font-mono text-zinc-400 px-2 py-1 bg-black border border-white/[0.06] truncate max-w-[180px]">
              {masked}
            </code>
            <button onClick={fetchConn} disabled={busy === "reveal"} className="px-2 py-1.5 border border-white/10 hover:border-brand/50" data-testid={`db-reveal-${db.id}`}>
              {reveal ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            </button>
            {reveal && conn && (
              <button onClick={() => { navigator.clipboard.writeText(conn); toast.success("Copied"); }} className="px-2 py-1.5 border border-white/10 hover:border-brand/50">
                <Copy className="h-3 w-3" />
              </button>
            )}
          </>
        )}
      </div>
      <div className="flex items-center gap-1">
        {db.status === "stopped" && (
          <button onClick={() => act("start")} disabled={!!busy} className="px-2 py-1.5 text-xs border border-white/10 hover:border-signal-live/50 hover:text-signal-live" data-testid={`db-start-${db.id}`}>
            <Play className="h-3 w-3" />
          </button>
        )}
        {db.status === "running" && (
          <button onClick={() => act("stop")} disabled={!!busy} className="px-2 py-1.5 text-xs border border-white/10 hover:border-signal-failed/50 hover:text-signal-failed" data-testid={`db-stop-${db.id}`}>
            <Square className="h-3 w-3" />
          </button>
        )}
        <button onClick={remove} disabled={!!busy} className="px-2 py-1.5 text-xs border border-white/10 hover:border-signal-failed/50 hover:text-signal-failed" data-testid={`db-delete-${db.id}`}>
          {busy === "delete" ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
        </button>
      </div>
    </div>
  );
}

export default function Databases() {
  const { active } = useWorkspace();
  const [list, setList] = useState([]);
  const [types, setTypes] = useState({});
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ type: "postgresql", name: "", version: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!active) return;
    setLoading(true);
    try {
      const r = await api.get(`/databases?workspace_id=${active.id}`);
      setList(r.data.databases || []);
      setTypes(r.data.supported_types || {});
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [active]);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!active || !form.name.trim()) { toast.error("Name is required"); return; }
    setBusy(true);
    try {
      await api.post(`/databases?workspace_id=${active.id}`, form);
      toast.success("Database created");
      setCreating(false);
      setForm({ type: "postgresql", name: "", version: "" });
      load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  if (!active) return <div className="p-6 text-sm font-mono text-zinc-500">Select a workspace.</div>;

  return (
    <div className="px-6 py-6 space-y-6" data-testid="databases-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// databases</div>
          <h1 className="font-display text-4xl font-semibold tracking-tighter">Managed databases.</h1>
          <p className="mt-1 text-sm text-zinc-400">Postgres, Redis, MySQL, MariaDB, MongoDB — provisioned in seconds with rotating credentials.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="inline-flex items-center gap-1.5 px-3 py-2 border border-white/10 hover:border-brand/50 text-xs font-mono" data-testid="db-refresh">
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> refresh
          </button>
          <button onClick={() => setCreating(true)} className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90" data-testid="db-create-open">
            <Plus className="h-4 w-4" /> New database
          </button>
        </div>
      </div>

      {creating && (
        <div className="border border-brand/40 p-5 space-y-4" data-testid="db-create-form">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Type</label>
              <select
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value, version: types[e.target.value]?.default_version || "" })}
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                data-testid="db-create-type"
              >
                {Object.entries(types).map(([k, v]) => <option key={k} value={k} className="bg-black">{v.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Name</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="my-app-db"
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                data-testid="db-create-name"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Version</label>
              <input
                value={form.version}
                onChange={(e) => setForm({ ...form, version: e.target.value })}
                placeholder={types[form.type]?.default_version || "latest"}
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                data-testid="db-create-version"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={create} disabled={busy} className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50" data-testid="db-create-submit">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Provision
            </button>
            <button onClick={() => setCreating(false)} className="px-3 py-2 border border-white/10 text-xs font-mono hover:border-white/30">cancel</button>
          </div>
        </div>
      )}

      {list.length === 0 && !loading && !creating && (
        <div className="border border-white/[0.06] p-10 text-center text-sm text-zinc-500" data-testid="db-empty">
          <Database className="h-6 w-6 mx-auto mb-3 text-zinc-600" />
          No databases yet. Spin one up to give your apps state.
        </div>
      )}

      {list.length > 0 && (
        <div className="border border-white/[0.06]">
          <div className="grid grid-cols-[1fr_140px_120px_140px_auto] gap-4 px-5 py-2 border-b border-white/[0.06] text-[10px] uppercase tracking-[0.25em] font-mono text-zinc-500">
            <div>Name</div><div>Status</div><div>Credentials</div><div>Connection</div><div className="text-right">Actions</div>
          </div>
          {list.map((d) => <DatabaseRow key={d.id} db={d} onChange={load} />)}
        </div>
      )}
    </div>
  );
}

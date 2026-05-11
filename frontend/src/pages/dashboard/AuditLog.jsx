/**
 * Audit log — append-only ledger of "who did what".
 * Owner/admin of a workspace sees workspace-scoped log; platform admins see
 * the cross-workspace log when no workspace_id is selected.
 */
import { useEffect, useState, useCallback } from "react";
import { api, getApiErrorMessage } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import { ShieldCheck, Filter, RefreshCw, ChevronDown } from "lucide-react";
import { toast } from "sonner";

const ACTION_LABELS = {
  "auth.login": "Sign in",
  "auth.logout": "Sign out",
  "app.create": "App created",
  "app.delete": "App deleted",
  "app.redeploy": "Redeploy",
  "app.update": "App updated",
  "deployment.queued": "Deployment queued",
  "billing.subscription.change": "Subscription changed",
  "billing.subscription.cancel": "Subscription canceled",
  "billing.checkout.start": "Checkout started",
  "credits.topup": "Credits topped up",
  "workspace.member.invite": "Member invited",
  "workspace.member.remove": "Member removed",
  "workspace.update": "Workspace updated",
  "admin.platform_settings.update": "Platform settings updated",
};

function actionLabel(a) { return ACTION_LABELS[a] || a; }

export default function AuditLog() {
  const { active } = useWorkspace();
  const [entries, setEntries] = useState([]);
  const [actions, setActions] = useState([]);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [more, setMore] = useState(false);

  const load = useCallback(async (reset = true) => {
    setLoading(true);
    try {
      const params = { workspace_id: active?.id, limit: 100 };
      if (actionFilter) params.action = actionFilter;
      if (!reset && entries.length) {
        params.before = entries[entries.length - 1].created_at;
      }
      const r = await api.get("/audit-log", { params });
      const next = r.data.entries || [];
      setEntries(reset ? next : [...entries, ...next]);
      setMore(next.length === params.limit);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [active, actionFilter, entries]);

  useEffect(() => {
    if (!active) return;
    api.get("/audit-log/actions", { params: { workspace_id: active.id } })
      .then((r) => setActions(r.data.actions || []))
      .catch(() => setActions([]));
  }, [active]);

  useEffect(() => { if (active) load(true); /* eslint-disable-next-line */ }, [active, actionFilter]);

  if (!active) {
    return <div className="p-6 text-sm font-mono text-zinc-500">Select a workspace to view its audit log.</div>;
  }

  return (
    <div className="px-6 py-6 space-y-6" data-testid="audit-page">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// audit</div>
          <h1 className="font-display text-4xl font-semibold tracking-tighter">Audit log</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Append-only ledger of every privileged action across <span className="text-brand">{active.name}</span>.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 border border-white/10 px-2.5 py-2 text-xs font-mono">
            <Filter className="h-3 w-3 text-zinc-500" />
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="bg-transparent focus:outline-none cursor-pointer pr-1"
              data-testid="audit-action-filter"
            >
              <option value="" className="bg-black">all actions</option>
              {actions.map((a) => (
                <option key={a} value={a} className="bg-black">{actionLabel(a)}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => load(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-white/10 hover:border-brand/50 text-xs font-mono"
            data-testid="audit-refresh"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} /> refresh
          </button>
        </div>
      </div>

      {entries.length === 0 && !loading && (
        <div className="border border-white/[0.06] p-10 text-center text-sm text-zinc-500" data-testid="audit-empty">
          <ShieldCheck className="h-6 w-6 mx-auto mb-3 text-zinc-600" />
          No audit entries yet. Actions on this workspace will appear here in real-time.
        </div>
      )}

      {entries.length > 0 && (
        <div className="border border-white/[0.06]">
          <div className="grid grid-cols-[180px_1fr_120px_180px] gap-px bg-white/[0.06] border-b border-white/[0.06]">
            {["When", "Actor / Action", "Resource", "IP / UA"].map((h) => (
              <div key={h} className="bg-background px-4 py-2 text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500">
                {h}
              </div>
            ))}
          </div>
          {entries.map((e) => (
            <div
              key={e.id}
              className="grid grid-cols-[180px_1fr_120px_180px] border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02]"
              data-testid={`audit-row-${e.action}`}
            >
              <div className="px-4 py-3 text-xs font-mono text-zinc-500" title={e.created_at}>
                {new Date(e.created_at).toLocaleString()}
              </div>
              <div className="px-4 py-3">
                <div className="text-sm">{actionLabel(e.action)}</div>
                <div className="text-[11px] font-mono text-zinc-500 mt-0.5">{e.actor_email || "—"}</div>
                {Object.keys(e.meta || {}).length > 0 && (
                  <details className="mt-1">
                    <summary className="text-[10px] font-mono text-zinc-600 cursor-pointer hover:text-zinc-400 inline-flex items-center gap-0.5">
                      <ChevronDown className="h-2.5 w-2.5" /> meta
                    </summary>
                    <pre className="mt-1 text-[10px] font-mono text-zinc-400 bg-black/40 p-2 border border-white/[0.04] overflow-x-auto">{JSON.stringify(e.meta, null, 2)}</pre>
                  </details>
                )}
              </div>
              <div className="px-4 py-3 text-xs font-mono text-zinc-500">
                {e.resource_type ? <span className="text-zinc-300">{e.resource_type}</span> : "—"}
                {e.resource_id && <div className="text-[10px] text-zinc-600 truncate" title={e.resource_id}>{e.resource_id.slice(0, 8)}</div>}
              </div>
              <div className="px-4 py-3 text-[10px] font-mono text-zinc-500 truncate">
                {e.ip && <div>{e.ip}</div>}
                {e.ua && <div className="truncate" title={e.ua}>{e.ua.slice(0, 22)}…</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {more && (
        <button
          onClick={() => load(false)}
          disabled={loading}
          className="px-4 py-2 border border-white/10 hover:border-brand/50 text-xs font-mono disabled:opacity-50"
          data-testid="audit-load-more"
        >
          Load older entries
        </button>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, getApiErrorMessage } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import StatusBadge from "../../components/StatusBadge";
import { CreditCard, ExternalLink, Loader2 } from "lucide-react";

export default function Billing() {
  const { active } = useWorkspace();
  const [plans, setPlans] = useState([]);
  const [sub, setSub] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = () => {
    if (!active) return;
    setLoading(true);
    Promise.all([
      api.get("/billing/plans"),
      api.get("/billing/subscription", { params: { workspace_id: active.id } }),
      api.get("/billing/invoices", { params: { workspace_id: active.id } }).catch(() => ({ data: [] })),
    ]).then(([p, s, i]) => { setPlans(p.data); setSub(s.data); setInvoices(i.data); })
      .finally(() => setLoading(false));
  };
  useEffect(load, [active]);

  const upgrade = async (plan) => {
    if (!active) return;
    setBusy(plan);
    setError("");
    try {
      await api.post("/billing/checkout", { workspace_id: active.id, plan });
      load();
    } catch (e) { setError(getApiErrorMessage(e)); }
    finally { setBusy(""); }
  };

  if (loading || !sub) {
    return <div className="p-6 text-zinc-500 font-mono text-sm">Loading billing…</div>;
  }

  return (
    <div className="px-6 py-6 space-y-10" data-testid="billing-page">
      <div>
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// billing</div>
        <h1 className="font-display text-4xl font-semibold tracking-tighter">Plans & invoices</h1>
        <p className="mt-1 text-sm text-zinc-400">Powered quietly by WHMCS · {sub.whmcs_configured ? "live billing" : "stub"}.</p>
      </div>

      {/* Current plan */}
      <section className="border border-white/[0.06] p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Current plan</div>
            <div className="mt-1 font-display text-3xl tracking-tighter capitalize">{sub.plan}</div>
            {sub.subscription && (
              <div className="mt-1 text-xs font-mono text-zinc-500">Status: {sub.subscription.status}</div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {plans.filter((p) => p.id !== sub.plan).map((p) => (
              <button
                key={p.id}
                onClick={() => upgrade(p.id)}
                disabled={busy === p.id}
                className={`px-4 py-2 text-sm font-medium ${p.highlight ? "bg-brand text-brand-fg hover:bg-brand/90" : "border border-white/15 hover:border-white/40"}`}
                data-testid={`billing-switch-${p.id}`}
              >
                {busy === p.id ? <Loader2 className="h-4 w-4 animate-spin" /> : `${sub.plan === "hobby" ? "Upgrade to" : "Switch to"} ${p.name} · $${p.price}`}
              </button>
            ))}
          </div>
        </div>
        {error && <div className="mt-4 text-signal-failed text-sm">{error}</div>}
      </section>

      {/* Plan grid */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-px bg-white/[0.06] border border-white/[0.06]">
        {plans.map((p) => (
          <div key={p.id} className={`bg-background p-6 ${p.highlight ? "tracing-border" : ""}`}>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">{p.name}</div>
            <div className="mt-2 font-display text-3xl tracking-tighter">${p.price}<span className="text-sm text-zinc-500">/{p.interval}</span></div>
            <ul className="mt-4 space-y-1.5 text-sm text-zinc-300">
              {p.features.map((f) => <li key={f}>· {f}</li>)}
            </ul>
            {p.id === sub.plan ? (
              <div className="mt-5 text-xs font-mono uppercase tracking-[0.3em] text-brand">// active</div>
            ) : (
              <button
                onClick={() => upgrade(p.id)}
                disabled={busy === p.id}
                className="mt-5 inline-flex items-center gap-2 text-xs font-mono uppercase tracking-[0.25em] text-zinc-400 hover:text-brand"
              >
                Switch →
              </button>
            )}
          </div>
        ))}
      </section>

      {/* Invoices */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <CreditCard className="h-4 w-4" />
          <h2 className="font-display text-2xl">Invoices</h2>
        </div>
        {invoices.length === 0 ? (
          <div className="border border-dashed border-white/10 p-10 text-center text-sm text-zinc-400">
            No invoices yet. They'll appear here once a paid plan is active.
          </div>
        ) : (
          <div className="border-t border-l border-white/[0.06]">
            <div className="grid grid-cols-12 px-4 py-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 border-r border-b border-white/[0.06]">
              <div className="col-span-3"># Invoice</div>
              <div className="col-span-2">Amount</div>
              <div className="col-span-3">Due</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-2 text-right">Actions</div>
            </div>
            {invoices.map((inv) => (
              <div key={inv.id} className="grid grid-cols-12 px-4 py-3 border-r border-b border-white/[0.06] items-center" data-testid={`invoice-row-${inv.id}`}>
                <div className="col-span-3 font-mono text-sm">#{inv.number}</div>
                <div className="col-span-2 font-mono">${inv.amount.toFixed(2)} {inv.currency}</div>
                <div className="col-span-3 font-mono text-xs text-zinc-400">{inv.due_date || "—"}</div>
                <div className="col-span-2"><StatusBadge status={(inv.status || "").toLowerCase()} /></div>
                <div className="col-span-2 text-right">
                  {inv.link && (
                    <a href={inv.link} target="_blank" rel="noreferrer" className="text-xs font-mono text-brand hover:underline inline-flex items-center gap-1">
                      open <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

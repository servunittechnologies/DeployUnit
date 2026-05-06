import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { api, getApiErrorMessage, API_BASE } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import StatusBadge from "../../components/StatusBadge";
import BillingProfileForm from "../../components/BillingProfileForm";
import { CreditCard, ExternalLink, Loader2, Download, Check, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

function format(d) {
  if (!d) return "—";
  try { return new Date(d).toLocaleDateString(); } catch { return d; }
}

export default function Billing() {
  const { active } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const [plans, setPlans] = useState([]);
  const [sub, setSub] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [editingProfile, setEditingProfile] = useState(false);

  const load = useCallback(async () => {
    if (!active) return;
    setLoading(true);
    try {
      const [p, s, i] = await Promise.all([
        api.get("/billing/plans"),
        api.get("/billing/subscription", { params: { workspace_id: active.id } }),
        api.get("/billing/invoices", { params: { workspace_id: active.id } }).catch(() => ({ data: [] })),
      ]);
      setPlans(p.data); setSub(s.data); setInvoices(i.data);
    } finally { setLoading(false); }
  }, [active]);

  useEffect(() => { load(); }, [load]);

  // Handle Mollie return
  useEffect(() => {
    if (params.get("mollie") === "success") {
      toast.success("Thanks! We're confirming your payment with Mollie…");
      setParams({});
      // Poll for a few seconds in case the webhook hasn't landed yet
      const t = setInterval(load, 3000);
      setTimeout(() => clearInterval(t), 20000);
    }
  }, [params, setParams, load]);

  const goCheckout = async (plan) => {
    if (!active) return;
    if (!sub?.billing_profile && plan !== "hobby") {
      setEditingProfile(true);
      toast.error("Please fill in your billing profile first.");
      return;
    }
    setBusy(plan);
    try {
      const { data } = await api.post("/billing/checkout", { workspace_id: active.id, plan });
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        toast.success(`Plan switched to ${plan}.`);
        load();
      }
    } catch (e) {
      toast.error(getApiErrorMessage(e));
    } finally { setBusy(""); }
  };

  const cancel = async () => {
    if (!active) return;
    if (!window.confirm("Cancel your subscription? Your workspace drops back to the Hobby plan.")) return;
    try {
      await api.post("/billing/cancel", null, { params: { workspace_id: active.id } });
      toast.success("Subscription canceled.");
      load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };

  if (loading || !sub) {
    return <div className="p-6 text-zinc-500 font-mono text-sm">Loading billing…</div>;
  }

  const profile = sub.billing_profile;
  const subStatus = sub.subscription?.status || (sub.plan === "hobby" ? "active" : "none");

  return (
    <div className="px-6 py-6 space-y-10" data-testid="billing-page">
      <div>
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// billing</div>
        <h1 className="font-display text-4xl font-semibold tracking-tighter">Plans & invoices</h1>
        <p className="mt-1 text-sm text-zinc-400">Powered by Mollie · Your workspace, your VAT, your invoices.</p>
      </div>

      {/* Current subscription */}
      <section className="border border-white/[0.06] p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Current plan</div>
            <div className="mt-1 font-display text-3xl tracking-tighter capitalize">{sub.plan}</div>
            <div className="mt-1 flex items-center gap-3 text-xs font-mono text-zinc-500">
              Status: <StatusBadge status={subStatus} />
              {sub.subscription?.next_billing_at && (
                <span>· next charge {format(sub.subscription.next_billing_at)}</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {sub.plan !== "hobby" && sub.subscription?.status === "active" && (
              <button onClick={cancel} className="px-4 py-2 border border-signal-failed/40 text-signal-failed hover:bg-signal-failed/10 text-sm" data-testid="billing-cancel">
                Cancel subscription
              </button>
            )}
          </div>
        </div>
        {!profile && sub.plan === "hobby" && (
          <div className="mt-4 p-3 border border-signal-queued/30 bg-signal-queued/5 text-sm flex items-center gap-3">
            <AlertTriangle className="h-4 w-4 text-signal-queued" />
            Fill in your billing profile below before choosing a paid plan.
          </div>
        )}
      </section>

      {/* Billing profile */}
      <section className="border border-white/[0.06] p-6" data-testid="billing-profile-section">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Billing profile</div>
            <h2 className="font-display text-xl mt-1">Who's on the invoice?</h2>
          </div>
          {profile && !editingProfile && (
            <button onClick={() => setEditingProfile(true)} className="text-xs font-mono uppercase tracking-[0.25em] text-zinc-400 hover:text-brand" data-testid="billing-edit-profile">
              Edit
            </button>
          )}
        </div>

        {(!profile || editingProfile) ? (
          <BillingProfileForm
            workspaceId={active?.id}
            initial={profile}
            submitLabel={profile ? "Save changes" : "Save billing profile"}
            onSaved={() => { setEditingProfile(false); load(); }}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Company</div>
              <div className="mt-1">{profile.company_name}</div>
              <div className="text-xs text-zinc-500 font-mono">{profile.email}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Address</div>
              <div className="mt-1">{profile.address}</div>
              <div className="text-zinc-400">{profile.postal_code} {profile.city}</div>
              <div className="text-zinc-400">{profile.country}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">VAT treatment</div>
              <div className="mt-1">{profile.vat_note}</div>
              {profile.is_business && (
                <div className="text-xs font-mono mt-1">
                  VAT ID: <span className="text-zinc-300">{profile.vat_id || "—"}</span>
                  {profile.vat_id_valid === true && <span className="text-signal-live ml-2">✓ VIES valid</span>}
                  {profile.vat_id_valid === false && <span className="text-signal-failed ml-2">✗ invalid</span>}
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Plans */}
      <section>
        <h2 className="font-display text-xl mb-3">Change plan</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-white/[0.06] border border-white/[0.06]">
          {plans.map((p) => {
            const active_here = p.id === sub.plan;
            return (
              <div key={p.id} className={`bg-background p-6 ${p.highlight ? "tracing-border" : ""}`} data-testid={`billing-plan-${p.id}`}>
                <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">{p.name}</div>
                <div className="mt-2 font-display text-3xl tracking-tighter">€{p.price}<span className="text-sm text-zinc-500">/{p.interval}</span></div>
                <ul className="mt-4 space-y-1.5 text-sm text-zinc-300">
                  {p.features.map((f) => <li key={f} className="flex gap-1.5"><Check className="h-3.5 w-3.5 text-brand mt-1" /> {f}</li>)}
                </ul>
                {active_here ? (
                  <div className="mt-5 text-xs font-mono uppercase tracking-[0.3em] text-brand">// current plan</div>
                ) : (
                  <button
                    onClick={() => goCheckout(p.id)}
                    disabled={busy === p.id}
                    className={`mt-5 w-full inline-flex items-center justify-center gap-2 py-2 text-sm font-medium ${p.highlight ? "bg-brand text-brand-fg hover:bg-brand/90" : "border border-white/15 hover:border-white/40"}`}
                    data-testid={`billing-switch-${p.id}`}
                  >
                    {busy === p.id ? <Loader2 className="h-4 w-4 animate-spin" /> : p.id === "hobby" ? "Downgrade" : `Go ${p.name} · €${p.price}`}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Payments */}
      {sub.payments && sub.payments.length > 0 && (
        <section>
          <h2 className="font-display text-xl mb-3">Recent payments</h2>
          <div className="border-t border-l border-white/[0.06]">
            <div className="grid grid-cols-12 px-4 py-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 border-r border-b border-white/[0.06]">
              <div className="col-span-3">Date</div>
              <div className="col-span-3">Plan</div>
              <div className="col-span-2">Amount</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-2">Method</div>
            </div>
            {sub.payments.map((p) => (
              <div key={p.mollie_payment_id} className="grid grid-cols-12 px-4 py-3 border-r border-b border-white/[0.06] text-sm" data-testid={`payment-${p.mollie_payment_id}`}>
                <div className="col-span-3 font-mono">{format(p.paid_at || p.created_at)}</div>
                <div className="col-span-3 capitalize">{p.plan} <span className="text-xs text-zinc-500">· {p.kind}</span></div>
                <div className="col-span-2 font-mono">€{(p.total || 0).toFixed(2)}</div>
                <div className="col-span-2"><StatusBadge status={p.status} /></div>
                <div className="col-span-2 font-mono text-zinc-400">{p.method || "—"}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Invoices */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <CreditCard className="h-4 w-4" />
          <h2 className="font-display text-xl">Invoices</h2>
        </div>
        {invoices.length === 0 ? (
          <div className="border border-dashed border-white/10 p-10 text-center text-sm text-zinc-400">
            No invoices yet — one will be generated per successful payment.
          </div>
        ) : (
          <div className="border-t border-l border-white/[0.06]">
            <div className="grid grid-cols-12 px-4 py-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 border-r border-b border-white/[0.06]">
              <div className="col-span-3"># Invoice</div>
              <div className="col-span-2">Date</div>
              <div className="col-span-2">Subtotal</div>
              <div className="col-span-2">VAT</div>
              <div className="col-span-2">Total</div>
              <div className="col-span-1 text-right">PDF</div>
            </div>
            {invoices.map((inv) => (
              <div key={inv.id} className="grid grid-cols-12 px-4 py-3 border-r border-b border-white/[0.06] items-center text-sm" data-testid={`invoice-row-${inv.invoice_number}`}>
                <div className="col-span-3 font-mono">#{inv.invoice_number}</div>
                <div className="col-span-2 font-mono text-zinc-400 text-xs">{format(inv.invoice_date)}</div>
                <div className="col-span-2 font-mono">€{(inv.subtotal || 0).toFixed(2)}</div>
                <div className="col-span-2 font-mono text-zinc-400 text-xs">
                  {inv.vat_rate > 0 ? `€${(inv.vat_amount || 0).toFixed(2)} (${inv.vat_rate}%)` : "reverse charge"}
                </div>
                <div className="col-span-2 font-mono font-medium">€{(inv.total || 0).toFixed(2)}</div>
                <div className="col-span-1 text-right">
                  <a href={`${API_BASE}/billing/invoices/${inv.invoice_number}/pdf`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-mono text-brand hover:underline" data-testid={`invoice-download-${inv.invoice_number}`}>
                    <Download className="h-3 w-3" /> PDF
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

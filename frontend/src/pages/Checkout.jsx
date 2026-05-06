import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, getApiErrorMessage } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import Logo from "../components/Logo";
import BillingProfileForm from "../components/BillingProfileForm";
import { Loader2, Check, ArrowRight } from "lucide-react";

export default function Checkout() {
  const [params] = useSearchParams();
  const planId = params.get("plan") || "pro";
  const { user, loading: authLoading } = useAuth();
  const { active, loading: wsLoading } = useWorkspace();
  const navigate = useNavigate();
  const [plans, setPlans] = useState([]);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [redirecting, setRedirecting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/billing/plans").then((r) => setPlans(r.data));
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (user === false) navigate(`/register?plan=${planId}`);
  }, [user, authLoading, navigate, planId]);

  useEffect(() => {
    if (!active) return;
    setLoading(true);
    api.get("/billing/profile", { params: { workspace_id: active.id } })
      .then((r) => setProfile(r.data || null))
      .finally(() => setLoading(false));
  }, [active]);

  const plan = plans.find((p) => p.id === planId);

  const startCheckout = async () => {
    if (!active) return;
    setRedirecting(true);
    setError("");
    try {
      const { data } = await api.post("/billing/checkout", { workspace_id: active.id, plan: planId });
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        navigate("/app/billing");
      }
    } catch (e) {
      setError(getApiErrorMessage(e));
      setRedirecting(false);
    }
  };

  if (authLoading || wsLoading || !plan || loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center text-zinc-500 font-mono text-sm">
        <Loader2 className="h-4 w-4 animate-spin mr-2" /> loading checkout...
      </div>
    );
  }

  const isFree = plan.id === "hobby";

  return (
    <div className="min-h-screen bg-background">
      <header className="glass">
        <div className="max-w-[1100px] mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/"><Logo /></Link>
          <Link to="/app" className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500 hover:text-white">
            Skip → dashboard
          </Link>
        </div>
      </header>

      <section className="max-w-[1100px] mx-auto px-6 py-14 grid grid-cols-1 lg:grid-cols-5 gap-px bg-white/[0.06] border border-white/[0.06]">
        {/* Plan summary */}
        <div className="bg-background p-8 lg:col-span-2">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-3">// your plan</div>
          <h1 className="font-display text-4xl tracking-tighter font-semibold">{plan.name}</h1>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="font-display text-5xl font-semibold tracking-tighter">€{plan.price}</span>
            <span className="text-zinc-500 text-sm">/{plan.interval}</span>
          </div>
          <p className="mt-2 text-zinc-400">{plan.tagline}</p>
          <ul className="mt-8 space-y-2 text-sm">
            {plan.features.map((f) => (
              <li key={f} className="flex items-center gap-2"><Check className="h-4 w-4 text-brand" /> {f}</li>
            ))}
          </ul>

          <div className="mt-8 p-3 border border-white/10 bg-elevated/30 text-xs font-mono text-zinc-400 leading-6">
            <div className="text-brand">// next steps</div>
            {isFree ? (
              <>
                <div>1. Confirm your workspace</div>
                <div>2. Start deploying</div>
              </>
            ) : (
              <>
                <div>1. Fill in your billing profile (VAT matters!)</div>
                <div>2. Redirect to Mollie to pay</div>
                <div>3. A PDF invoice lands in your dashboard</div>
                <div>4. Mollie auto-charges every month</div>
              </>
            )}
          </div>
          <Link to="/pricing" className="mt-6 inline-block text-xs font-mono uppercase tracking-[0.3em] text-zinc-500 hover:text-brand" data-testid="checkout-change-plan">
            // change plan
          </Link>
        </div>

        {/* Profile + pay */}
        <div className="bg-elevated/30 p-8 lg:col-span-3">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">Workspace</div>
          <div className="mt-1 font-display text-2xl">{active?.name}</div>
          <div className="mt-1 text-xs font-mono text-zinc-500">{user?.email}</div>

          {isFree ? (
            <>
              <p className="mt-8 text-sm text-zinc-400">
                Hobby is free. Click confirm and you're live.
              </p>
              {error && <div className="mt-4 text-signal-failed text-sm">{error}</div>}
              <button
                onClick={startCheckout}
                disabled={redirecting}
                className="mt-6 w-full inline-flex items-center justify-center gap-2 py-3 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition disabled:opacity-50 shadow-[0_0_20px_rgba(0,229,255,0.25)]"
                data-testid="checkout-submit"
              >
                {redirecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Confirm free plan <ArrowRight className="h-4 w-4" /></>}
              </button>
            </>
          ) : (
            <>
              <div className="mt-8 text-[10px] uppercase tracking-[0.3em] font-mono text-brand mb-2">// billing profile</div>
              <BillingProfileForm
                workspaceId={active?.id}
                initial={profile}
                submitLabel={profile ? "Update & continue to Mollie" : "Save & continue to Mollie"}
                onSaved={async (data) => {
                  setProfile(data.profile);
                  // Directly hit checkout — this is the user's intent on this page
                  await startCheckout();
                }}
              />
              {profile && (
                <button
                  onClick={startCheckout}
                  disabled={redirecting}
                  className="mt-4 w-full inline-flex items-center justify-center gap-2 py-3 border border-white/15 hover:border-brand hover:text-brand transition text-sm font-medium disabled:opacity-50"
                  data-testid="checkout-skip-to-mollie"
                >
                  {redirecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Profile is fine — go to Mollie <ArrowRight className="h-4 w-4" /></>}
                </button>
              )}
              {error && <div className="mt-4 text-signal-failed text-sm">{error}</div>}
              <div className="mt-4 text-[11px] font-mono text-zinc-500">
                You'll be redirected to Mollie's secure checkout. Cancel any time from the Billing page.
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

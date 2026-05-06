import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, getApiErrorMessage } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import Logo from "../components/Logo";
import { Loader2, Check, ArrowRight, ExternalLink } from "lucide-react";

export default function Checkout() {
  const [params] = useSearchParams();
  const planId = params.get("plan") || "pro";
  const { user, loading: authLoading } = useAuth();
  const { active, workspaces, loading: wsLoading } = useWorkspace();
  const navigate = useNavigate();
  const [plans, setPlans] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/billing/plans").then((r) => setPlans(r.data));
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (user === false) navigate(`/register?plan=${planId}`);
  }, [user, authLoading, navigate, planId]);

  const plan = plans.find((p) => p.id === planId);

  const submit = async () => {
    if (!active) return;
    setSubmitting(true);
    setError("");
    try {
      const { data } = await api.post("/billing/checkout", { workspace_id: active.id, plan: planId });
      setResult(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (authLoading || wsLoading || !plan) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center text-zinc-500 font-mono text-sm">
        <Loader2 className="h-4 w-4 animate-spin mr-2" /> loading checkout...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="glass">
        <div className="max-w-[1100px] mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/"><Logo /></Link>
          <Link to="/app" className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500 hover:text-white">Skip → dashboard</Link>
        </div>
      </header>

      <section className="max-w-[1100px] mx-auto px-6 py-16 grid grid-cols-1 lg:grid-cols-2 gap-px bg-white/[0.06] border border-white/[0.06]">
        <div className="bg-background p-10">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-3">// confirm plan</div>
          <h1 className="font-display text-4xl tracking-tighter font-semibold">{plan.name}</h1>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="font-display text-5xl font-semibold tracking-tighter">${plan.price}</span>
            <span className="text-zinc-500 text-sm">/{plan.interval}</span>
          </div>
          <p className="mt-2 text-zinc-400">{plan.tagline}</p>
          <ul className="mt-8 space-y-2 text-sm">
            {plan.features.map((f) => (
              <li key={f} className="flex items-center gap-2"><Check className="h-4 w-4 text-brand" /> {f}</li>
            ))}
          </ul>
          <Link to="/pricing" className="mt-8 inline-block text-xs font-mono uppercase tracking-[0.3em] text-zinc-500 hover:text-brand" data-testid="checkout-change-plan">
            // change plan
          </Link>
        </div>

        <div className="bg-elevated/30 p-10">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">Workspace</div>
          <div className="mt-1 font-display text-2xl">{active?.name}</div>
          <div className="mt-1 text-xs font-mono text-zinc-500">{active?.type} · {workspaces.length} total</div>

          <div className="mt-8 p-4 border border-white/10 text-xs leading-6 text-zinc-400 font-mono bg-black/40">
            <div className="text-brand">// what happens next</div>
            <div>1. We create a billing record in WHMCS</div>
            <div>2. An invoice is generated for ${plan.price}/{plan.interval}</div>
            <div>3. Your workspace plan is upgraded</div>
            <div>4. You start deploying</div>
          </div>

          {result ? (
            <div className="mt-6 p-4 border border-signal-live/30 bg-signal-live/5 text-sm" data-testid="checkout-success">
              <div className="text-signal-live font-mono uppercase tracking-[0.3em] text-[10px]">// activated</div>
              <div className="mt-2">Plan upgraded to <strong>{plan.name}</strong>. Status: {result.status}.</div>
              {result.invoice_link && (
                <a href={result.invoice_link} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-2 text-brand text-xs font-mono">
                  View invoice <ExternalLink className="h-3 w-3" />
                </a>
              )}
              <button
                onClick={() => navigate("/app")}
                className="mt-5 inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90"
                data-testid="checkout-go-dashboard"
              >
                Go to dashboard <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <>
              {error && (
                <div className="mt-4 px-3 py-2 border border-signal-failed/30 bg-signal-failed/10 text-signal-failed text-sm">{error}</div>
              )}
              <button
                onClick={submit}
                disabled={submitting}
                className="mt-6 w-full inline-flex items-center justify-center gap-2 py-3 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition disabled:opacity-50 shadow-[0_0_20px_rgba(0,229,255,0.25)]"
                data-testid="checkout-submit"
              >
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Confirm and create invoice <ArrowRight className="h-4 w-4" /></>}
              </button>
              <div className="mt-3 text-[11px] font-mono text-zinc-500">
                {plan.id === "hobby" ? "No payment required for the Hobby plan." : "An invoice will be generated via WHMCS. You can pay any time from the Billing page."}
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import Logo from "../components/Logo";
import { Check, ArrowRight } from "lucide-react";

export default function Pricing() {
  const [plans, setPlans] = useState([]);
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/billing/plans").then((r) => setPlans(r.data));
  }, []);

  const choose = (planId) => {
    if (!user || user === false) navigate(`/register?plan=${planId}`);
    else navigate(`/checkout?plan=${planId}`);
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="glass sticky top-0 z-30">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/"><Logo /></Link>
          <nav className="flex items-center gap-3">
            <Link to="/login" className="text-sm text-zinc-400 hover:text-white">Sign in</Link>
            <Link to="/register" className="px-3 py-1.5 text-sm bg-brand text-brand-fg font-medium hover:bg-brand/90">Start free</Link>
          </nav>
        </div>
      </header>

      <section className="max-w-[1400px] mx-auto px-6 py-20 text-center">
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-3">// pricing</div>
        <h1 className="font-display text-5xl lg:text-6xl tracking-tighter font-semibold">
          Pay for outcomes,<br /> not config.
        </h1>
        <p className="mt-4 text-zinc-400 max-w-xl mx-auto">
          Cancel any time. All plans include monitoring, alerts, custom domains, and 24/7 build queue.
        </p>
      </section>

      <section className="max-w-[1400px] mx-auto px-6 pb-24 grid grid-cols-1 md:grid-cols-3 gap-px bg-white/[0.06] border border-white/[0.06]">
        {plans.map((p) => (
          <div
            key={p.id}
            className={`relative bg-background p-8 flex flex-col ${p.highlight ? "tracing-border" : ""}`}
            data-testid={`plan-${p.id}`}
          >
            {p.highlight && (
              <div className="absolute top-3 right-3 text-[10px] font-mono uppercase tracking-[0.25em] text-brand">// recommended</div>
            )}
            <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">{p.name}</div>
            <div className="mt-3 flex items-baseline gap-1">
              <span className="font-display text-5xl font-semibold tracking-tighter">€{p.price}</span>
              <span className="text-zinc-500 text-sm">/{p.interval}</span>
            </div>
            <p className="mt-2 text-sm text-zinc-400">{p.tagline}</p>
            <ul className="mt-6 space-y-2 text-sm">
              {p.features.map((f) => (
                <li key={f} className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-brand" /> {f}
                </li>
              ))}
            </ul>
            <button
              onClick={() => choose(p.id)}
              className={`mt-8 inline-flex items-center justify-center gap-2 py-2.5 ${
                p.highlight ? "bg-brand text-brand-fg hover:bg-brand/90 shadow-[0_0_20px_rgba(0,229,255,0.25)]" : "border border-white/15 hover:border-white/40"
              }`}
              data-testid={`plan-cta-${p.id}`}
            >
              {p.id === "hobby" ? "Start free" : `Choose ${p.name}`} <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        ))}
      </section>
    </div>
  );
}

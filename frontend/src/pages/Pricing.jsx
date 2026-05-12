import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Check, ArrowRight, Sparkles, Shield, Rocket } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import Logo from "../components/Logo";
import useSpotlight from "../hooks/useSpotlight";

const PLAN_ICON = { hobby: Sparkles, pro: Rocket, agency: Shield };

function PlanCard({ plan, onChoose, index }) {
  const onMove = useSpotlight();
  const Icon = PLAN_ICON[plan.id] || Sparkles;
  return (
    <motion.div
      onMouseMove={onMove}
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: 0.1 * index, duration: 0.7 }}
      className={`spotlight relative bg-background p-8 flex flex-col border border-white/[0.08] ${plan.highlight ? "tracing-border" : ""}`}
      data-testid={`plan-${plan.id}`}
    >
      {plan.highlight && (
        <div className="!absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-fit px-3 py-1 bg-brand text-brand-fg text-[10px] font-mono uppercase tracking-[0.3em] inline-flex items-center gap-1.5 whitespace-nowrap z-10">
          <span className="h-1.5 w-1.5 rounded-full bg-brand-fg/70" />
          recommended
        </div>
      )}
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 border border-brand/40 flex items-center justify-center">
          <Icon className="h-4 w-4 text-brand" />
        </div>
        <div className="text-xs font-mono uppercase tracking-[0.35em] text-zinc-500">{plan.name}</div>
      </div>
      <div className="mt-5 flex items-baseline gap-1">
        <span className="font-display text-5xl font-semibold tracking-tighter">€{plan.price}</span>
        <span className="text-zinc-500 text-sm">/{plan.interval}</span>
      </div>
      <p className="mt-2 text-sm text-zinc-400">{plan.tagline}</p>

      <ul className="mt-7 space-y-2.5 text-sm flex-1">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2.5">
            <Check className="h-4 w-4 text-brand mt-0.5 flex-shrink-0" />
            <span className="text-zinc-300">{f}</span>
          </li>
        ))}
      </ul>

      <button
        onClick={() => onChoose(plan.id)}
        className={`magnetic-btn mt-8 inline-flex items-center justify-center gap-2 py-3 transition ${
          plan.highlight
            ? "bg-brand text-brand-fg font-medium hover:bg-brand/90 shadow-[0_0_28px_rgba(0,229,255,0.4)]"
            : "border border-white/15 hover:border-brand/70 hover:text-brand"
        }`}
        data-testid={`plan-cta-${plan.id}`}
      >
        {plan.id === "hobby" ? "Start free" : `Choose ${plan.name}`} <ArrowRight className="h-4 w-4" />
      </button>
    </motion.div>
  );
}

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
    <div className="min-h-screen bg-background text-foreground relative overflow-x-clip">
      {/* aurora bg */}
      <div className="fixed inset-0 -z-10 pointer-events-none">
        <div className="aurora-blob" style={{ top: "-5%", right: "-5%", height: 500, width: 500, background: "radial-gradient(circle, #00E5FF 0%, transparent 60%)", animation: "aurora-2 26s ease-in-out infinite" }} />
        <div className="aurora-blob" style={{ bottom: "-10%", left: "-10%", height: 520, width: 520, background: "radial-gradient(circle, #6B4BFF 0%, transparent 55%)", animation: "aurora-1 32s ease-in-out infinite" }} />
      </div>

      <header className="sticky top-0 z-30 bg-black/90 backdrop-blur-xl border-b border-zinc-900">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/"><Logo /></Link>
          <nav className="flex items-center gap-3">
            <Link to="/login" className="text-sm text-zinc-400 hover:text-brand transition-colors">Sign in</Link>
            <Link to="/register" className="magnetic-btn px-3 py-1.5 text-sm bg-brand text-brand-fg font-medium hover:bg-brand/90">Start free</Link>
          </nav>
        </div>
      </header>

      <section className="max-w-[1400px] mx-auto px-6 pt-24 pb-12 text-center relative">
        <div className="absolute inset-0 -z-10 bg-grid opacity-25" />
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.4em] text-brand"
        >
          <span className="h-px w-6 bg-brand/60" /> pricing <span className="h-px w-6 bg-brand/60" />
        </motion.div>
        <motion.h1
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="mt-5 font-display text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-semibold leading-[1.05]"
        >
          Pay for outcomes,<br /> not config.
        </motion.h1>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25 }}
          className="mt-6 text-sm sm:text-base text-zinc-400 max-w-md mx-auto"
        >
          Cancel any time. Monitoring, alerts, custom domains and a 24/7 build queue on every plan.
        </motion.p>
      </section>

      <section className="max-w-[1400px] mx-auto px-6 pb-28 grid grid-cols-1 md:grid-cols-3 gap-5">
        {plans.map((p, i) => (
          <PlanCard key={p.id} plan={p} onChoose={choose} index={i} />
        ))}
      </section>

      <section className="max-w-[1200px] mx-auto px-6 pb-28">
        <div className="border border-white/[0.06] p-8 md:p-10 relative overflow-hidden">
          <div className="absolute inset-0 -z-0 bg-grid-fine opacity-30" />
          <div className="relative grid md:grid-cols-3 gap-6 text-sm">
            <div>
              <div className="text-[10px] uppercase tracking-[0.35em] text-brand font-mono">// billing</div>
              <div className="font-display text-xl mt-2">EU VAT handled</div>
              <div className="text-zinc-400 mt-2">NL VAT, destination for B2C EU, reverse-charge for verified B2B VAT IDs.</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.35em] text-brand font-mono">// invoices</div>
              <div className="font-display text-xl mt-2">PDF invoices, auto</div>
              <div className="text-zinc-400 mt-2">Sequential numbering, downloadable from your billing tab, GDPR compliant.</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.35em] text-brand font-mono">// payment</div>
              <div className="font-display text-xl mt-2">Mollie-powered</div>
              <div className="text-zinc-400 mt-2">SEPA, iDEAL, Bancontact, card. Cancel anytime from the dashboard.</div>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/[0.06] py-8">
        <div className="max-w-[1400px] mx-auto px-6 flex items-center justify-between text-xs font-mono text-zinc-500">
          <Logo small />
          <div>© {new Date().getFullYear()} DeployUnit · Hosting for Next.js & Node</div>
        </div>
      </footer>
    </div>
  );
}

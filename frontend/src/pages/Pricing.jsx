import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import * as LucideIcons from "lucide-react";
import { Check, ArrowRight, Sparkles, Shield, Rocket, Coins } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import Logo from "../components/Logo";
import useSpotlight from "../hooks/useSpotlight";
import useSeo from "../hooks/useSeo";

const PLAN_ICON = { free: Sparkles, starter: Sparkles, pro: Rocket, agency: Shield };

// Fallback content used until /billing/pricing-page returns — keeps the
// page useful even if the backend is unreachable on first paint.
const PRICING_FALLBACK = {
  hero: {
    kicker: "Predictable. Transparent. EU-hosted.",
    title_lead: "Flat plans.",
    title_accent: "Transparent add-ons.",
    subtitle: "Pick a plan. Unlock extra features with credits — every add-on priced openly. No surprise bills, ever.",
  },
  addons_intro: {
    kicker: "credits unlock",
    title: "What you can do with credits.",
    subtitle: "Every plan includes a monthly credit allowance. Use them for the features below — buy more whenever you need, never expire.",
    footnote: "Every action shows its credit cost before you confirm. Watch your balance live on the dashboard. Hard cap toggle so you're never billed for more than you budgeted.",
  },
  addons: [],
};

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
        {plan.id === "free" ? "Start free" : `Choose ${plan.name}`} <ArrowRight className="h-4 w-4" />
      </button>
    </motion.div>
  );
}

export default function Pricing() {
  useSeo({
    title: "Pricing — DeployUnit",
    description: "Transparent EU hosting pricing for Next.js & Node.js. Free forever for personal projects. Pro from €19/mo. No vendor lock-in.",
    path: "/pricing",
  });
  const [plans, setPlans] = useState([]);
  const [cms, setCms] = useState(PRICING_FALLBACK);
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/billing/plans").then((r) => setPlans(r.data)).catch(() => {});
    api.get("/billing/pricing-page").then((r) => setCms(r.data)).catch(() => {});
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
          <span className="h-px w-6 bg-brand/60" /> {cms.hero.kicker || "pricing"} <span className="h-px w-6 bg-brand/60" />
        </motion.div>
        <motion.h1
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="mt-5 font-display text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-semibold leading-[1.05]"
        >
          {cms.hero.title_lead}<br /> <span className="text-brand">{cms.hero.title_accent}</span>
        </motion.h1>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25 }}
          className="mt-6 text-base sm:text-lg text-zinc-400 max-w-lg mx-auto leading-relaxed"
        >
          {cms.hero.subtitle}
        </motion.p>
      </section>

      <section className="max-w-[1400px] mx-auto px-6 pb-20 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {plans.map((p, i) => (
          <PlanCard key={p.id} plan={p} onChoose={choose} index={i} />
        ))}
      </section>

      {/* What credits unlock — admin-managed catalog. We dynamically resolve
          the lucide icon by name from the CMS payload; unknown icon names
          fall back to Sparkles so a typo never crashes the page. */}
      {cms.addons.length > 0 && (
        <section className="max-w-[1200px] mx-auto px-6 pb-20" data-testid="addons-catalog">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.4em] text-brand">
              <Coins className="h-3 w-3" /> {cms.addons_intro.kicker}
            </div>
            <h2 className="mt-4 font-display text-3xl md:text-5xl tracking-tighter font-semibold leading-[1.1]">
              {cms.addons_intro.title}
            </h2>
            <p className="mt-4 text-zinc-400 max-w-xl mx-auto">
              {cms.addons_intro.subtitle}
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-white/[0.06] border border-white/[0.06]">
            {cms.addons.map((addon, i) => {
              const Ai = LucideIcons[addon.icon] || Sparkles;
              return (
                <motion.div
                  key={addon.id || addon.name}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  className="bg-background p-6"
                  data-testid={`addon-${(addon.id || addon.name).toLowerCase().replace(/\s+/g,'-')}`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="h-9 w-9 border border-brand/40 flex items-center justify-center">
                      <Ai className="h-4 w-4 text-brand" />
                    </div>
                    <div className="text-xs font-mono text-brand">{addon.price}</div>
                  </div>
                  <div className="font-display text-lg text-zinc-100">{addon.name}</div>
                  <div className="mt-2 text-sm text-zinc-400 leading-relaxed">{addon.hint}</div>
                </motion.div>
              );
            })}
          </div>
          <div className="mt-6 text-center text-xs font-mono text-zinc-500">
            {cms.addons_intro.footnote}
          </div>
        </section>
      )}

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

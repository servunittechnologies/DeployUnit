import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  Leaf, MapPin, ShieldCheck, Sparkles, Users, Rocket, Zap, Globe,
  ArrowRight, Heart,
} from "lucide-react";
import MarketingLayout from "../components/MarketingLayout";

function Section({ id, className = "", children }) {
  return (
    <section id={id} className={`max-w-5xl mx-auto px-6 lg:px-8 ${className}`}>{children}</section>
  );
}

function Overline({ children, color = "text-cyan-400" }) {
  return (
    <div className={`inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.4em] ${color}`}>
      <span className={`h-px w-6 ${color === "text-cyan-400" ? "bg-cyan-500/60" : "bg-emerald-500/60"}`} />
      {children}
    </div>
  );
}

const VALUES = [
  {
    icon: MapPin, title: "EU-first by default",
    body: "Your data, your customers' data, and your billing all live inside the EU. GDPR is not a checkbox — it's how we ship.",
  },
  {
    icon: Leaf, title: "Sustainability as a metric",
    body: "We measure our carbon footprint quarterly, push our renewable mix up every cycle, and plant a tree for every deploy.",
  },
  {
    icon: Users, title: "Built for agencies",
    body: "Workspaces, per-customer billing, audit logs and credit budgets — the patterns we wished existed when running our own studio.",
  },
  {
    icon: ShieldCheck, title: "Boringly transparent",
    body: "Public roadmap, public status page, honest pricing. No surprise invoices and no carbon-offset accounting tricks.",
  },
];

const TIMELINE = [
  { year: "2022", title: "ServUnit Technologies BV",
    body: "Founded in Belgium. We start building the infrastructure layer — datacenters, dark-fiber network, and the operational tooling — that will eventually power three brands." },
  { year: "2023", title: "ServUnit launches",
    body: <>Our enterprise hosting brand goes live at <a href="https://servunit.com" target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">servunit.com</a> — web hosting, domains, VPS, dedicated servers and colocation for developers, entrepreneurs and organisations, served from SmartDC Rotterdam over our own 40 Gbps+ network.</> },
  { year: "2024", title: "GameUnit launches",
    body: <>We open a second front for gamers at <a href="https://gameunit.pro" target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">gameunit.pro</a> — Minecraft, FiveM, ARK, Rust, Satisfactory and more, with 12 TB/s DDoS protection, instant delivery, and a control panel built for low-latency multiplayer.</> },
  { year: "2026", title: "DeployHub — new",
    body: "Now we open the same EU infrastructure to modern developers and agencies as a fully-managed PaaS. Push to Git, get a live URL, full container metrics — backed by the network and operations team that already runs ServUnit and GameUnit." },
];

export default function About() {
  return (
    <MarketingLayout>
      {/* Hero */}
      <Section className="pt-24 lg:pt-32 pb-16">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <Overline>About us</Overline>
          <h1 className="mt-4 font-display text-4xl md:text-6xl font-bold tracking-tighter leading-[0.95]">
            Built by people who <span className="text-cyan-400">ship for a living.</span>
          </h1>
          <p className="mt-6 text-base sm:text-lg text-zinc-400 max-w-2xl leading-relaxed">
            DeployHub is the EU-hosted PaaS we wished existed when running our own agency.
            We're crafting it in Belgium, powered by ServUnit Technologies BV, and we're betting
            that European teams deserve a deploy platform that takes their data, their carbon footprint,
            and their craft seriously.
          </p>
        </motion.div>
      </Section>

      {/* Stats strip */}
      <Section className="pb-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { k: "EU", v: "datacenters only" },
            { k: "70%+", v: "renewable energy" },
            { k: "240+", v: "agencies onboard" },
            { k: "99.99%", v: "platform uptime" },
          ].map((s) => (
            <motion.div
              key={s.v}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4 }}
              className="border border-zinc-800 bg-zinc-950/40 p-5 text-center"
            >
              <div className="font-display text-3xl text-white font-bold">{s.k}</div>
              <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mt-2">{s.v}</div>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* Values */}
      <Section className="py-16">
        <div className="mb-10 max-w-2xl">
          <Overline>What we believe</Overline>
          <h2 className="mt-3 font-display text-3xl md:text-4xl font-bold tracking-tighter">Four principles, no asterisks.</h2>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          {VALUES.map((v) => (
            <motion.div
              key={v.title}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4 }}
              className="border border-zinc-800 bg-zinc-950/40 p-6 hover:border-cyan-500/40 transition-colors"
              data-testid={`about-value-${v.title.split(" ")[0].toLowerCase()}`}
            >
              <v.icon className="h-5 w-5 text-cyan-400 mb-3" />
              <div className="font-display text-lg font-semibold text-white">{v.title}</div>
              <p className="mt-2 text-sm text-zinc-400 leading-relaxed">{v.body}</p>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* Timeline */}
      <Section className="py-16">
        <div className="mb-10 max-w-2xl">
          <Overline>How we got here</Overline>
          <h2 className="mt-3 font-display text-3xl md:text-4xl font-bold tracking-tighter">A short story.</h2>
        </div>
        <div className="relative border-l border-zinc-800 pl-6 space-y-8">
          {TIMELINE.map((t, i) => (
            <motion.div
              key={t.year}
              initial={{ opacity: 0, x: -12 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
              className="relative"
            >
              <span className="absolute -left-[31px] top-1 h-3 w-3 bg-cyan-400 rounded-full shadow-[0_0_8px_2px_rgba(6,182,212,0.5)]" />
              <div className="text-[10px] uppercase tracking-[0.4em] font-mono text-cyan-400 mb-1">{t.year}</div>
              <div className="font-display text-lg font-semibold text-white">{t.title}</div>
              <p className="mt-1.5 text-sm text-zinc-400 max-w-xl">{t.body}</p>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* Sustainability anchor section */}
      <Section id="sustainability" className="py-16">
        <div className="border border-emerald-500/30 bg-gradient-to-r from-emerald-950/40 via-black to-black p-8 lg:p-10">
          <div className="flex items-start gap-4 mb-4">
            <div className="p-2 border border-emerald-500/30 bg-black/40">
              <Leaf className="h-5 w-5 text-emerald-400" />
            </div>
            <div>
              <Overline color="text-emerald-400">Sustainability</Overline>
              <h2 className="mt-2 font-display text-2xl md:text-3xl font-bold tracking-tighter">Greener with every deploy.</h2>
            </div>
          </div>
          <p className="text-zinc-300 leading-relaxed max-w-2xl">
            Our EU datacenters run mostly on renewable wind & solar today — and we invest every quarter to push that further.
            For every app you deploy, we plant one extra tree via{" "}
            <a href="https://teamtrees.org" target="_blank" rel="noreferrer" className="text-emerald-400 underline hover:text-emerald-300">teamtrees.org</a>.
            Real trees, verified by the Arbor Day Foundation.
          </p>
        </div>
      </Section>

      {/* CTA */}
      <Section className="py-20 text-center">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5 }}>
          <h2 className="font-display text-3xl md:text-4xl font-bold tracking-tighter">Want to join the journey?</h2>
          <p className="mt-3 text-zinc-400 max-w-xl mx-auto">Try DeployHub free for 14 days, or get in touch — we're easy to reach.</p>
          <div className="mt-7 flex flex-wrap gap-3 justify-center">
            <Link
              to="/register"
              className="group inline-flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-6 py-3 transition-colors"
              data-testid="about-cta-register"
            >
              Start deploying <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              to="/contact"
              className="inline-flex items-center gap-2 border border-zinc-700 hover:border-cyan-500 text-white px-6 py-3 transition-colors font-mono text-sm uppercase tracking-wider"
              data-testid="about-cta-contact"
            >
              Talk to us
            </Link>
          </div>
        </motion.div>
      </Section>
    </MarketingLayout>
  );
}

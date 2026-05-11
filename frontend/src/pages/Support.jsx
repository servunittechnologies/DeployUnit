import { useState } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  ArrowRight, BookOpen, ChevronDown, CreditCard, GitBranch, HeartHandshake,
  LifeBuoy, MessageSquare, Mail, Search, Server, Sparkles, ShieldCheck,
  Wrench,
} from "lucide-react";
import MarketingLayout from "../components/MarketingLayout";

function Section({ className = "", children }) {
  return <section className={`max-w-5xl mx-auto px-6 lg:px-8 ${className}`}>{children}</section>;
}

function Overline({ children }) {
  return (
    <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.4em] text-cyan-400">
      <span className="h-px w-6 bg-cyan-500/60" />
      {children}
    </div>
  );
}

const CATEGORIES = [
  { icon: Sparkles,  title: "Getting started",     body: "Connect your first repo, deploy in 41 seconds, and understand the dashboard." },
  { icon: GitBranch, title: "Deploys & builds",    body: "Buildpacks, build args, custom Dockerfiles, PR previews, rollbacks." },
  { icon: Server,    title: "Domains & DNS",       body: "Custom domains, SSL, DNS records, Cloudflare integration." },
  { icon: CreditCard,title: "Billing & credits",   body: "Plans, credit wallet, VAT, invoices, downgrades and upgrades." },
  { icon: ShieldCheck,title:"Security & teams",    body: "Workspaces, roles, audit logs, two-factor, OAuth tokens." },
  { icon: Wrench,    title: "Troubleshooting",     body: "Build failures, container restarts, env-var debugging, status checks." },
];

const FAQ = [
  { q: "How long does my first deploy take?",
    a: "On average 41 seconds from a fresh GitHub repo. Auto-detection runs against your package.json / Dockerfile / requirements.txt and picks the right buildpack." },
  { q: "Where is my data stored?",
    a: "Entirely inside the EU. We never replicate customer data outside the EU." },
  { q: "Can I bring my own domain?",
    a: "Yes. Add it under Domains, point a CNAME or A record at the assigned address, and we issue a free Let's Encrypt certificate automatically." },
  { q: "What happens if I exceed my plan limits?",
    a: "Resource overages (vCPU, RAM, storage) are billed through the credit wallet at transparent per-unit rates — no surprise invoices and no hard cutoffs mid-month." },
  { q: "Do you offer Slack / Discord / SMS alerts?",
    a: "Yes, on every plan. Wire any combination of channels per app under Notifications. SMS and WhatsApp deductions are credit-billed only when they fire." },
  { q: "How do refunds work?",
    a: "First 14 days are no-questions-asked refundable. After that, contact us — we're reasonable." },
  { q: "Is there a free tier?",
    a: "There's a 14-day free trial that's identical to the Pro plan. After that, the cheapest paid plan starts at €9/mo." },
  { q: "What's your uptime SLA?",
    a: "99.9% on Pro, 99.95% on Agency, with auto-credit on any breach. Live status is at /status." },
];

function FaqItem({ q, a, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-zinc-800 bg-zinc-950/40" data-testid={`faq-${q.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 30)}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-left text-sm text-zinc-200 hover:text-white"
      >
        <span className="font-medium">{q}</span>
        <ChevronDown className={`h-4 w-4 text-zinc-500 shrink-0 transition-transform ${open ? "rotate-180 text-cyan-400" : ""}`} />
      </button>
      <motion.div
        initial={false}
        animate={{ height: open ? "auto" : 0, opacity: open ? 1 : 0 }}
        transition={{ duration: 0.25 }}
        className="overflow-hidden"
      >
        <div className="px-5 pb-4 text-sm text-zinc-400 leading-relaxed">{a}</div>
      </motion.div>
    </div>
  );
}

const QUICK_LINKS = [
  { title: "Live system status",  body: "Real-time health of every component.",    to: "/status",  icon: ShieldCheck },
  { title: "Email a human",       body: "Reach support in one business day.",      to: "/contact", icon: Mail },
  { title: "About DeployHub",     body: "Why we exist, what we believe.",          to: "/about",   icon: HeartHandshake },
];

export default function Support() {
  const [q, setQ] = useState("");
  const filteredFaq = FAQ.filter((f) =>
    !q || f.q.toLowerCase().includes(q.toLowerCase()) || f.a.toLowerCase().includes(q.toLowerCase()),
  );

  return (
    <MarketingLayout>
      <Section className="pt-24 lg:pt-32 pb-12">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <Overline>Support</Overline>
          <h1 className="mt-4 font-display text-4xl md:text-6xl font-bold tracking-tighter leading-[0.95]">
            How can we <span className="text-cyan-400">help?</span>
          </h1>
          <p className="mt-6 text-base sm:text-lg text-zinc-400 max-w-2xl">
            Browse the most common questions below, or reach a human via the contact form — we read every single message.
          </p>

          {/* Search */}
          <div className="mt-8 relative max-w-xl">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search the help center…"
              className="w-full bg-zinc-950/40 border border-zinc-800 focus:border-cyan-500 outline-none pl-10 pr-3 py-3 text-sm text-zinc-200"
              data-testid="support-search"
            />
          </div>
        </motion.div>
      </Section>

      {/* Categories */}
      <Section className="pb-16">
        <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 mb-4">// browse by topic</div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {CATEGORIES.map((c) => (
            <motion.div
              key={c.title}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.35 }}
              className="border border-zinc-800 bg-zinc-950/40 p-5 hover:border-cyan-500/40 transition-colors"
              data-testid={`support-category-${c.title.split(" ")[0].toLowerCase()}`}
            >
              <c.icon className="h-4 w-4 text-cyan-400 mb-3" />
              <div className="font-display text-base font-semibold text-white">{c.title}</div>
              <div className="mt-1.5 text-xs text-zinc-400 leading-relaxed">{c.body}</div>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* FAQ */}
      <Section className="pb-16">
        <div className="mb-6">
          <Overline>Frequently asked</Overline>
          <h2 className="mt-3 font-display text-2xl md:text-3xl font-bold tracking-tighter">Quick answers.</h2>
        </div>
        {filteredFaq.length === 0 ? (
          <div className="border border-dashed border-zinc-800 p-8 text-center text-sm font-mono text-zinc-500">
            No matches for "{q}". Try the contact form — we'll write the answer ourselves.
          </div>
        ) : (
          <div className="space-y-2" data-testid="support-faq-list">
            {filteredFaq.map((f, i) => (
              <FaqItem key={f.q} q={f.q} a={f.a} defaultOpen={i === 0 && !q} />
            ))}
          </div>
        )}
      </Section>

      {/* Quick links */}
      <Section className="pb-16">
        <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 mb-4">// other ways to reach us</div>
        <div className="grid md:grid-cols-3 gap-3">
          {QUICK_LINKS.map((l) => (
            <Link
              key={l.title}
              to={l.to}
              className="group border border-zinc-800 bg-zinc-950/40 p-5 hover:border-cyan-500/40 transition-colors"
              data-testid={`support-quick-${l.to.replace("/", "")}`}
            >
              <div className="flex items-start gap-3">
                <div className="p-2 border border-zinc-800 bg-black shrink-0">
                  <l.icon className="h-4 w-4 text-cyan-400" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-display text-base font-semibold text-white">{l.title}</span>
                    <ArrowRight className="h-3.5 w-3.5 text-zinc-500 group-hover:text-cyan-400 group-hover:translate-x-0.5 transition-all" />
                  </div>
                  <div className="mt-1 text-xs text-zinc-400">{l.body}</div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </Section>

      {/* CTA strip */}
      <Section className="pb-20">
        <div className="border border-zinc-800 bg-zinc-950/40 p-6 md:p-8 flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <LifeBuoy className="h-6 w-6 text-cyan-400" />
            <div>
              <div className="font-display text-lg font-semibold">Still need a hand?</div>
              <div className="text-xs text-zinc-400">Drop us a line — we typically reply within one business day.</div>
            </div>
          </div>
          <Link
            to="/contact"
            className="inline-flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-5 py-2.5 transition-colors"
            data-testid="support-cta-contact"
          >
            <MessageSquare className="h-4 w-4" /> Open a ticket
          </Link>
        </div>
      </Section>
    </MarketingLayout>
  );
}

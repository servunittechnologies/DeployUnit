import { useEffect, useMemo, useState } from "react";
import { api, getApiErrorMessage } from "../../lib/api";
import { useAuth } from "../../contexts/AuthContext";
import {
  Activity, Mail, Globe2, Code2, Sparkles, Check, Loader2, Bell, ArrowRight,
  GitBranch, Bot, FileText, Layers, Wrench, Briefcase, Server, BarChart3,
} from "lucide-react";
import { toast } from "sonner";

// Stable order — by category, ETA-agnostic for now.
const CATEGORIES = [
  { id: "all",       label: "All",                  icon: Layers },
  { id: "analytics", label: "Analytics & Insights", icon: BarChart3 },
  { id: "dx",        label: "Developer experience", icon: Wrench },
  { id: "business",  label: "Business tools",       icon: Briefcase },
  { id: "infra",     label: "Infrastructure",       icon: Server },
];

const FEATURES = [
  // Analytics & Insights
  {
    id: "heatmaps", category: "analytics",
    title: "Native heatmaps & session replays",
    tagline: "See exactly where every visitor clicks, scrolls, and rage-clicks.",
    icon: Activity,
    bullets: ["Click density heatmaps", "Session replay (rrweb)", "Dead & rage clicks"],
  },

  // Developer experience
  {
    id: "branching", category: "dx",
    title: "Database branching",
    tagline: "Spin up an instant prod-clone DB for every pull request.",
    icon: GitBranch,
    bullets: ["1-click PR snapshots", "Reset to prod anytime", "Auto-cleanup on merge"],
  },
  {
    id: "copilot", category: "dx",
    title: "AI Code Co-pilot",
    tagline: "Chat with an AI that knows your codebase + live logs.",
    icon: Bot,
    bullets: ["Explain build failures", "1-click fix PRs", "Refactor across files"],
  },
  {
    id: "visualdiff", category: "dx",
    title: "Visual deploy diffs",
    tagline: "Auto-screenshot every page on every deploy — side-by-side before/after.",
    icon: Sparkles,
    bullets: ["Pixel diff per route", "Stakeholder-friendly view", "Approve UI changes in PR"],
  },
  {
    id: "api", category: "dx",
    title: "Developers API",
    tagline: "Script deploys, scale resources, and pull metrics — programmatically.",
    icon: Code2,
    bullets: ["REST + GraphQL", "Node + Python SDKs", "Terraform provider"],
  },

  // Business tools
  {
    id: "reports", category: "business",
    title: "White-label client reports",
    tagline: "Auto-emailed PDF reports per app: uptime, performance, traffic — branded as you.",
    icon: FileText,
    bullets: ["Monthly auto-PDF", "Your logo & colors", "Per-app + per-customer"],
  },

  // Infrastructure
  {
    id: "mailserver", category: "infra",
    title: "Mailserver hosting",
    tagline: "Send and receive on your own domain — no SendGrid, no SES.",
    icon: Mail,
    bullets: ["SMTP + IMAP", "Auto SPF / DKIM / DMARC", "EU-resident mailboxes"],
  },
  {
    id: "dns", category: "infra",
    title: "DNS Manager",
    tagline: "Full DNS authority for every customer domain, side-by-side with their apps.",
    icon: Globe2,
    bullets: ["Authoritative DNS", "GeoDNS routing", "DNSSEC + apex flattening"],
  },
];

function WaitlistInline({ feature, defaultEmail }) {
  const [email, setEmail] = useState(defaultEmail || "");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const join = async (e) => {
    e?.preventDefault?.();
    if (!email || !email.includes("@")) {
      toast.error("Please enter a valid email.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.post("/roadmap/waitlist", { feature, email });
      setDone(true);
      toast.success(r.data?.already_signed_up
        ? "You're already on the waitlist."
        : "You're on the waitlist — we'll email you on launch.");
    } catch (e2) { toast.error(getApiErrorMessage(e2)); }
    finally { setBusy(false); }
  };

  if (done) {
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-mono bg-signal-success/10 text-signal-success border border-signal-success/30"
           data-testid={`waitlist-done-${feature}`}>
        <Check className="h-3 w-3" /> on the waitlist
      </div>
    );
  }

  return (
    <form onSubmit={join} className="flex gap-1.5">
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@company.com"
        className="flex-1 bg-black/40 border border-white/[0.08] focus:border-brand outline-none px-2.5 py-1.5 text-xs font-mono text-zinc-200"
        data-testid={`waitlist-email-${feature}`}
      />
      <button
        type="submit"
        disabled={busy}
        className="inline-flex items-center justify-center gap-1 px-3 py-1.5 bg-brand text-brand-fg text-xs font-medium hover:bg-brand/90 disabled:opacity-50 whitespace-nowrap"
        data-testid={`waitlist-submit-${feature}`}
      >
        {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Bell className="h-3 w-3" />}
        Notify
      </button>
    </form>
  );
}

function FeatureCard({ f, count, defaultEmail }) {
  return (
    <div
      className="relative h-full border border-white/[0.06] p-5 hover:border-brand/40 transition-colors duration-300 flex flex-col"
      data-testid={`roadmap-feature-${f.id}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-start gap-2.5 min-w-0">
          <div className="p-1.5 bg-brand/10 border border-brand/30 shrink-0">
            <f.icon className="h-4 w-4 text-brand" />
          </div>
          <h3 className="font-display text-base tracking-tight leading-snug pt-0.5">{f.title}</h3>
        </div>
        <span className="text-[9px] font-mono uppercase tracking-[0.25em] bg-brand/10 text-brand border border-brand/30 px-1.5 py-0.5 shrink-0 whitespace-nowrap">
          soon
        </span>
      </div>

      <p className="text-xs text-zinc-400 leading-relaxed mb-3">{f.tagline}</p>

      <ul className="text-[11px] font-mono text-zinc-500 space-y-1 mb-4 flex-1">
        {f.bullets.map((b) => (
          <li key={b} className="flex items-start gap-1.5">
            <ArrowRight className="h-2.5 w-2.5 text-brand/70 shrink-0 mt-1" /> {b}
          </li>
        ))}
      </ul>

      <div className="space-y-1.5">
        <WaitlistInline feature={f.id} defaultEmail={defaultEmail} />
        {count > 0 && (
          <div className="text-[10px] font-mono text-zinc-500" data-testid={`roadmap-count-${f.id}`}>
            {count} {count === 1 ? "dev" : "devs"} waiting
          </div>
        )}
      </div>
    </div>
  );
}

export default function Roadmap() {
  const { user } = useAuth();
  const [counts, setCounts] = useState({});
  const [activeCat, setActiveCat] = useState("all");

  useEffect(() => {
    api.get("/roadmap/features").then((r) => {
      const c = {};
      for (const f of r.data || []) c[f.id] = f.waitlist_count;
      setCounts(c);
    }).catch(() => {});
  }, []);

  const totalWaiting = useMemo(
    () => Object.values(counts).reduce((a, b) => a + (b || 0), 0),
    [counts],
  );

  const visible = activeCat === "all"
    ? FEATURES
    : FEATURES.filter((f) => f.category === activeCat);

  // Group by category when showing "all" — gives the page structure without
  // making the user think.
  const grouped = useMemo(() => {
    if (activeCat !== "all") return null;
    const out = {};
    for (const f of FEATURES) {
      (out[f.category] = out[f.category] || []).push(f);
    }
    return out;
  }, [activeCat]);

  return (
    <div className="px-8 py-10 max-w-7xl mx-auto" data-testid="roadmap-page">
      {/* Hero */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.3em] bg-brand/10 text-brand border border-brand/30 mb-3">
            <Sparkles className="h-3 w-3" /> public roadmap
          </div>
          <h1 className="font-display text-4xl sm:text-5xl tracking-tight">What we're shipping next</h1>
          <p className="text-zinc-400 mt-2 max-w-2xl text-sm">
            Big features in active development. Drop your email on any of them and we'll ping you the day it goes live —
            no marketing follow-ups, just launch announcements.
          </p>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">total waiting</div>
          <div className="font-display text-3xl tracking-tight" data-testid="roadmap-total-waiting">{totalWaiting}</div>
        </div>
      </div>

      {/* Category filter */}
      <div className="flex flex-wrap gap-1.5 mb-8 border-b border-white/[0.06] pb-1">
        {CATEGORIES.map((c) => {
          const count = c.id === "all"
            ? FEATURES.length
            : FEATURES.filter((f) => f.category === c.id).length;
          const active = activeCat === c.id;
          return (
            <button
              key={c.id}
              onClick={() => setActiveCat(c.id)}
              data-testid={`roadmap-filter-${c.id}`}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border-b-2 -mb-px transition-colors ${
                active
                  ? "border-brand text-brand"
                  : "border-transparent text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <c.icon className="h-3 w-3" />
              {c.label}
              <span className={`text-[10px] ${active ? "text-brand/70" : "text-zinc-600"}`}>{count}</span>
            </button>
          );
        })}
      </div>

      {/* Body */}
      {activeCat === "all" ? (
        <div className="space-y-10">
          {CATEGORIES.filter((c) => c.id !== "all").map((c) => {
            const items = grouped?.[c.id] || [];
            if (items.length === 0) return null;
            return (
              <section key={c.id} data-testid={`roadmap-section-${c.id}`}>
                <div className="flex items-center gap-2 mb-3">
                  <c.icon className="h-3.5 w-3.5 text-zinc-500" />
                  <h2 className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500">{c.label}</h2>
                  <div className="flex-1 h-px bg-white/[0.06]" />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {items.map((f) => (
                    <FeatureCard key={f.id} f={f} count={counts[f.id] ?? 0} defaultEmail={user?.email} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {visible.map((f) => (
            <FeatureCard key={f.id} f={f} count={counts[f.id] ?? 0} defaultEmail={user?.email} />
          ))}
        </div>
      )}

      <div className="mt-14 border-t border-white/[0.06] pt-6 text-[11px] font-mono text-zinc-500 flex items-center justify-between flex-wrap gap-2">
        <span>Want something else? <a href="mailto:hello@deployhub.app" className="text-brand hover:underline">Tell us</a> what would unblock you next.</span>
        <span>You'll be the first to know when these ship — check Settings → Notifications for in-app pings.</span>
      </div>
    </div>
  );
}

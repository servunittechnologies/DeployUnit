import { useEffect, useState } from "react";
import { api, getApiErrorMessage } from "../../lib/api";
import { useAuth } from "../../contexts/AuthContext";
import {
  Activity, Mail, Globe2, Code2, Sparkles, Check, Loader2, Bell, ArrowRight,
} from "lucide-react";
import { toast } from "sonner";

const FEATURES = [
  {
    id: "heatmaps",
    title: "Native heatmaps & session replays",
    tagline: "See exactly where every visitor clicks, scrolls, and rage-clicks.",
    icon: Activity,
    body: "A first-party recording engine built right into DeployHub. Click heatmaps overlaid on auto-captured page screenshots, full session replay with rrweb, dead-click + rage-click detection, scroll-depth maps — all stored in your own infrastructure. No third-party scripts.",
    bullets: ["Click density heatmaps", "Session replay (rrweb)", "Dead & rage clicks", "Scroll depth maps", "Privacy-first · anonymous"],
    accent: "from-fuchsia-500/30 to-brand/20",
  },
  {
    id: "mailserver",
    title: "Mailserver hosting",
    tagline: "Send and receive on your own domain — no SendGrid, no SES.",
    icon: Mail,
    body: "Fully managed SMTP + IMAP + transactional API per workspace. Auto SPF/DKIM/DMARC, EU-resident mailboxes, catch-all aliases, and one-click rotation of credentials. Pair it with your DeployHub app for `noreply@your-customer.com` deliverability without ops headaches.",
    bullets: ["Outbound SMTP relay", "Inbound IMAP mailboxes", "Auto SPF / DKIM / DMARC", "Per-workspace EU storage", "Transactional API"],
    accent: "from-emerald-500/30 to-brand/20",
  },
  {
    id: "dns",
    title: "DNS Manager",
    tagline: "Full DNS authority for every customer domain, side-by-side with their apps.",
    icon: Globe2,
    body: "Manage A / AAAA / CNAME / MX / TXT / SRV records straight from DeployHub. Auto-provision GeoDNS for multi-region apps, instant subdomain templates, native ANAME flattening for apex domains, and changelog auditing on every record.",
    bullets: ["Authoritative DNS per zone", "GeoDNS routing", "Apex ANAME flattening", "DNSSEC", "Changelog with one-click rollback"],
    accent: "from-sky-500/30 to-brand/20",
  },
  {
    id: "api",
    title: "Developers API",
    tagline: "Script deploys, scale resources, and pull metrics — programmatically.",
    icon: Code2,
    body: "A public REST + GraphQL API surfacing every action you can take in the dashboard. Personal access tokens per workspace, scoped permissions, generous rate limits, official Node + Python SDKs, and a Terraform provider for infrastructure-as-code.",
    bullets: ["REST + GraphQL", "Personal access tokens", "Node.js & Python SDKs", "Terraform provider", "Webhooks for every event"],
    accent: "from-amber-500/30 to-brand/20",
  },
];

function WaitlistButton({ feature, defaultEmail }) {
  const [email, setEmail] = useState(defaultEmail || "");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const join = async () => {
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
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  if (done) {
    return (
      <div className="inline-flex items-center gap-2 px-4 py-2 bg-signal-success/10 text-signal-success border border-signal-success/30 text-sm font-medium"
           data-testid={`waitlist-done-${feature}`}>
        <Check className="h-4 w-4" /> You're on the waitlist
      </div>
    );
  }

  return (
    <div className="flex flex-col sm:flex-row gap-2 max-w-md">
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@company.com"
        className="flex-1 bg-black/40 border border-white/[0.08] focus:border-brand outline-none px-3 py-2 text-sm font-mono text-zinc-200"
        data-testid={`waitlist-email-${feature}`}
      />
      <button
        onClick={join}
        disabled={busy}
        className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-brand text-brand-fg text-sm font-medium hover:bg-brand/90 disabled:opacity-50"
        data-testid={`waitlist-submit-${feature}`}
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}
        Notify me
      </button>
    </div>
  );
}

function FeatureCard({ f, counts, defaultEmail }) {
  const count = counts[f.id] ?? 0;
  return (
    <div className="relative overflow-hidden border border-white/[0.06] p-8 group" data-testid={`roadmap-feature-${f.id}`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${f.accent} opacity-0 group-hover:opacity-30 transition-opacity duration-700 pointer-events-none`} />
      <div
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage: "linear-gradient(#ffffff 1px, transparent 1px), linear-gradient(90deg, #ffffff 1px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      />
      <div className="relative">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-brand/10 border border-brand/30">
              <f.icon className="h-5 w-5 text-brand" />
            </div>
            <div>
              <h3 className="font-display text-2xl tracking-tight">{f.title}</h3>
              <p className="text-zinc-400 text-sm mt-1.5">{f.tagline}</p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.3em] bg-brand/10 text-brand border border-brand/30 shrink-0 whitespace-nowrap">
            <Sparkles className="h-3 w-3" /> coming soon
          </span>
        </div>

        <p className="text-sm text-zinc-300 leading-relaxed mb-5 max-w-2xl">{f.body}</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-6 max-w-xl">
          {f.bullets.map((b) => (
            <div key={b} className="flex items-center gap-2 text-xs font-mono text-zinc-400">
              <ArrowRight className="h-3 w-3 text-brand/70" /> {b}
            </div>
          ))}
        </div>

        <div className="flex items-end justify-between flex-wrap gap-4">
          <WaitlistButton feature={f.id} defaultEmail={defaultEmail} />
          {count > 0 && (
            <div className="text-[11px] font-mono text-zinc-500" data-testid={`roadmap-count-${f.id}`}>
              {count} {count === 1 ? "developer" : "developers"} waiting
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Roadmap() {
  const { user } = useAuth();
  const [counts, setCounts] = useState({});

  useEffect(() => {
    api.get("/roadmap/features").then((r) => {
      const c = {};
      for (const f of r.data || []) c[f.id] = f.waitlist_count;
      setCounts(c);
    }).catch(() => {});
  }, []);

  return (
    <div className="px-8 py-10 max-w-7xl" data-testid="roadmap-page">
      <div className="mb-10">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.3em] bg-brand/10 text-brand border border-brand/30 mb-4">
          <Sparkles className="h-3 w-3" /> public roadmap
        </div>
        <h1 className="font-display text-4xl sm:text-5xl tracking-tight">What we're shipping next</h1>
        <p className="text-zinc-400 mt-3 max-w-2xl">
          Big features in active development. Drop your email on any of them and we'll email you the day they go live —
          no marketing follow-ups, just launch announcements.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {FEATURES.map((f) => (
          <FeatureCard key={f.id} f={f} counts={counts} defaultEmail={user?.email} />
        ))}
      </div>

      <div className="mt-14 border-t border-white/[0.06] pt-6 text-[11px] font-mono text-zinc-500 flex items-center justify-between flex-wrap gap-2">
        <span>Want something else? <a href="mailto:hello@deployhub.app" className="text-brand hover:underline">Tell us</a> what would unblock you next.</span>
        <span>Tip: keep an eye on the Settings → Notifications tab to enable in-app pings.</span>
      </div>
    </div>
  );
}

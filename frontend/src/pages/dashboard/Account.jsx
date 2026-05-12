import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getApiErrorMessage } from "../../lib/api";
import { useAuth } from "../../contexts/AuthContext";
import {
  Save, User as UserIcon, KeyRound, Sparkles, Wallet, Receipt,
  Bell, Github, CheckCircle2, Trash2, Send, MessageSquare, Phone, Mail,
  ArrowRight, ShieldCheck, ExternalLink, Plus,
} from "lucide-react";
import { toast } from "sonner";
import GitHubButton from "../../components/GitHubButton";

const EVENT_LABELS = {
  deploy_failed: "Deploy failed",
  deploy_succeeded: "Deploy succeeded",
  app_down: "App down (uptime)",
  app_recovered: "App recovered",
  build_warning: "Build warning",
  domain_expiring: "Domain expiring soon",
  credits_low: "Credits running low",
};
const CHANNEL_META = {
  sms: { label: "SMS", icon: Phone },
  whatsapp: { label: "WhatsApp", icon: MessageSquare },
  email: { label: "Email", icon: Mail },
  slack: { label: "Slack", icon: MessageSquare },
  discord: { label: "Discord", icon: MessageSquare },
};

// Sticky in-page tab nav so the page never feels like one giant scroll
const SECTIONS = [
  { id: "profile", label: "Profile", icon: UserIcon },
  { id: "plan", label: "Plan & usage", icon: Sparkles },
  { id: "credits", label: "Credits wallet", icon: Wallet },
  { id: "billing", label: "Billing & invoices", icon: Receipt },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "security", label: "Security", icon: ShieldCheck },
];

function SectionHeader({ id, icon: Icon, title, subtitle }) {
  return (
    <div id={id} className="scroll-mt-24">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="h-4 w-4 text-brand" />
        <h2 className="font-display text-xl tracking-tight">{title}</h2>
      </div>
      {subtitle && <p className="text-xs text-zinc-500 mb-4">{subtitle}</p>}
    </div>
  );
}

function UsageBar({ used, cap }) {
  const unlimited = cap === undefined || cap === null || cap < 0;
  const pct = unlimited ? 0 : Math.min(100, Math.round((used / Math.max(cap, 1)) * 100));
  const tone = pct > 90 ? "bg-signal-failed" : pct > 70 ? "bg-signal-queued" : "bg-brand";
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between">
        <span className="font-display text-lg">{used}{unlimited ? "" : <span className="text-zinc-500 text-sm"> / {cap}</span>}</span>
        {unlimited && <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">∞</span>}
      </div>
      <div className="h-1 bg-white/[0.06] overflow-hidden">
        <div className={`h-full ${unlimited ? "bg-brand/40" : tone}`} style={{ width: unlimited ? "100%" : `${pct}%` }} />
      </div>
    </div>
  );
}

export default function Account() {
  const { user, refresh } = useAuth();
  const nav = useNavigate();

  const [snap, setSnap] = useState(null);
  const [loading, setLoading] = useState(true);

  // Profile
  const [name, setName] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  // Security
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  // Credits history + packs
  const [packs, setPacks] = useState([]);
  const [history, setHistory] = useState([]);
  // Plan switch
  const [planBusy, setPlanBusy] = useState(false);
  // Billing
  const [bill, setBill] = useState(null);
  const [bp, setBp] = useState({});
  const [countries, setCountries] = useState([]);
  // Notifications
  const [phoneE164, setPhoneE164] = useState("");
  const [slackUrl, setSlackUrl] = useState("");
  const [discordUrl, setDiscordUrl] = useState("");
  const [supportedEvents, setSupportedEvents] = useState([]);
  const [supportedChannels, setSupportedChannels] = useState([]);
  const [channelMatrix, setChannelMatrix] = useState({});
  const [testBusy, setTestBusy] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [s, p, h, b, c, n] = await Promise.all([
        api.get("/account"),
        api.get("/account/credits/packs"),
        api.get("/account/credits/history?limit=20"),
        api.get("/account/billing"),
        api.get("/billing/countries"),
        api.get("/notifications/prefs"),
      ]);
      setSnap(s.data);
      setName(s.data.profile?.name || "");
      setPacks(p.data || []);
      setHistory(h.data || []);
      setBill(b.data);
      setBp(b.data?.billing_profile || {});
      setCountries(c.data || []);
      const np = n.data || {};
      setPhoneE164(np.phone_e164 || "");
      setSlackUrl(np.slack_webhook_url || "");
      setDiscordUrl(np.discord_webhook_url || "");
      setSupportedEvents(np.supported_events || []);
      setSupportedChannels(np.supported_channels || ["sms", "whatsapp", "email"]);
      const channels = np.channels || {};
      const matrix = {};
      (np.supported_events || []).forEach((ev) => {
        const row = {};
        (np.supported_channels || []).forEach((c) => {
          row[c] = (channels[c] || []).includes(ev);
        });
        matrix[ev] = row;
      });
      setChannelMatrix(matrix);
    } catch (e) {
      toast.error(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  // ──────── Profile
  const saveProfile = async () => {
    setProfileBusy(true);
    try {
      await api.patch("/account/profile", { name: name.trim() });
      await refresh();
      toast.success("Profile saved");
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setProfileBusy(false); }
  };

  // ──────── Password
  const changePw = async (e) => {
    e.preventDefault();
    try {
      await api.post("/account/password", { current_password: currentPw, new_password: newPw });
      setCurrentPw(""); setNewPw("");
      toast.success("Password updated");
    } catch (err) { toast.error(getApiErrorMessage(err)); }
  };

  // ──────── Plan switch
  const switchPlan = async (planId) => {
    setPlanBusy(true);
    try {
      const r = await api.post("/account/plan/checkout", { plan: planId });
      if (r.data?.checkout_url) {
        window.location.href = r.data.checkout_url;
        return;
      }
      toast.success(`Switched to ${planId}`);
      await load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setPlanBusy(false); }
  };
  const cancelPlan = async () => {
    if (!window.confirm("Cancel your subscription? You'll drop back to Free immediately.")) return;
    setPlanBusy(true);
    try {
      await api.post("/account/plan/cancel");
      toast.success("Subscription canceled");
      await load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setPlanBusy(false); }
  };

  // ──────── Credits
  const buyPack = async (packId) => {
    try {
      const r = await api.post("/account/credits/checkout", { pack: packId });
      if (r.data?.checkout_url) window.location.href = r.data.checkout_url;
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };

  // ──────── Billing profile
  const saveBillingProfile = async () => {
    try {
      const r = await api.put("/account/billing/profile", {
        company_name: bp.company_name || "",
        address: bp.address || "",
        postal_code: bp.postal_code || "",
        city: bp.city || "",
        country: bp.country || "",
        email: bp.email || user?.email || "",
        vat_id: bp.vat_id || null,
        is_business: !!bp.is_business,
      });
      toast.success(`Billing profile saved · ${r.data?.vat_note || ""}`);
      await load();
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };

  // ──────── Notifications
  const toggleEventChannel = (ev, ch) => {
    setChannelMatrix((m) => ({ ...m, [ev]: { ...(m[ev] || {}), [ch]: !(m[ev] || {})[ch] } }));
  };
  const savePrefs = async () => {
    const channels = {};
    supportedChannels.forEach((c) => { channels[c] = []; });
    Object.entries(channelMatrix).forEach(([ev, ch]) => {
      supportedChannels.forEach((c) => { if (ch?.[c]) channels[c].push(ev); });
    });
    try {
      await api.put("/notifications/prefs", {
        phone_e164: phoneE164.trim() || null,
        slack_webhook_url: slackUrl.trim() || null,
        discord_webhook_url: discordUrl.trim() || null,
        channels,
      });
      toast.success("Notification preferences saved");
    } catch (e) { toast.error(getApiErrorMessage(e)); }
  };
  const sendTest = async (channel) => {
    // Reuse first owned workspace for test send (Mollie/twilio needs ws context for credits)
    const wsId = snap?.workspaces?.[0]?.id;
    if (!wsId) { toast.error("Create a Workspace first"); return; }
    setTestBusy(channel);
    try {
      const r = await api.post("/notifications/test", { workspace_id: wsId, channel });
      const result = (r.data?.results || [])[0];
      if (!result) toast.error(`No "deploy_succeeded" toggled on for ${channel} — flip it on first`);
      else if (result.status === "sent") toast.success(`Test ${channel} sent (cost: ${result.cost} cr)`);
      else if (result.status === "skipped") toast.error(`Skipped — ${result.error || "channel not ready"}`);
      else if (result.status === "insufficient_credits") toast.error("Top up your credits first");
      else toast.error(`Test ${channel} ${result.status}: ${result.error || ""}`);
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setTestBusy(null); }
  };

  if (loading || !snap) {
    return <div className="px-6 py-10 text-sm font-mono text-zinc-500" data-testid="account-loading">Loading account…</div>;
  }

  const plan = snap.plan;
  const usage = snap.usage || {};
  const credits = snap.credits || {};
  const limits = plan.limits || {};
  const isPaid = plan.id !== "free" && plan.id !== "hobby";
  const planRank = { free: 0, hobby: 0, pro: 1, agency: 2 };
  const currentRank = planRank[plan.id] ?? 0;

  return (
    <div className="px-4 py-5 sm:px-6 sm:py-6 max-w-6xl" data-testid="account-page">
      {/* Hero */}
      <div className="mb-6">
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// account</div>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <h1 className="font-display text-2xl sm:text-4xl font-semibold tracking-tighter break-words">
            {user?.name || user?.email}
          </h1>
          <div className="flex items-center gap-2 text-xs font-mono text-zinc-500 flex-wrap">
            <span className="px-2 py-1 border border-brand/40 text-brand uppercase tracking-wider">{plan.name}</span>
            <span>•</span>
            <span>{snap.workspaces.length} Workspace{snap.workspaces.length === 1 ? "" : "s"}</span>
            <span>•</span>
            <span className="text-brand">{credits.balance} credits</span>
          </div>
        </div>
        <p className="text-xs text-zinc-500 mt-2 max-w-2xl">
          One plan, one wallet, one inbox for notifications — applied across <strong>every Workspace you own</strong>. Workspace-specific settings (name, members, delete) live under <a href="/app/settings" className="text-brand hover:underline">Workspace settings</a>.
        </p>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Section nav */}
        <aside className="hidden lg:block col-span-3 sticky top-20 self-start" data-testid="account-section-nav">
          <nav className="border border-white/[0.06]">
            {SECTIONS.map((s) => (
              <a
                key={s.id}
                href={`#${s.id}`}
                className="flex items-center gap-2 px-4 py-2.5 text-sm border-b border-white/[0.06] last:border-b-0 text-zinc-400 hover:text-white hover:bg-white/[0.03]"
                data-testid={`account-nav-${s.id}`}
              >
                <s.icon className="h-4 w-4" />
                {s.label}
              </a>
            ))}
          </nav>
        </aside>

        <div className="col-span-12 lg:col-span-9 space-y-10">
          {/* Profile */}
          <section className="border border-white/[0.06] p-6 space-y-4" data-testid="section-profile">
            <SectionHeader id="profile" icon={UserIcon} title="Profile" subtitle="How you show up across DeployUnit." />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Email</label>
                <div className="mt-1 font-mono text-sm py-2">{user?.email}</div>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Display name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                  data-testid="account-name-input"
                />
              </div>
            </div>
            <div>
              <button
                onClick={saveProfile}
                disabled={profileBusy || name === user?.name}
                className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-40"
                data-testid="account-profile-save"
              >
                <Save className="h-4 w-4" /> Save
              </button>
            </div>

            {/* GitHub linkage */}
            <div className="pt-4 border-t border-white/[0.06]">
              <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2">Connected accounts</div>
              <div className="bg-elevated/30 border border-white/[0.06] p-4">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <div className="flex items-center gap-3">
                    <Github className="h-5 w-5" />
                    <div>
                      <div className="text-sm font-medium flex items-center gap-2">
                        GitHub
                        {user?.github_login && <CheckCircle2 className="h-4 w-4 text-signal-live" />}
                      </div>
                      <div className="text-xs font-mono text-zinc-500">
                        {user?.github_login ? `Connected as @${user.github_login}` : "Not connected — link to deploy your repos."}
                      </div>
                    </div>
                  </div>
                  <div className="min-w-[220px]">
                    {user?.github_login ? (
                      <button
                        onClick={async () => {
                          if (!window.confirm("Disconnect GitHub from this account?")) return;
                          await api.post("/auth/github/disconnect");
                          await refresh();
                        }}
                        className="w-full inline-flex items-center justify-center gap-2 py-2 border border-signal-failed/40 text-signal-failed hover:bg-signal-failed/10"
                        data-testid="account-github-disconnect"
                      >
                        <Trash2 className="h-4 w-4" /> Disconnect
                      </button>
                    ) : (
                      <GitHubButton link label="Connect GitHub" testId="account-connect-github" />
                    )}
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Plan + Usage */}
          <section className="border border-white/[0.06] p-6 space-y-5" data-testid="section-plan">
            <SectionHeader id="plan" icon={Sparkles} title="Plan & usage" subtitle="Your plan applies across every Workspace you own. Limits are pooled." />

            {/* Current plan card */}
            <div className="bg-elevated/30 border border-white/[0.06] p-5 grid grid-cols-12 gap-4">
              <div className="col-span-12 md:col-span-4">
                <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Current plan</div>
                <div className="mt-1 font-display text-3xl tracking-tight">{plan.name}</div>
                <div className="text-sm text-zinc-400">€{plan.price}/mo</div>
                <div className="text-[11px] font-mono text-zinc-500 mt-2">{plan.tagline}</div>
                {isPaid && (
                  <button
                    onClick={cancelPlan}
                    disabled={planBusy}
                    className="mt-4 text-xs text-signal-failed hover:underline disabled:opacity-50"
                    data-testid="account-plan-cancel"
                  >
                    Cancel subscription
                  </button>
                )}
              </div>
              <div className="col-span-12 md:col-span-8 grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-1">Apps</div>
                  <UsageBar used={usage.apps || 0} cap={limits.apps} />
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-1">Domains</div>
                  <UsageBar used={usage.domains || 0} cap={limits.domains} />
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-1">Workspaces</div>
                  <UsageBar used={usage.workspaces || snap.workspaces?.length || 1} cap={limits.workspaces} />
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-1">Projects</div>
                  <div className="font-display text-lg text-zinc-300">{usage.projects ?? "—"}</div>
                </div>
              </div>
            </div>

            {/* Plan options grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {(snap.available_plans || ["free", "pro", "agency"]).map ? null : null}
            </div>
            <PlanGrid currentPlanId={plan.id} currentRank={currentRank} planRank={planRank} onSelect={switchPlan} disabled={planBusy} />
          </section>

          {/* Credits */}
          <section className="border border-white/[0.06] p-6 space-y-5" data-testid="section-credits">
            <SectionHeader id="credits" icon={Wallet} title="Credits wallet"
              subtitle="Used for SMS, WhatsApp alerts, build overages. Shared across Workspaces. Free email + in-app alerts." />

            <div className="bg-elevated/30 border border-white/[0.06] p-5 grid grid-cols-12 gap-4">
              <div className="col-span-12 md:col-span-6">
                <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Balance</div>
                <div className="mt-1 font-display text-5xl tracking-tight text-brand">{credits.balance}</div>
                <div className="text-xs font-mono text-zinc-500">
                  ≈ €{(credits.balance * 0.1).toFixed(2)} worth
                </div>
                {credits.monthly_grant > 0 && (
                  <div className="text-xs font-mono text-zinc-500 mt-1">
                    +{credits.monthly_grant} granted each {plan.interval} (lifetime: {credits.granted_total})
                  </div>
                )}
              </div>
              <div className="col-span-12 md:col-span-6 grid grid-cols-1 sm:grid-cols-3 gap-2">
                {packs.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => buyPack(p.id)}
                    className="text-left bg-background border border-white/10 hover:border-brand/50 p-3 transition-colors"
                    data-testid={`pack-${p.id}`}
                  >
                    <div className="font-display text-base">{p.label}</div>
                    <div className="text-xs font-mono text-zinc-500">{p.credits} cr · €{p.price_eur}</div>
                    {p.bonus_pct && <div className="text-[10px] font-mono text-brand mt-1">+{p.bonus_pct}% bonus</div>}
                  </button>
                ))}
              </div>
            </div>

            {/* Recent transactions */}
            <div>
              <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2">Recent activity</div>
              {history.length === 0 ? (
                <div className="text-xs font-mono text-zinc-600 py-3">No transactions yet.</div>
              ) : (
                <div className="border border-white/[0.06] divide-y divide-white/[0.06]">
                  {history.map((t) => (
                    <div key={t.id} className="grid grid-cols-12 gap-3 px-3 py-2 text-xs font-mono items-center" data-testid={`txn-${t.id}`}>
                      <div className="col-span-3 text-zinc-500">{(t.created_at || "").slice(0, 19).replace("T", " ")}</div>
                      <div className="col-span-2"><span className={`px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${t.type === "consume" ? "bg-signal-failed/15 text-signal-failed" : t.type === "topup" ? "bg-signal-live/15 text-signal-live" : "bg-brand/15 text-brand"}`}>{t.type || t.kind}</span></div>
                      <div className="col-span-5 truncate text-zinc-300">{t.reason}</div>
                      <div className="col-span-2 text-right text-zinc-200">
                        {t.type === "consume" ? "-" : "+"}{Math.abs(t.amount || t.delta || 0)} <span className="text-zinc-500">→ {t.balance_after}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Billing */}
          <section className="border border-white/[0.06] p-6 space-y-5" data-testid="section-billing">
            <SectionHeader id="billing" icon={Receipt} title="Billing & invoices"
              subtitle="Used for plan checkout, credit packs, and EU VAT-compliant PDF invoices." />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field label="Company name" v={bp.company_name} on={(v) => setBp({ ...bp, company_name: v })} testId="bp-company" />
              <Field label="Email for invoices" v={bp.email || user?.email} on={(v) => setBp({ ...bp, email: v })} testId="bp-email" />
              <Field label="Address" v={bp.address} on={(v) => setBp({ ...bp, address: v })} testId="bp-address" />
              <Field label="Postal code" v={bp.postal_code} on={(v) => setBp({ ...bp, postal_code: v })} testId="bp-postal" />
              <Field label="City" v={bp.city} on={(v) => setBp({ ...bp, city: v })} testId="bp-city" />
              <div>
                <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Country</label>
                <select
                  value={bp.country || ""}
                  onChange={(e) => setBp({ ...bp, country: e.target.value })}
                  className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                  data-testid="bp-country"
                >
                  <option value="" className="bg-black">— Select —</option>
                  {countries.map((c) => (<option key={c.code} value={c.code} className="bg-black">{c.name} {c.eu ? `· VAT ${c.vat_rate}%` : ""}</option>))}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm md:col-span-2 mt-1">
                <input type="checkbox" checked={!!bp.is_business} onChange={(e) => setBp({ ...bp, is_business: e.target.checked })} data-testid="bp-business" />
                I'm purchasing as a business (will show VAT line on invoice)
              </label>
              {bp.is_business && (
                <Field label="VAT ID (EU only, e.g. NL123456789B01)" v={bp.vat_id} on={(v) => setBp({ ...bp, vat_id: v })} testId="bp-vat" />
              )}
            </div>
            <div>
              <button onClick={saveBillingProfile} className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90" data-testid="bp-save">
                <Save className="h-4 w-4" /> Save billing profile
              </button>
              {bp.vat_note && <span className="ml-3 text-xs font-mono text-zinc-500">{bp.vat_note}</span>}
            </div>

            {/* Invoices */}
            <div>
              <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2 mt-4">Invoices</div>
              {(!bill?.invoices || bill.invoices.length === 0) ? (
                <div className="text-xs font-mono text-zinc-600 py-3">No invoices yet. Pick a paid plan to start.</div>
              ) : (
                <div className="border border-white/[0.06] divide-y divide-white/[0.06]">
                  {bill.invoices.map((inv) => (
                    <div key={inv.invoice_number} className="grid grid-cols-12 gap-3 px-3 py-2 items-center" data-testid={`inv-${inv.invoice_number}`}>
                      <div className="col-span-3 font-mono text-xs text-zinc-300">{inv.invoice_number}</div>
                      <div className="col-span-3 font-mono text-xs text-zinc-500">{(inv.invoice_date || "").slice(0, 10)}</div>
                      <div className="col-span-3 text-sm">€{inv.total?.toFixed(2)} <span className="text-[10px] text-zinc-500 font-mono">incl VAT</span></div>
                      <div className="col-span-3 text-right">
                        <a className="text-xs text-brand hover:underline inline-flex items-center gap-1" href={inv.pdf_url} target="_blank" rel="noreferrer">PDF <ExternalLink className="h-3 w-3" /></a>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Notifications */}
          <section className="border border-white/[0.06] p-6 space-y-5" data-testid="section-notifications">
            <SectionHeader id="notifications" icon={Bell} title="Notification preferences"
              subtitle="Where DeployUnit pings you when things break. SMS & WhatsApp use credits; email & in-app are free." />

            <Field label="Phone (E.164, e.g. +32475123456)" v={phoneE164} on={setPhoneE164} testId="notif-phone" />

            <div className="border border-white/[0.06] overflow-x-auto">
              <div className="grid text-[10px] uppercase tracking-[0.25em] font-mono text-zinc-500 border-b border-white/[0.06]"
                   style={{ gridTemplateColumns: `minmax(180px,1fr) repeat(${supportedChannels.length}, 72px)` }}>
                <div className="p-3">Event</div>
                {supportedChannels.map((c) => {
                  const Icon = CHANNEL_META[c]?.icon || Mail;
                  return (
                    <div key={c} className="p-3 text-center flex flex-col items-center gap-1">
                      <Icon className="h-3 w-3" /> {CHANNEL_META[c]?.label || c}
                    </div>
                  );
                })}
              </div>
              {supportedEvents.map((ev) => (
                <div key={ev} className="grid border-b border-white/[0.06] last:border-b-0 items-center"
                     style={{ gridTemplateColumns: `minmax(180px,1fr) repeat(${supportedChannels.length}, 72px)` }}
                     data-testid={`notif-row-${ev}`}>
                  <div className="p-3">
                    <div className="text-sm">{EVENT_LABELS[ev] || ev}</div>
                    <div className="text-[10px] font-mono text-zinc-600">{ev}</div>
                  </div>
                  {supportedChannels.map((c) => {
                    const on = !!channelMatrix[ev]?.[c];
                    return (
                      <div key={c} className="p-3 flex justify-center">
                        <button
                          type="button"
                          onClick={() => toggleEventChannel(ev, c)}
                          className={`h-6 w-11 relative rounded-full transition-colors ${on ? "bg-brand" : "bg-white/[0.08] hover:bg-white/[0.14]"}`}
                          data-testid={`notif-toggle-${ev}-${c}`}
                          aria-pressed={on}
                        >
                          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-black transition-all ${on ? "left-[22px]" : "left-0.5"}`} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Field label="Slack webhook URL" v={slackUrl} on={setSlackUrl} placeholder="https://hooks.slack.com/services/..." testId="notif-slack" />
              <Field label="Discord webhook URL" v={discordUrl} on={setDiscordUrl} placeholder="https://discord.com/api/webhooks/..." testId="notif-discord" />
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <button onClick={savePrefs} className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90" data-testid="notif-save">
                <Save className="h-4 w-4" /> Save preferences
              </button>
              {["sms", "whatsapp", "slack", "discord"].map((c) => (
                <button
                  key={c}
                  onClick={() => sendTest(c)}
                  disabled={testBusy === c}
                  className="inline-flex items-center gap-1.5 px-3 py-2 border border-white/10 text-sm font-mono hover:border-brand/50 disabled:opacity-40"
                  data-testid={`notif-test-${c}`}
                >
                  <Send className="h-3 w-3" /> {testBusy === c ? "sending…" : `Test ${c}`}
                </button>
              ))}
            </div>
          </section>

          {/* Security */}
          <section className="border border-white/[0.06] p-6 space-y-4" data-testid="section-security">
            <SectionHeader id="security" icon={ShieldCheck} title="Security" subtitle="Change your password. Sessions reset on the next request." />
            <form onSubmit={changePw} className="space-y-3 max-w-md">
              <input
                type="password" required value={currentPw} onChange={(e) => setCurrentPw(e.target.value)}
                placeholder="current password"
                className="w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                data-testid="account-current-pw"
              />
              <input
                type="password" required minLength={8} value={newPw} onChange={(e) => setNewPw(e.target.value)}
                placeholder="new password (min 8)"
                className="w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                data-testid="account-new-pw"
              />
              <button type="submit" className="px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90" data-testid="account-pw-save">
                Update password
              </button>
            </form>
          </section>
        </div>
      </div>
    </div>
  );
}

function Field({ label, v, on, testId, placeholder }) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">{label}</label>
      <input
        value={v || ""}
        onChange={(e) => on(e.target.value)}
        placeholder={placeholder || ""}
        className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
        data-testid={testId}
      />
    </div>
  );
}

function PlanGrid({ currentPlanId, currentRank, planRank, onSelect, disabled }) {
  const [plans, setPlans] = useState([]);
  useEffect(() => {
    api.get("/billing/plans").then((r) => setPlans(r.data || [])).catch(() => setPlans([]));
  }, []);
  if (!plans.length) return null;
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="account-plan-grid">
      {plans.map((p) => {
        const isCurrent = p.id === currentPlanId;
        const rank = planRank[p.id] ?? 0;
        const isUpgrade = rank > currentRank;
        const isDowngrade = rank < currentRank;
        return (
          <div
            key={p.id}
            className={`border p-4 flex flex-col ${isCurrent ? "border-brand bg-brand/[0.04]" : "border-white/[0.06] hover:border-white/20"} transition-colors`}
            data-testid={`plan-card-${p.id}`}
          >
            <div className="flex items-center justify-between mb-1">
              <div className="font-display text-lg">{p.name}</div>
              {isCurrent && <span className="text-[10px] font-mono uppercase tracking-wider text-brand">Current</span>}
            </div>
            <div className="text-xs font-mono text-zinc-500 mb-3">€{p.price}/{p.interval}</div>
            <ul className="text-xs text-zinc-400 space-y-1 mb-4 flex-1">
              {(p.features || []).slice(0, 5).map((f) => (
                <li key={f} className="flex gap-1.5"><span className="text-brand">›</span> {f}</li>
              ))}
            </ul>
            <button
              onClick={() => onSelect(p.id)}
              disabled={isCurrent || disabled}
              className={`w-full inline-flex items-center justify-center gap-2 py-2 text-sm font-medium ${
                isCurrent ? "bg-white/5 text-zinc-500 cursor-default"
                  : isUpgrade ? "bg-brand text-brand-fg hover:bg-brand/90"
                  : "border border-white/10 text-zinc-400 hover:text-white hover:border-white/30"
              }`}
              data-testid={`plan-select-${p.id}`}
            >
              {isCurrent ? "Active" : isUpgrade ? <>Upgrade <ArrowRight className="h-3 w-3" /></> : isDowngrade ? "Switch down" : "Switch"}
            </button>
          </div>
        );
      })}
    </div>
  );
}

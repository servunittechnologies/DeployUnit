import { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import {
  ShieldCheck, Database, Globe, CheckCircle2, XCircle, AlertCircle,
  Loader2, Save, Copy, RefreshCw, Key, Users, Banknote, Github,
  Coins, Star,
} from "lucide-react";
import { toast } from "sonner";

const TABS = [
  { id: "integrations", label: "Integrations", icon: Database },
  { id: "plans", label: "Plans & Pricing", icon: Coins },
  { id: "platform", label: "Platform Domain", icon: Globe },
  { id: "vat", label: "VAT / VIES", icon: Banknote },
  { id: "users", label: "Users", icon: Users },
];

function StatusPill({ ok, label }) {
  if (ok === true) return <span className="inline-flex items-center gap-1.5 text-signal-live text-xs font-mono"><CheckCircle2 className="h-3.5 w-3.5" /> {label || "connected"}</span>;
  if (ok === false) return <span className="inline-flex items-center gap-1.5 text-signal-failed text-xs font-mono"><XCircle className="h-3.5 w-3.5" /> {label || "not configured"}</span>;
  return <span className="inline-flex items-center gap-1.5 text-zinc-500 text-xs font-mono"><AlertCircle className="h-3.5 w-3.5" /> {label || "unknown"}</span>;
}

function Field({ label, hint, children }) {
  return (
    <label className="block">
      <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 font-mono mb-1.5">{label}</div>
      {children}
      {hint && <div className="mt-1 text-xs text-zinc-500 font-mono">{hint}</div>}
    </label>
  );
}

function Input(props) {
  return (
    <input
      {...props}
      className={`w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand focus:ring-1 focus:ring-brand/60 focus:outline-none transition-colors ${props.className || ""}`}
    />
  );
}

function Section({ title, description, children }) {
  return (
    <div className="border border-white/[0.06] p-6 bg-[#0a0a0a]">
      <div className="mb-5">
        <h3 className="font-display text-lg tracking-tight">{title}</h3>
        {description && <p className="mt-1 text-sm text-zinc-400">{description}</p>}
      </div>
      {children}
    </div>
  );
}

/* ─────────────────────────── Integrations ─────────────────────────── */
function IntegrationsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/integrations");
      setData(r.data);
    } catch (e) {
      toast.error("Failed to load integrations");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  if (loading) return <div className="flex items-center gap-2 text-zinc-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading integrations…</div>;
  if (!data) return null;

  return (
    <div className="space-y-4" data-testid="admin-integrations">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono uppercase tracking-[0.35em] text-zinc-500">// live integration status</div>
        <button onClick={load} className="text-xs font-mono text-zinc-400 hover:text-brand inline-flex items-center gap-1.5"><RefreshCw className="h-3.5 w-3.5" /> refresh</button>
      </div>

      <Section
        title="Coolify (deployment engine)"
        description="Where all your apps are built & hosted."
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm font-mono">
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">status</div>
            {data.coolify.configured ? (
              data.coolify?.health?.ok ? (
                <StatusPill ok={true} label="connected" />
              ) : (
                <span className="inline-flex items-center gap-1.5 text-signal-queued text-xs font-mono" data-testid="admin-coolify-unreachable">
                  <AlertCircle className="h-3.5 w-3.5" /> configured, unreachable from backend
                </span>
              )
            ) : (
              <StatusPill ok={false} label="not configured" />
            )}
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">endpoint</div>
            <div className="text-zinc-300 truncate" data-testid="admin-coolify-url">{data.coolify.base_url || "—"}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">version</div>
            <div className="text-zinc-300">{data.coolify?.health?.version || "—"}</div>
          </div>
        </div>
        {data.coolify.configured && !data.coolify?.health?.ok && (
          <div className="mt-3 text-[11px] font-mono text-zinc-500 leading-relaxed">
            Credentials are saved, but DeployHub's backend couldn't reach <span className="text-zinc-300">{data.coolify.base_url}</span> right now.
            Check firewall rules, server uptime, or network routing. Deployments will queue until reachable.
            {data.coolify?.health?.error && <span className="text-signal-failed"> · {data.coolify.health.error}</span>}
          </div>
        )}
      </Section>

      <Section
        title="Mollie (payments)"
        description="Handles subscriptions, EU VAT calculation + payments."
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm font-mono">
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">status</div>
            <StatusPill ok={data.mollie.configured} label={data.mollie.configured ? "live" : "not configured"} />
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">mode</div>
            <div className="text-zinc-300 capitalize">{data.mollie.mode || "—"}</div>
          </div>
        </div>
      </Section>

      <Section
        title="GitHub OAuth"
        description="Used for login + repo browsing + automatic deploy keys."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm font-mono">
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">status</div>
            <StatusPill ok={data.github_oauth.configured} />
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">client id</div>
            <div className="text-zinc-300 truncate">{data.github_oauth.client_id || "—"}</div>
          </div>
          <div className="md:col-span-2">
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">callback url (paste into GitHub OAuth app)</div>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-black border border-white/10 px-3 py-2 text-xs text-brand truncate">{data.github_oauth.callback_url || "—"}</code>
              <button
                onClick={() => { navigator.clipboard.writeText(data.github_oauth.callback_url || ""); toast.success("Copied"); }}
                className="px-2.5 py-2 border border-white/10 hover:border-brand/70 hover:text-brand transition-colors"
                data-testid="admin-copy-callback"
              ><Copy className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        </div>
      </Section>

      <Section
        title="Twilio (SMS + WhatsApp)"
        description="Used to send customer notification alerts (billed from each workspace's credit wallet)."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm font-mono">
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">status</div>
            <StatusPill ok={data.twilio?.configured} label={data.twilio?.configured ? "connected" : "not configured — add credentials below in Platform Domain → Twilio"} />
          </div>
        </div>
      </Section>

      <Section title="Company tax" description="VAT rates follow this home country for domestic billing.">
        <div className="text-sm font-mono">
          <span className="text-zinc-500">home country: </span>
          <span className="text-zinc-200">{data.company_country}</span>
          <span className="text-zinc-500 ml-6">eu countries covered: </span>
          <span className="text-zinc-200">{data.eu_vat_countries}</span>
        </div>
      </Section>
    </div>
  );
}

/* ─────────────────────── Plans & Pricing ─────────────────────── */
function PlanRow({ plan, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    price: plan.price,
    tagline: plan.tagline || "",
    credits: plan.credits ?? 0,
    apps: plan.limits?.apps ?? 0,
    domains: plan.limits?.domains ?? 0,
    team: plan.limits?.team ?? 0,
    bandwidth_gb: plan.limits?.bandwidth_gb ?? 0,
    build_minutes: plan.limits?.build_minutes ?? 0,
    highlight: plan.highlight,
    active: plan.active,
    fleet_view: plan.fleet_view,
  });
  const [saving, setSaving] = useState(false);
  const [usage, setUsage] = useState(null);

  useEffect(() => {
    api.get(`/admin/plans/${plan.id}/usage`).then((r) => setUsage(r.data)).catch(() => null);
  }, [plan.id]);

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        price: parseFloat(form.price),
        tagline: form.tagline,
        credits: parseInt(form.credits, 10),
        highlight: form.highlight,
        active: form.active,
        fleet_view: form.fleet_view,
        limits: {
          apps: parseInt(form.apps, 10),
          domains: parseInt(form.domains, 10),
          team: parseInt(form.team, 10),
          bandwidth_gb: parseInt(form.bandwidth_gb, 10),
          build_minutes: parseInt(form.build_minutes, 10),
        },
      };
      await api.put(`/admin/plans/${plan.id}`, payload);
      toast.success(`${plan.name} updated`);
      setEditing(false);
      onSaved?.();
    } catch (e) {
      toast.error("Save failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setSaving(false);
    }
  };

  const fmtLimit = (v) => (v === -1 || v === null ? "∞" : v);

  return (
    <div className={`border border-white/[0.08] ${plan.highlight ? "ring-1 ring-brand/40" : ""} bg-[#0a0a0a]`} data-testid={`admin-plan-${plan.id}`}>
      <div className="p-5 flex items-center justify-between border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <span className={`px-2 py-0.5 text-[10px] uppercase tracking-[0.3em] ${plan.active ? "border border-signal-live/40 text-signal-live" : "border border-white/10 text-zinc-500"}`}>
            {plan.active ? "active" : "hidden"}
          </span>
          <h4 className="font-display text-lg tracking-tight">{plan.name}</h4>
          {plan.highlight && <Star className="h-4 w-4 text-brand fill-brand" />}
          <span className="font-display text-2xl">€{plan.price.toFixed(0)}</span>
          <span className="text-xs text-zinc-500 font-mono">/{plan.interval}</span>
        </div>
        <div className="flex items-center gap-3">
          {usage && (
            <span className="text-xs font-mono text-zinc-500" data-testid={`admin-plan-usage-${plan.id}`}>
              {usage.workspaces} workspace{usage.workspaces === 1 ? "" : "s"}
            </span>
          )}
          {!editing ? (
            <button onClick={() => setEditing(true)} className="text-xs font-mono text-brand hover:underline" data-testid={`admin-plan-edit-${plan.id}`}>edit</button>
          ) : (
            <>
              <button onClick={() => setEditing(false)} disabled={saving} className="text-xs font-mono text-zinc-500 hover:underline">cancel</button>
              <button onClick={save} disabled={saving} className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-mono bg-brand text-brand-fg hover:bg-brand/90 disabled:opacity-50" data-testid={`admin-plan-save-${plan.id}`}>
                {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} save
              </button>
            </>
          )}
        </div>
      </div>

      <div className="p-5">
        {editing ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              ["Price (€)", "price", "number"],
              ["Credits/mo", "credits", "number"],
              ["Apps cap (-1=∞)", "apps", "number"],
              ["Domains (-1=∞)", "domains", "number"],
              ["Team (-1=∞)", "team", "number"],
              ["Bandwidth (GB)", "bandwidth_gb", "number"],
              ["Build minutes", "build_minutes", "number"],
            ].map(([label, k, type]) => (
              <Field key={k} label={label}>
                <Input
                  type={type}
                  value={form[k]}
                  onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                  data-testid={`admin-plan-${plan.id}-${k}`}
                />
              </Field>
            ))}
            <Field label="Tagline">
              <Input value={form.tagline} onChange={(e) => setForm({ ...form, tagline: e.target.value })} />
            </Field>
            <div className="col-span-2 md:col-span-4 flex items-center gap-6 pt-2 text-sm font-mono">
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.highlight} onChange={(e) => setForm({ ...form, highlight: e.target.checked })} /> recommended
              </label>
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} /> active (shown on pricing page)
              </label>
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.fleet_view} onChange={(e) => setForm({ ...form, fleet_view: e.target.checked })} /> Fleet view feature
              </label>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm font-mono">
            {[
              ["apps", fmtLimit(plan.limits?.apps)],
              ["domains", fmtLimit(plan.limits?.domains)],
              ["team", fmtLimit(plan.limits?.team)],
              ["bandwidth", `${plan.limits?.bandwidth_gb ?? "—"} GB`],
              ["build min", plan.limits?.build_minutes ?? "—"],
              ["credits/mo", plan.credits ?? 0],
              ["fleet view", plan.fleet_view ? "✓" : "—"],
              ["sla", plan.support_sla_hours ? `${plan.support_sla_hours}h` : "community"],
            ].map(([k, v]) => (
              <div key={k}>
                <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500">{k}</div>
                <div className="text-zinc-200 mt-1">{v}</div>
              </div>
            ))}
            {plan.tagline && (
              <div className="col-span-2 md:col-span-4 text-zinc-400 text-xs italic">"{plan.tagline}"</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function PlansTab() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/plans");
      setPlans(r.data);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  if (loading) return <div className="flex items-center gap-2 text-zinc-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading plans…</div>;

  return (
    <div className="space-y-4" data-testid="admin-plans">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono uppercase tracking-[0.35em] text-zinc-500">// edit pricing, limits, credits — affects pricing page immediately</div>
        <button onClick={load} className="text-xs font-mono text-zinc-400 hover:text-brand inline-flex items-center gap-1.5">
          <RefreshCw className="h-3.5 w-3.5" /> refresh
        </button>
      </div>
      {plans.map((p) => (
        <PlanRow key={p.id} plan={p} onSaved={load} />
      ))}
    </div>
  );
}

/* ─────────────────────── Platform Domain + Cloudflare ─────────────────────── */
function PlatformTab() {
  // Test sender component declared inline so it can reach api directly
  const MailerSendTester = ({ from_email_set, api_key_set }) => {
    const [to, setTo] = useState("");
    const [busy, setBusy] = useState(false);
    const send = async () => {
      if (!to.includes("@")) { toast.error("Enter a valid email"); return; }
      setBusy(true);
      try {
        const r = await api.post("/admin/mailersend/test", { to_email: to });
        if (r.data.ok) toast.success(`Sent! Check ${to} (message id: ${r.data.message_id || "n/a"})`);
        else toast.error(`Send failed: ${r.data.error || r.data.status}`);
      } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
      finally { setBusy(false); }
    };
    return (
      <div className="mt-4 pt-4 border-t border-white/[0.04]">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2">Diagnostic test send</div>
        <div className="flex items-center gap-2 flex-wrap">
          <input
            type="email"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="your@email.com"
            className="flex-1 min-w-[260px] bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="admin-mailersend-test-email"
          />
          <button
            onClick={send}
            disabled={busy || !from_email_set || !api_key_set}
            className="px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-40 text-sm"
            data-testid="admin-mailersend-test-send"
          >
            {busy ? "Sending…" : "Send test"}
          </button>
        </div>
        {(!from_email_set || !api_key_set) && (
          <div className="text-[10px] font-mono text-zinc-600 mt-2">Save the API key and a verified from-email first.</div>
        )}
      </div>
    );
  };

  const [s, setS] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    cloudflare_api_token: "",
    cloudflare_zone_id: "",
    cloudflare_zone_name: "",
    default_subdomain_target_ip: "",
    default_subdomain_target_host: "",
    company_country: "",
    company_name: "",
    company_address: "",
    company_postcode: "",
    company_city: "",
    company_vat_id: "",
    // Twilio (SMS + WhatsApp). Auth token stored Fernet-encrypted server-side.
    twilio_account_sid: "",
    twilio_auth_token: "",
    twilio_messaging_service_sid: "",
    twilio_from_number: "",
    twilio_whatsapp_from: "",
    twilio_status_callback: "",
    twilio_test_mode: false,
    // MailerSend
    mailersend_api_key: "",
    mailersend_from_email: "",
    mailersend_from_name: "",
    mailersend_reply_to: "",
  });

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/platform-settings");
      setS(r.data);
      setForm((f) => ({
        ...f,
        cloudflare_api_token: "",
        cloudflare_zone_id: r.data.cloudflare_zone_id || "",
        cloudflare_zone_name: r.data.cloudflare_zone_name || "",
        default_subdomain_target_ip: r.data.default_subdomain_target_ip || "",
        default_subdomain_target_host: r.data.default_subdomain_target_host || "",
        company_country: r.data.company_country || "",
        company_name: r.data.company_name || "",
        company_address: r.data.company_address || "",
        company_postcode: r.data.company_postcode || "",
        company_city: r.data.company_city || "",
        company_vat_id: r.data.company_vat_id || "",
        twilio_account_sid: r.data.twilio_account_sid || "",
        twilio_auth_token: "", // never round-trip; backend redacts
        twilio_messaging_service_sid: r.data.twilio_messaging_service_sid || "",
        twilio_from_number: r.data.twilio_from_number || "",
        twilio_whatsapp_from: r.data.twilio_whatsapp_from || "",
        twilio_status_callback: r.data.twilio_status_callback || "",
        twilio_test_mode: !!r.data.twilio_test_mode,
        mailersend_api_key: "",
        mailersend_from_email: r.data.mailersend_from_email || "",
        mailersend_from_name: r.data.mailersend_from_name || "",
        mailersend_reply_to: r.data.mailersend_reply_to || "",
      }));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      const payload = {};
      Object.entries(form).forEach(([k, v]) => {
        // Only send tokens if user typed a new value (avoid clearing by empty string)
        if ((k === "cloudflare_api_token" || k === "twilio_auth_token" || k === "mailersend_api_key") && v === "") return;
        payload[k] = v;
      });
      const r = await api.put("/admin/platform-settings", payload);
      setS(r.data);
      setForm((f) => ({ ...f, cloudflare_api_token: "", twilio_auth_token: "", mailersend_api_key: "" }));
      toast.success("Platform settings saved");
    } catch (e) {
      toast.error("Save failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setSaving(false);
    }
  };

  if (loading || !s) return <div className="flex items-center gap-2 text-zinc-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>;

  return (
    <div className="space-y-4" data-testid="admin-platform">
      <Section
        title="Company identity (invoices + VAT)"
        description="These details appear on every invoice and drive VAT logic. Home country determines domestic rate vs EU reverse-charge."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Field label="Company name">
            <Input
              value={form.company_name}
              onChange={(e) => setForm({ ...form, company_name: e.target.value })}
              placeholder="ServUnit BV"
              data-testid="admin-company-name"
            />
          </Field>
          <Field label="Home country (ISO-2)" hint="e.g. NL, BE, DE — drives VAT logic">
            <Input
              value={form.company_country}
              onChange={(e) => setForm({ ...form, company_country: e.target.value.toUpperCase() })}
              placeholder="BE"
              maxLength={2}
              data-testid="admin-company-country"
            />
          </Field>
          <Field label="Street address">
            <Input
              value={form.company_address}
              onChange={(e) => setForm({ ...form, company_address: e.target.value })}
              placeholder="Hemelshoek 235"
              data-testid="admin-company-address"
            />
          </Field>
          <Field label="Postcode + city">
            <div className="grid grid-cols-3 gap-2">
              <Input
                className="col-span-1"
                value={form.company_postcode}
                onChange={(e) => setForm({ ...form, company_postcode: e.target.value })}
                placeholder="2590"
                data-testid="admin-company-postcode"
              />
              <Input
                className="col-span-2"
                value={form.company_city}
                onChange={(e) => setForm({ ...form, company_city: e.target.value })}
                placeholder="Berlaar"
                data-testid="admin-company-city"
              />
            </div>
          </Field>
          <Field label="VAT ID" hint="Used for reverse-charge B2B">
            <Input
              value={form.company_vat_id}
              onChange={(e) => setForm({ ...form, company_vat_id: e.target.value })}
              placeholder="BE0779674221"
              data-testid="admin-company-vat-id"
            />
          </Field>
        </div>
      </Section>

      <Section
        title="Default subdomain (Cloudflare)"
        description="Every new app automatically gets a subdomain like {slug}.yourzone.app. DeployHub creates the DNS A-record via Cloudflare on your behalf."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Field label="Root domain (must be in Cloudflare)" hint="e.g. deployhub.app">
            <Input
              value={form.cloudflare_zone_name}
              onChange={(e) => setForm({ ...form, cloudflare_zone_name: e.target.value })}
              placeholder="deployhub.app"
              data-testid="admin-cf-zone-name"
            />
          </Field>
          <Field label="Cloudflare Zone ID" hint="Find in Cloudflare dashboard → Overview → right sidebar">
            <Input
              value={form.cloudflare_zone_id}
              onChange={(e) => setForm({ ...form, cloudflare_zone_id: e.target.value })}
              placeholder="0123456789abcdef0123456789abcdef"
              data-testid="admin-cf-zone-id"
            />
          </Field>
          <Field label="Cloudflare API Token" hint={s.cloudflare_api_token_set ? "A token is already saved. Leave blank to keep it." : "Create one in Cloudflare → My Profile → API Tokens with Zone.DNS:Edit scope."}>
            <Input
              type="password"
              value={form.cloudflare_api_token}
              onChange={(e) => setForm({ ...form, cloudflare_api_token: e.target.value })}
              placeholder={s.cloudflare_api_token_set ? "•••••••• (saved)" : "paste token here"}
              data-testid="admin-cf-token"
            />
          </Field>
          <Field label="Deploy target IP (A record)" hint="Your Coolify server IP">
            <Input
              value={form.default_subdomain_target_ip}
              onChange={(e) => setForm({ ...form, default_subdomain_target_ip: e.target.value })}
              placeholder="149.12.246.205"
              data-testid="admin-target-ip"
            />
          </Field>
          <Field label="Deploy target hostname (optional, CNAME)" hint="Used instead of IP when set — good for HA setups">
            <Input
              value={form.default_subdomain_target_host}
              onChange={(e) => setForm({ ...form, default_subdomain_target_host: e.target.value })}
              placeholder="server-1.deployhub.internal"
              data-testid="admin-target-host"
            />
          </Field>
        </div>
      </Section>

      <Section
        title="Twilio (SMS + WhatsApp alerts)"
        description="Used to send customer notifications (billed from credit wallet). Get credentials at twilio.com → Console → Account."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Field label="Account SID" hint="Find in Twilio Console → Account → API keys & tokens">
            <Input
              value={form.twilio_account_sid}
              onChange={(e) => setForm({ ...form, twilio_account_sid: e.target.value })}
              placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              data-testid="admin-twilio-sid"
            />
          </Field>
          <Field label="Auth Token" hint={s.twilio_auth_token_set ? "A token is already saved. Leave blank to keep it." : "Same page as Account SID in Twilio Console."}>
            <Input
              type="password"
              value={form.twilio_auth_token}
              onChange={(e) => setForm({ ...form, twilio_auth_token: e.target.value })}
              placeholder={s.twilio_auth_token_set ? "•••••••• (saved)" : "paste token here"}
              data-testid="admin-twilio-token"
            />
          </Field>
          <Field label="From phone (E.164)" hint="Twilio number for SMS, e.g. +14155551234. Required if no Messaging Service SID.">
            <Input
              value={form.twilio_from_number}
              onChange={(e) => setForm({ ...form, twilio_from_number: e.target.value })}
              placeholder="+14155551234"
              data-testid="admin-twilio-from"
            />
          </Field>
          <Field label="Messaging Service SID (optional)" hint="If you use Twilio Messaging Services for routing. Leave blank to use From phone.">
            <Input
              value={form.twilio_messaging_service_sid}
              onChange={(e) => setForm({ ...form, twilio_messaging_service_sid: e.target.value })}
              placeholder="MGxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              data-testid="admin-twilio-msg-service"
            />
          </Field>
          <Field label="WhatsApp sender" hint="Approved WhatsApp Business sender, e.g. whatsapp:+14155238886">
            <Input
              value={form.twilio_whatsapp_from}
              onChange={(e) => setForm({ ...form, twilio_whatsapp_from: e.target.value })}
              placeholder="whatsapp:+14155238886"
              data-testid="admin-twilio-whatsapp-from"
            />
          </Field>
          <Field label="Status callback URL (optional)" hint="Webhook for delivery receipts. Defaults to /api/notifications/twilio/status.">
            <Input
              value={form.twilio_status_callback}
              onChange={(e) => setForm({ ...form, twilio_status_callback: e.target.value })}
              placeholder="https://yourapp.com/api/notifications/twilio/status"
              data-testid="admin-twilio-callback"
            />
          </Field>
          <div className="md:col-span-2 flex items-center gap-2 pt-1">
            <input
              id="twilio_test_mode"
              type="checkbox"
              checked={form.twilio_test_mode}
              onChange={(e) => setForm({ ...form, twilio_test_mode: e.target.checked })}
              data-testid="admin-twilio-test-mode"
            />
            <label htmlFor="twilio_test_mode" className="text-xs font-mono text-zinc-400 cursor-pointer">
              Test mode (use Twilio test credentials — no real messages sent, no charges)
            </label>
          </div>
        </div>
      </Section>

      <Section
        title="MailerSend (transactional email)"
        description="Welcome emails, password resets, notification alerts. Get an API key at mailersend.com → Domains → API tokens (Email permission). The from-email must be on a domain you've verified in MailerSend."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Field label="API token" hint={s.mailersend_api_key_set ? "A token is already saved. Leave blank to keep it." : "MailerSend → Email → API tokens → Create new token with 'Email' permission."}>
            <Input
              type="password"
              value={form.mailersend_api_key}
              onChange={(e) => setForm({ ...form, mailersend_api_key: e.target.value })}
              placeholder={s.mailersend_api_key_set ? "•••••••• (saved)" : "mlsn.xxxxxxxxxxxxxxxxxxxxxxx"}
              data-testid="admin-mailersend-token"
            />
          </Field>
          <Field label="From email" hint="Must be an address on a domain you've verified in MailerSend (DKIM + Return-Path DNS records added).">
            <Input
              value={form.mailersend_from_email}
              onChange={(e) => setForm({ ...form, mailersend_from_email: e.target.value })}
              placeholder="hello@yourdomain.com"
              data-testid="admin-mailersend-from"
            />
          </Field>
          <Field label="From name" hint="Display name in the inbox. Default 'DeployHub' if blank.">
            <Input
              value={form.mailersend_from_name}
              onChange={(e) => setForm({ ...form, mailersend_from_name: e.target.value })}
              placeholder="DeployHub"
              data-testid="admin-mailersend-from-name"
            />
          </Field>
          <Field label="Reply-To (optional)" hint="Email replies will land here instead of your noreply address.">
            <Input
              value={form.mailersend_reply_to}
              onChange={(e) => setForm({ ...form, mailersend_reply_to: e.target.value })}
              placeholder="support@yourdomain.com"
              data-testid="admin-mailersend-reply"
            />
          </Field>
        </div>
        <MailerSendTester from_email_set={!!form.mailersend_from_email} api_key_set={!!s.mailersend_api_key_set || !!form.mailersend_api_key} />
      </Section>

      <div className="flex justify-end">
        <button
          onClick={save}
          disabled={saving}
          className="magnetic-btn inline-flex items-center gap-2 px-5 py-2.5 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50 transition"
          data-testid="admin-save-platform"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save platform settings
        </button>
      </div>
    </div>
  );
}

/* ─────────────────────────── VAT ─────────────────────────── */
function VatTab() {
  const [vat, setVat] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const test = async () => {
    if (!vat.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const r = await api.post("/admin/vat/test", { vat_id: vat.trim() });
      setResult(r.data);
    } catch (e) {
      setResult({ valid: false, error: e?.response?.data?.detail || e.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="admin-vat">
      <Section
        title="VIES validator"
        description="Test any EU VAT number against the official European Commission VIES SOAP service. Used at checkout to decide reverse-charge B2B billing."
      >
        <div className="flex gap-2">
          <Input
            placeholder="BE0779674221"
            value={vat}
            onChange={(e) => setVat(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && test()}
            data-testid="admin-vat-input"
          />
          <button
            onClick={test}
            disabled={loading || !vat.trim()}
            className="magnetic-btn inline-flex items-center gap-2 px-5 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50 whitespace-nowrap"
            data-testid="admin-vat-submit"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            Validate
          </button>
        </div>
        {result && (
          <div className={`mt-4 p-4 border ${result.valid ? "border-signal-live/30 bg-signal-live/5" : "border-signal-failed/30 bg-signal-failed/5"}`} data-testid="admin-vat-result">
            <div className="flex items-center gap-2 font-mono text-sm">
              {result.valid ? <CheckCircle2 className="h-4 w-4 text-signal-live" /> : <XCircle className="h-4 w-4 text-signal-failed" />}
              <span className={result.valid ? "text-signal-live" : "text-signal-failed"}>
                {result.valid ? "VALID" : "INVALID"}
              </span>
              {result.error && <span className="text-zinc-500 ml-2">({result.error})</span>}
            </div>
            {result.name && (
              <div className="mt-3 text-sm font-mono">
                <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500">name</div>
                <div className="text-zinc-200">{result.name}</div>
              </div>
            )}
            {result.address && (
              <div className="mt-3 text-sm font-mono">
                <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500">address</div>
                <div className="text-zinc-200 whitespace-pre-line">{result.address}</div>
              </div>
            )}
          </div>
        )}
      </Section>

      <Section title="How VAT is calculated" description="Summary of the rules applied at checkout.">
        <ul className="text-sm space-y-2 font-mono text-zinc-300">
          <li>→ Same country as company: <span className="text-brand">home VAT</span> (e.g. NL = 21%)</li>
          <li>→ EU B2B with verified VAT ID: <span className="text-brand">0% reverse-charge</span></li>
          <li>→ EU B2C: <span className="text-brand">destination country rate</span> (OSS/MOSS)</li>
          <li>→ Non-EU: <span className="text-brand">0%</span></li>
        </ul>
      </Section>
    </div>
  );
}

/* ─────────────────────────── Users ─────────────────────────── */
function UsersTab() {
  const [data, setData] = useState({ users: [], total: 0 });
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [detailUser, setDetailUser] = useState(null); // {id, email}

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/users", { params: { q: q || undefined, limit: 50, offset } });
      setData(r.data);
    } finally { setLoading(false); }
  }, [q, offset]);
  useEffect(() => { load(); }, [load]);

  if (detailUser) {
    return <UserDetailPanel userId={detailUser.id} onBack={() => { setDetailUser(null); load(); }} />;
  }

  return (
    <Section title={`Users (${data.total})`} description="Search, promote, suspend, adjust credits, change plans — everything per user.">
      <div className="flex items-center gap-2 mb-4">
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setOffset(0); }}
          placeholder="search email / name / github…"
          className="flex-1 bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
          data-testid="admin-users-search"
        />
        <button onClick={load} className="px-3 py-2 border border-white/10 hover:border-brand/50 text-xs font-mono">
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      <div className="border border-white/[0.06]">
        <div className="grid grid-cols-[1fr_120px_90px_90px_90px] gap-4 px-4 py-2 border-b border-white/[0.06] text-[10px] uppercase tracking-[0.25em] font-mono text-zinc-500">
          <div>Email / name</div><div>Role</div><div>Workspaces</div><div>Credits</div><div className="text-right">Open</div>
        </div>
        {data.users.length === 0 && !loading && (
          <div className="p-6 text-sm font-mono text-zinc-500">No users found.</div>
        )}
        {data.users.map((u) => (
          <div key={u.id} className="grid grid-cols-[1fr_120px_90px_90px_90px] gap-4 px-4 py-3 text-sm border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02]" data-testid={`admin-user-row-${u.id}`}>
            <div className="truncate">
              <div className="text-zinc-200 truncate">{u.email}</div>
              <div className="text-[11px] font-mono text-zinc-500 truncate">
                {u.name}{u.github_login ? ` · @${u.github_login}` : ""}
                {u.is_active === false ? " · suspended" : ""}
              </div>
            </div>
            <div>
              <span className={`px-2 py-0.5 text-[10px] uppercase tracking-[0.3em] font-mono ${u.role === "admin" ? "border border-brand/40 text-brand" : "border border-white/10 text-zinc-400"}`}>
                {u.role}
              </span>
            </div>
            <div className="text-xs font-mono text-zinc-300">{u.workspaces_count}</div>
            <div className="text-xs font-mono text-zinc-300">{u.credits_total}</div>
            <div className="text-right">
              <button onClick={() => setDetailUser({ id: u.id, email: u.email })} className="text-xs text-brand hover:underline" data-testid={`admin-user-open-${u.id}`}>open →</button>
            </div>
          </div>
        ))}
      </div>

      {data.total > 50 && (
        <div className="flex items-center justify-between mt-4 text-xs font-mono text-zinc-500">
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))} className="px-3 py-1.5 border border-white/10 hover:border-brand/50 disabled:opacity-40">← previous</button>
          <div>{offset + 1}–{Math.min(offset + 50, data.total)} of {data.total}</div>
          <button disabled={offset + 50 >= data.total} onClick={() => setOffset(offset + 50)} className="px-3 py-1.5 border border-white/10 hover:border-brand/50 disabled:opacity-40">next →</button>
        </div>
      )}
    </Section>
  );
}

/* ─────────────────────── User detail panel ─────────────────────── */
function UserDetailPanel({ userId, onBack }) {
  const [data, setData] = useState(null);
  const [payments, setPayments] = useState(null);
  const [busy, setBusy] = useState("");
  const [pwdNew, setPwdNew] = useState("");

  const load = useCallback(async () => {
    const r = await api.get(`/admin/users/${userId}`);
    setData(r.data);
    const rp = await api.get(`/admin/users/${userId}/payments`);
    setPayments(rp.data);
  }, [userId]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <div className="text-sm font-mono text-zinc-500">Loading user…</div>;
  const u = data.user;

  const setPassword = async () => {
    if (pwdNew.length < 8) { toast.error("Min 8 characters"); return; }
    setBusy("pwd");
    try {
      await api.post(`/admin/users/${userId}/password`, { new_password: pwdNew });
      toast.success(`Password updated for ${u.email}. They must sign in again.`);
      setPwdNew("");
    } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
    finally { setBusy(""); }
  };

  const toggleRole = async () => {
    const newRole = u.role === "admin" ? "user" : "admin";
    if (!window.confirm(`Change ${u.email} to ${newRole}?`)) return;
    setBusy("role");
    try {
      await api.post(`/admin/users/${userId}/role`, { role: newRole });
      toast.success(`Now ${newRole}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
    finally { setBusy(""); }
  };

  const toggleSuspend = async () => {
    const becoming = u.is_active === false ? "active" : "suspended";
    if (!window.confirm(`Mark ${u.email} as ${becoming}?`)) return;
    setBusy("suspend");
    try {
      await api.post(`/admin/users/${userId}/suspend`);
      toast.success(`Now ${becoming}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
    finally { setBusy(""); }
  };

  const hardDelete = async () => {
    if (!window.confirm(`PERMANENTLY DELETE ${u.email}? This cannot be undone. Type their email in the next prompt to confirm.`)) return;
    const confirm = window.prompt("Type the email to confirm:");
    if (confirm !== u.email) { toast.error("Email did not match"); return; }
    setBusy("delete");
    try {
      await api.delete(`/admin/users/${userId}`);
      toast.success("User deleted");
      onBack();
    } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
    finally { setBusy(""); }
  };

  const adjustCredits = async (workspaceId, delta) => {
    const reason = window.prompt(`Reason for ${delta > 0 ? "granting" : "revoking"} ${Math.abs(delta)} credits:`, "Manual support adjustment");
    if (reason === null) return;
    try {
      const r = await api.post(`/admin/users/${userId}/credits`, { workspace_id: workspaceId, delta, reason });
      toast.success(`New balance: ${r.data.balance} cr`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
  };

  const setPlan = async (workspaceId, plan) => {
    if (!window.confirm(`Switch this workspace to ${plan}?`)) return;
    try {
      await api.post(`/admin/users/${userId}/plan`, { workspace_id: workspaceId, plan });
      toast.success(`Plan: ${plan}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || e.message); }
  };

  return (
    <div className="space-y-6" data-testid="admin-user-detail">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-brand" data-testid="admin-user-back">
          ← back to users
        </button>
        <div className="flex items-center gap-2">
          <button onClick={toggleRole} disabled={busy === "role"} className="px-3 py-1.5 text-xs font-mono border border-white/10 hover:border-brand/50">
            {u.role === "admin" ? "Demote to user" : "Promote to admin"}
          </button>
          <button onClick={toggleSuspend} disabled={busy === "suspend"} className="px-3 py-1.5 text-xs font-mono border border-signal-queued/40 text-signal-queued hover:bg-signal-queued/10">
            {u.is_active === false ? "Unsuspend" : "Suspend"}
          </button>
          <button onClick={hardDelete} disabled={busy === "delete"} className="px-3 py-1.5 text-xs font-mono border border-signal-failed/40 text-signal-failed hover:bg-signal-failed/10">
            Delete user
          </button>
        </div>
      </div>

      {/* Profile */}
      <div className="border border-white/[0.06] p-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Email</div>
            <div className="text-base mt-1">{u.email}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Name</div>
            <div className="text-base mt-1">{u.name || "—"}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Role / Status</div>
            <div className="text-base mt-1">
              {u.role} · <span className={u.is_active === false ? "text-signal-failed" : "text-signal-live"}>{u.is_active === false ? "suspended" : "active"}</span>
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">GitHub</div>
            <div className="text-base mt-1">{u.github_login ? `@${u.github_login}` : "—"}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Created</div>
            <div className="text-base mt-1 font-mono">{u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Last password reset</div>
            <div className="text-base mt-1 font-mono">{u.password_updated_at ? new Date(u.password_updated_at).toLocaleDateString() : "—"}</div>
          </div>
        </div>

        {/* Password reset */}
        <div className="mt-6 pt-6 border-t border-white/[0.04]">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500 mb-2">Set new password</div>
          <div className="flex items-center gap-2 max-w-md">
            <input
              type="password"
              value={pwdNew}
              onChange={(e) => setPwdNew(e.target.value)}
              placeholder="min 8 characters"
              className="flex-1 bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
              data-testid="admin-user-new-password"
            />
            <button onClick={setPassword} disabled={busy === "pwd" || pwdNew.length < 8} className="px-4 py-2 bg-brand text-brand-fg font-medium disabled:opacity-40 text-sm" data-testid="admin-user-password-save">
              Save
            </button>
          </div>
        </div>
      </div>

      {/* Workspaces */}
      <div className="border border-white/[0.06] p-5 space-y-4">
        <h3 className="font-display text-lg">Workspaces ({data.workspaces.length})</h3>
        {data.workspaces.length === 0 && <div className="text-xs font-mono text-zinc-500">User owns no workspaces.</div>}
        {data.workspaces.map((w) => (
          <div key={w.id} className="border border-white/[0.06] p-4" data-testid={`admin-ws-${w.id}`}>
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <div className="text-sm font-medium">{w.name}</div>
                <div className="text-[11px] font-mono text-zinc-500 mt-0.5">{w.type} · {w.apps_count} apps · {w.payments_count} payments</div>
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <div className="text-xs font-mono text-zinc-400">
                  Plan: <span className="text-zinc-200">{w.plan_details?.name || w.plan}</span> · €{w.plan_details?.price || 0}/mo
                </div>
                <select
                  value={w.plan || "free"}
                  onChange={(e) => setPlan(w.id, e.target.value)}
                  className="bg-black border border-white/10 px-2 py-1 text-xs font-mono focus:border-brand outline-none"
                  data-testid={`admin-ws-plan-${w.id}`}
                >
                  {data.available_plans.map((p) => <option key={p.id} value={p.id} className="bg-black">{p.name} (€{p.price})</option>)}
                </select>
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-white/[0.04] flex items-center justify-between gap-4 flex-wrap">
              <div className="text-sm">
                Credits balance: <span className="text-brand font-mono">{w.credits_balance || 0} cr</span>
              </div>
              <div className="flex items-center gap-1.5">
                {[100, 500, 1000].map((n) => (
                  <button key={n} onClick={() => adjustCredits(w.id, n)} className="px-2.5 py-1 text-xs font-mono border border-signal-live/30 text-signal-live hover:bg-signal-live/10" data-testid={`admin-ws-grant-${w.id}-${n}`}>
                    +{n}
                  </button>
                ))}
                <button onClick={() => {
                  const v = window.prompt("Custom credit delta (negative to revoke):", "100");
                  const n = parseInt(v || "0", 10);
                  if (n) adjustCredits(w.id, n);
                }} className="px-2.5 py-1 text-xs font-mono border border-white/10 hover:border-brand/50">±custom</button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Payments + invoices */}
      <div className="border border-white/[0.06] p-5 space-y-4">
        <h3 className="font-display text-lg">Payments & invoices</h3>
        {!payments ? <div className="text-xs font-mono text-zinc-500">Loading…</div> : (
          <>
            <div className="text-xs font-mono text-zinc-500">
              Total paid: <span className="text-brand">€{payments.totals.paid_eur}</span> · {payments.totals.payments} payments · {payments.totals.invoices} invoices
            </div>
            {payments.workspaces.map((w) => (
              <div key={w.workspace.id} className="border border-white/[0.04] p-4">
                <div className="text-sm font-medium">{w.workspace.name}</div>
                <div className="text-[11px] font-mono text-zinc-500 mt-0.5 mb-3">€{w.paid_eur} paid total</div>
                {w.payments.length === 0 && <div className="text-[11px] font-mono text-zinc-600">No payments yet.</div>}
                {w.payments.length > 0 && (
                  <div className="border border-white/[0.04]">
                    <div className="grid grid-cols-[110px_1fr_90px_90px_140px] gap-2 px-3 py-1.5 text-[10px] uppercase tracking-[0.25em] font-mono text-zinc-500 border-b border-white/[0.04]">
                      <div>Date</div><div>Transaction ID</div><div>Plan</div><div>Status</div><div className="text-right">Amount</div>
                    </div>
                    {w.payments.slice(0, 20).map((p) => (
                      <div key={p.id || p.mollie_payment_id} className="grid grid-cols-[110px_1fr_90px_90px_140px] gap-2 px-3 py-2 text-[11px] font-mono border-b border-white/[0.02] last:border-b-0">
                        <div className="text-zinc-500">{p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}</div>
                        <div className="text-brand truncate" title={p.mollie_payment_id || p.id}>{(p.mollie_payment_id || p.id || "—").slice(0, 28)}</div>
                        <div className="text-zinc-400">{p.plan || "—"}</div>
                        <div className={p.status === "paid" ? "text-signal-live" : p.status === "expired" || p.status === "failed" ? "text-signal-failed" : "text-zinc-500"}>{p.status}</div>
                        <div className="text-right text-zinc-200">€{(p.total ?? p.subtotal ?? 0).toFixed?.(2) ?? p.total ?? 0}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </>
        )}
      </div>

      {/* Recent audit on this user */}
      <div className="border border-white/[0.06] p-5">
        <h3 className="font-display text-lg mb-3">Recent activity ({data.audit.length})</h3>
        {data.audit.length === 0 && <div className="text-xs font-mono text-zinc-500">No activity logged.</div>}
        {data.audit.length > 0 && (
          <div className="border border-white/[0.04] divide-y divide-white/[0.02]">
            {data.audit.slice(0, 15).map((a) => (
              <div key={a.id} className="grid grid-cols-[180px_1fr] gap-3 px-3 py-2 text-[11px] font-mono">
                <div className="text-zinc-500">{new Date(a.created_at).toLocaleString()}</div>
                <div><span className="text-zinc-300">{a.action}</span>{a.resource_type ? <span className="text-zinc-500"> · {a.resource_type}</span> : null}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─────────────────────────── Admin shell ─────────────────────────── */
export default function Admin() {
  const [tab, setTab] = useState("integrations");

  return (
    <div className="p-8 max-w-5xl" data-testid="admin-page">
      <div className="flex items-center gap-3 mb-1">
        <ShieldCheck className="h-5 w-5 text-brand" />
        <h1 className="font-display text-3xl tracking-tighter">Admin Console</h1>
      </div>
      <p className="text-sm text-zinc-400 mb-8">Platform-wide configuration. Only visible to admins.</p>

      <div className="flex items-center gap-1 border-b border-white/[0.06] mb-6">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            data-testid={`admin-tab-${t.id}`}
            className={`relative inline-flex items-center gap-2 px-4 py-3 text-sm transition-colors ${
              tab === t.id ? "text-brand" : "text-zinc-400 hover:text-white"
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
            {tab === t.id && <span className="absolute inset-x-0 -bottom-px h-px bg-brand" />}
          </button>
        ))}
      </div>

      {tab === "integrations" && <IntegrationsTab />}
      {tab === "plans" && <PlansTab />}
      {tab === "platform" && <PlatformTab />}
      {tab === "vat" && <VatTab />}
      {tab === "users" && <UsersTab />}
    </div>
  );
}

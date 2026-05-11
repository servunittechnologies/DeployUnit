import { useEffect, useState } from "react";
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
            <StatusPill ok={data.coolify.configured && data.coolify?.health?.ok} label={data.coolify.configured ? (data.coolify?.health?.ok ? "healthy" : "unreachable") : "not configured"} />
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
        // Only send the token if user typed a new one (avoid clearing by empty string)
        if (k === "cloudflare_api_token" && v === "") return;
        payload[k] = v;
      });
      const r = await api.put("/admin/platform-settings", payload);
      setS(r.data);
      setForm((f) => ({ ...f, cloudflare_api_token: "" }));
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
          <Field label="Company country (for VAT)" hint="ISO 2-letter code, e.g. NL, BE">
            <Input
              value={form.company_country}
              onChange={(e) => setForm({ ...form, company_country: e.target.value.toUpperCase() })}
              placeholder="NL"
              maxLength={2}
              data-testid="admin-company-country"
            />
          </Field>
        </div>
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
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/users");
      setUsers(r.data);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const toggle = async (user) => {
    const newRole = user.role === "admin" ? "user" : "admin";
    try {
      await api.post("/admin/users/role", { user_id: user.id, role: newRole });
      toast.success(`${user.email} → ${newRole}`);
      load();
    } catch (e) {
      toast.error("Failed: " + (e?.response?.data?.detail || e.message));
    }
  };

  if (loading) return <div className="flex items-center gap-2 text-zinc-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading users…</div>;

  return (
    <Section title={`Users (${users.length})`} description="All DeployHub accounts. Promote or demote admins with one click.">
      <div className="border border-white/[0.06] divide-y divide-white/[0.06]" data-testid="admin-users-table">
        {users.map((u) => (
          <div key={u.id} className="grid grid-cols-12 gap-4 px-4 py-3 text-sm font-mono items-center">
            <div className="col-span-4 truncate text-zinc-200">{u.email}</div>
            <div className="col-span-3 truncate text-zinc-500">{u.name}</div>
            <div className="col-span-2">
              <span className={`px-2 py-0.5 text-[10px] uppercase tracking-[0.3em] ${u.role === "admin" ? "border border-brand/40 text-brand" : "border border-white/10 text-zinc-400"}`}>
                {u.role}
              </span>
            </div>
            <div className="col-span-2 text-xs text-zinc-500">
              {u.workspaces_owned} ws · {u.github_login ? <><Github className="inline h-3 w-3" /> {u.github_login}</> : "no github"}
            </div>
            <div className="col-span-1 text-right">
              <button
                onClick={() => toggle(u)}
                className="text-xs text-zinc-400 hover:text-brand underline"
                data-testid={`admin-toggle-role-${u.id}`}
              >
                {u.role === "admin" ? "demote" : "promote"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </Section>
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

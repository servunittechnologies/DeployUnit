import { useEffect, useState, useCallback } from "react";
import { api } from "../../lib/api";
import {
  ShieldCheck, Database, Globe, CheckCircle2, XCircle, AlertCircle,
  Loader2, Save, Copy, RefreshCw, Key, Users, Banknote, Github,
  Coins, Star, Cpu, LifeBuoy, ArrowLeft, Filter, Search as SearchIcon,
  Trash2, Plus, RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
import { TicketThread, StatusPill as TicketStatusPill } from "./Tickets";
import TabBar from "../../components/TabBar";

const TABS = [
  { id: "integrations", label: "Integrations", icon: Database },
  { id: "plans", label: "Plans & Pricing", icon: Coins },
  { id: "credit-packs", label: "Credit Packs", icon: Star },
  { id: "resources", label: "Resources & Limits", icon: Cpu },
  { id: "platform", label: "Platform Domain", icon: Globe },
  { id: "vat", label: "VAT / VIES", icon: Banknote },
  { id: "users", label: "Users", icon: Users },
  { id: "tickets", label: "Support tickets", icon: LifeBuoy },
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
        title="Build engine"
        description="Where all your apps are built & hosted."
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm font-mono">
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">status</div>
            {data.build_engine?.configured ? (
              data.build_engine?.health?.ok ? (
                <StatusPill ok={true} label="connected" />
              ) : (
                <span className="inline-flex items-center gap-1.5 text-signal-queued text-xs font-mono" data-testid="admin-build-engine-unreachable">
                  <AlertCircle className="h-3.5 w-3.5" /> configured, unreachable from backend
                </span>
              )
            ) : (
              <StatusPill ok={false} label="not configured" />
            )}
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">endpoint</div>
            <div className="text-zinc-300 truncate" data-testid="admin-build-engine-url">{data.build_engine?.base_url || "—"}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">version</div>
            <div className="text-zinc-300">{data.build_engine?.health?.version || "—"}</div>
          </div>
        </div>
        {data.build_engine?.configured && !data.build_engine?.health?.ok && (
          <div className="mt-3 text-[11px] font-mono text-zinc-500 leading-relaxed">
            Credentials are saved, but DeployUnit's backend couldn't reach <span className="text-zinc-300">{data.build_engine.base_url}</span> right now.
            Check firewall rules, server uptime, or network routing. Deployments will queue until reachable.
            {data.build_engine?.health?.error && <span className="text-signal-failed"> · {data.build_engine.health.error}</span>}
          </div>
        )}
      </Section>

      <MetricsAgentSection />

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
        title="SMSTools (EU SMS)"
        description="GDPR-compliant European SMS provider. Used for customer alert notifications, billed from each workspace's credit wallet."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm font-mono">
          <div>
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">status</div>
            <StatusPill ok={data.smstools?.configured} label={data.smstools?.configured ? "connected" : "not configured — add credentials below in Platform Domain → SMSTools"} />
            {data.smstools?.balance !== undefined && (
              <div className="mt-2 text-zinc-400 text-xs">Balance: <span className="text-zinc-200">€ {Number(data.smstools.balance).toFixed(2)}</span></div>
            )}
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
              ["Workspace (-1=∞)", "team", "number"],
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

/* ─────────────────────── Metrics agent ─────────────────────── */
function MetricsAgentSection() {
  const [info, setInfo] = useState(null);
  const [revealedKey, setRevealedKey] = useState(null);
  const [rotating, setRotating] = useState(false);

  const load = () => api.get("/admin/metrics/agent").then((r) => setInfo(r.data)).catch(() => setInfo(null));
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);

  const rotate = async () => {
    const verb = info?.configured ? "Rotate" : "Generate";
    if (!window.confirm(`${verb} agent key?\n\nAny installed agent will need to be reinstalled with the new key.`)) return;
    setRotating(true);
    try {
      const r = await api.post("/admin/metrics/agent/rotate");
      setRevealedKey(r.data.api_key);
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || e.message); }
    finally { setRotating(false); }
  };

  const copy = (text) => { navigator.clipboard.writeText(text); toast.success("Copied"); };

  if (!info) return null;
  const seenAgo = info.last_seen_at
    ? Math.max(0, Math.round((Date.now() - new Date(info.last_seen_at).getTime()) / 1000))
    : null;
  const live = seenAgo !== null && seenAgo < 120;

  return (
    <Section
      title="Metrics agent"
      description="Pushes container CPU/memory/disk/network stats from your build engine VPS so the analytics tabs show live + historical data."
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm font-mono mb-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">status</div>
          {!info.configured ? (
            <StatusPill ok={false} label="not configured" />
          ) : live ? (
            <StatusPill ok={true} label={`live · ${seenAgo}s ago`} />
          ) : info.last_seen_at ? (
            <span className="inline-flex items-center gap-1.5 text-signal-queued text-xs font-mono" data-testid="admin-agent-stale">
              <AlertCircle className="h-3.5 w-3.5" /> configured · last seen {Math.round(seenAgo / 60)} min ago
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-signal-queued text-xs font-mono" data-testid="admin-agent-pending">
              <AlertCircle className="h-3.5 w-3.5" /> configured · awaiting first sample
            </span>
          )}
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">last batch (accepted / skipped)</div>
          <div className="text-zinc-300" data-testid="admin-agent-batch">
            <span className="text-signal-success">{info.last_sample_count ?? 0}</span>
            <span className="text-zinc-600 mx-1">/</span>
            <span className={info.last_skipped_count > 0 ? "text-signal-queued" : "text-zinc-500"}>{info.last_skipped_count ?? 0}</span>
            <span className="text-zinc-600 ml-2 text-xs">of {info.last_seen_count ?? 0} seen</span>
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 mb-1">key issued</div>
          <div className="text-zinc-300">{info.created_at ? new Date(info.created_at).toLocaleString() : "—"}</div>
        </div>
      </div>

      {/* Unmanaged containers are silently dropped at ingest — no more
          nagging warnings. The reconcile job (every 10 min) imports any
          real build engine resources that should be tracked. Show a tiny
          informational pill only if there's a backlog to look at. */}
      {(info.unmanaged_coolify_count ?? 0) > 0 && (
        <div className="bg-black/30 border border-white/[0.06] px-3 py-2 mb-4 text-[11px] font-mono text-zinc-400 flex items-center gap-2" data-testid="admin-agent-unmanaged">
          <span className="h-1.5 w-1.5 rounded-full bg-brand" />
          {info.unmanaged_coolify_count} build engine resource{info.unmanaged_coolify_count === 1 ? "" : "s"} not yet imported to DeployUnit — they'll appear here on the next reconcile.
        </div>
      )}

      {revealedKey && (
        <div className="bg-brand/10 border border-brand/40 p-4 mb-4" data-testid="agent-key-revealed">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-brand mb-1">⚠ store this key NOW — shown once</div>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-black/40 px-3 py-2 text-xs font-mono break-all">{revealedKey}</code>
            <button onClick={() => copy(revealedKey)} className="px-3 py-2 border border-white/15 hover:border-brand text-xs font-mono"><Copy className="h-3 w-3 inline mr-1" /> copy</button>
          </div>
        </div>
      )}

      <div className="bg-elevated/30 border border-white/[0.06] p-4 space-y-3">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">// install on your build engine VPS</div>
        <div className="text-xs text-zinc-400">
          Run this once on the same VPS that hosts your build engine (Docker required). The script will pull and
          start a tiny agent container that reports container stats every 30s.
        </div>
        <div className="flex items-center gap-2">
          <code className="flex-1 bg-black/40 px-3 py-2 text-xs font-mono break-all" data-testid="agent-install-cmd">
            {info.install_command}
          </code>
          <button onClick={() => copy(info.install_command)} className="px-3 py-2 border border-white/15 hover:border-brand text-xs font-mono" data-testid="agent-install-copy">
            <Copy className="h-3 w-3 inline mr-1" /> copy
          </button>
        </div>
        <div className="text-[10px] font-mono text-zinc-500">
          During install you'll be prompted to paste the agent key (use the "Generate" button below if you don't have one yet).
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 mt-4">
        <button
          onClick={rotate}
          disabled={rotating}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-40"
          data-testid="agent-key-rotate"
        >
          <Key className="h-4 w-4" /> {info.configured ? "Rotate key" : "Generate key"}
        </button>
      </div>
    </Section>
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

/* ─────────────────────── Resources & Limits ─────────────────────── */
function ResourcesTab() {
  const [cfg, setCfg] = useState(null);
  const [defaults, setDefaults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [a, b] = await Promise.all([
        api.get("/admin/resource-config"),
        api.get("/admin/resource-defaults"),
      ]);
      setCfg(a.data);
      setDefaults(b.data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  if (loading || !cfg) return <div className="flex items-center gap-2 text-zinc-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>;

  const updatePlanDefault = (planId, key, value) => {
    setCfg({
      ...cfg,
      plan_defaults: {
        ...cfg.plan_defaults,
        [planId]: { ...cfg.plan_defaults[planId], [key]: Number(value) },
      },
    });
  };
  const updatePricing = (key, value) => {
    setCfg({ ...cfg, pricing: { ...cfg.pricing, [key]: Number(value) } });
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/admin/resource-config", {
        plan_defaults: cfg.plan_defaults,
        pricing: cfg.pricing,
      });
      toast.success("Resource config saved · applies to next deploy");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || e.message); }
    finally { setSaving(false); }
  };
  const revert = async () => {
    if (!window.confirm("Revert to built-in baseline values?")) return;
    setCfg(defaults);
  };

  return (
    <div className="space-y-8" data-testid="admin-resources">
      <Section title="Plan defaults" description="Each app on this plan starts with these resources for free. CPU in vCPU, memory + storage in MB.">
        <div className="border border-white/[0.06]">
          <div className="grid grid-cols-12 px-4 py-2 text-[10px] uppercase tracking-[0.35em] text-zinc-500 font-mono border-b border-white/[0.06]">
            <div className="col-span-3">Plan</div>
            <div className="col-span-3">CPU (vCPU)</div>
            <div className="col-span-3">Memory (MB)</div>
            <div className="col-span-3">Storage (MB)</div>
          </div>
          {Object.entries(cfg.plan_defaults).map(([planId, d]) => (
            <div key={planId} className="grid grid-cols-12 px-4 py-3 items-center border-b border-white/[0.04] last:border-b-0">
              <div className="col-span-3 font-display capitalize">{planId}</div>
              <div className="col-span-3 pr-3">
                <Input type="number" step="0.05" value={d.cpu_vcpu} onChange={(e) => updatePlanDefault(planId, "cpu_vcpu", e.target.value)} data-testid={`def-cpu-${planId}`} />
              </div>
              <div className="col-span-3 pr-3">
                <Input type="number" step="64" value={d.memory_mb} onChange={(e) => updatePlanDefault(planId, "memory_mb", e.target.value)} data-testid={`def-mem-${planId}`} />
              </div>
              <div className="col-span-3">
                <Input type="number" step="512" value={d.storage_mb} onChange={(e) => updatePlanDefault(planId, "storage_mb", e.target.value)} data-testid={`def-storage-${planId}`} />
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Addon pricing" description="Customers pay credits/month for resource upgrades on top of their plan default. Bigger unit sizes = simpler UX.">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-elevated/30 border border-white/[0.06] p-4 space-y-3">
            <div className="text-sm font-display flex items-center gap-2"><Cpu className="h-4 w-4 text-brand" /> CPU</div>
            <Field label="Unit size (vCPU)"><Input type="number" step="0.05" value={cfg.pricing.cpu_unit_vcpu} onChange={(e) => updatePricing("cpu_unit_vcpu", e.target.value)} data-testid="price-cpu-unit" /></Field>
            <Field label="Credits per unit/month"><Input type="number" step="1" value={cfg.pricing.cpu_credits_per_unit} onChange={(e) => updatePricing("cpu_credits_per_unit", e.target.value)} data-testid="price-cpu-cost" /></Field>
            <div className="text-[10px] font-mono text-zinc-500">≈ €{((cfg.pricing.cpu_credits_per_unit || 0) * 0.1).toFixed(2)} / +{cfg.pricing.cpu_unit_vcpu} vCPU / mo</div>
          </div>
          <div className="bg-elevated/30 border border-white/[0.06] p-4 space-y-3">
            <div className="text-sm font-display flex items-center gap-2"><Database className="h-4 w-4 text-brand" /> Memory</div>
            <Field label="Unit size (MB)"><Input type="number" step="64" value={cfg.pricing.memory_unit_mb} onChange={(e) => updatePricing("memory_unit_mb", e.target.value)} data-testid="price-mem-unit" /></Field>
            <Field label="Credits per unit/month"><Input type="number" step="1" value={cfg.pricing.memory_credits_per_unit} onChange={(e) => updatePricing("memory_credits_per_unit", e.target.value)} data-testid="price-mem-cost" /></Field>
            <div className="text-[10px] font-mono text-zinc-500">≈ €{((cfg.pricing.memory_credits_per_unit || 0) * 0.1).toFixed(2)} / +{cfg.pricing.memory_unit_mb} MB / mo</div>
          </div>
          <div className="bg-elevated/30 border border-white/[0.06] p-4 space-y-3">
            <div className="text-sm font-display flex items-center gap-2"><Database className="h-4 w-4 text-brand" /> Storage</div>
            <Field label="Unit size (MB)"><Input type="number" step="512" value={cfg.pricing.storage_unit_mb} onChange={(e) => updatePricing("storage_unit_mb", e.target.value)} data-testid="price-storage-unit" /></Field>
            <Field label="Credits per unit/month"><Input type="number" step="1" value={cfg.pricing.storage_credits_per_unit} onChange={(e) => updatePricing("storage_credits_per_unit", e.target.value)} data-testid="price-storage-cost" /></Field>
            <div className="text-[10px] font-mono text-zinc-500">≈ €{((cfg.pricing.storage_credits_per_unit || 0) * 0.1).toFixed(2)} / +{(cfg.pricing.storage_unit_mb || 0) >= 1024 ? `${cfg.pricing.storage_unit_mb / 1024} GB` : `${cfg.pricing.storage_unit_mb} MB`} / mo</div>
          </div>
        </div>
      </Section>

      <div className="flex items-center justify-end gap-2">
        <button onClick={revert} className="px-3 py-2 border border-white/15 text-zinc-300 hover:text-white text-sm font-mono uppercase tracking-wider" data-testid="resources-revert">
          Revert defaults
        </button>
        <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-40" data-testid="resources-save">
          <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </div>
  );
}


/* ──────────────────── SMSTools test-send mini-widget ──────────────────── */
function SenderIdValidator({ value }) {
  const v = (value || "").trim();
  if (!v) return (
    <div className="mt-1.5 text-[11px] font-mono text-amber-400/80" data-testid="sender-validator-empty">
      ⚠ Empty — SMSTools will reject the send with error 111. Set a brand name or your own phone number (digits only).
    </div>
  );
  const isDigits = /^[0-9]+$/.test(v);
  const isAlphanum = /^[a-zA-Z0-9]+$/.test(v);
  const digitsTooLong = isDigits && v.length > 14;
  const alphanumTooLong = isAlphanum && !isDigits && v.length > 11;
  const hasSpecials = !isAlphanum && !isDigits;

  if (hasSpecials) return (
    <div className="mt-1.5 text-[11px] font-mono text-rose-400" data-testid="sender-validator-bad">
      ✗ Contains special characters — only A–Z, a–z and 0–9 allowed. SMSTools will return error 111.
    </div>
  );
  if (alphanumTooLong) return (
    <div className="mt-1.5 text-[11px] font-mono text-rose-400" data-testid="sender-validator-too-long">
      ✗ Too long ({v.length} chars) — alphanumeric senders must be ≤11 chars.
    </div>
  );
  if (digitsTooLong) return (
    <div className="mt-1.5 text-[11px] font-mono text-rose-400" data-testid="sender-validator-digits-too-long">
      ✗ Too long ({v.length} digits) — numeric senders must be ≤14 digits.
    </div>
  );
  // Format is fine — but for EU we still need pre-registration warning.
  return (
    <div className="mt-1.5 text-[11px] font-mono text-emerald-400/90 leading-relaxed" data-testid="sender-validator-ok">
      ✓ Format is valid ({v.length} {isDigits ? "digits" : "alphanumeric chars"}).
      {!isDigits && (
        <span className="block text-amber-400/80 mt-0.5">
          ⚠ For EU carriers (NL, BE, DE, FR, …) you MUST pre-register this name in your SMSTools dashboard → <b>Sender names</b> → <b>Add sender</b>. Without approval, carriers return error 111.
        </span>
      )}
      {isDigits && (
        <span className="block text-zinc-500 mt-0.5">
          Numeric senders (your own GSM number, digits only) work without pre-registration — the safest option for first-time setup.
        </span>
      )}
    </div>
  );
}


function SMSToolsTestSend() {
  const [to, setTo] = useState("");
  const [sending, setSending] = useState(false);

  const send = async () => {
    if (!to.trim()) { toast.error("Enter a recipient (E.164 format, e.g. +32475123456)"); return; }
    setSending(true);
    try {
      const r = await api.post("/admin/smstools/test", { to: to.trim() });
      toast.success(`Sent ✓ message id: ${r.data.message_id || "—"}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mt-5 pt-5 border-t border-white/[0.04]">
      <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-3">Send test SMS</div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
        <Field label="Recipient (E.164)">
          <Input
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="+32475123456"
            data-testid="admin-smstools-test-to"
          />
        </Field>
        <div className="md:col-span-2 flex justify-end">
          <button
            onClick={send}
            disabled={sending}
            className="px-4 py-2 border border-brand text-brand hover:bg-brand/10 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium"
            data-testid="admin-smstools-test-send"
          >
            {sending ? "Sending…" : "Send test SMS"}
          </button>
        </div>
      </div>
      <div className="mt-2 text-[11px] font-mono text-zinc-500">
        Uses the platform's SMSTools balance directly — no workspace credits charged.
      </div>
    </div>
  );
}


/* ─────────────────────── Platform Domain + Cloudflare ─────────────────────── */
function SubdomainPoolWidget({ target, onTargetChange, proxied, onProxiedChange }) {
  const [stats, setStats] = useState(null);
  const [refilling, setRefilling] = useState(false);
  const [loading, setLoading] = useState(true);
  const [healing, setHealing] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const load = async () => {
    try {
      const r = await api.get("/admin/subdomain-pool");
      setStats(r.data);
    } catch (e) {
      console.warn("pool stats fail", e?.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);

  const refill = async () => {
    setRefilling(true);
    try {
      const r = await api.post("/admin/subdomain-pool/refill");
      setStats(r.data);
      if (r.data.added > 0) toast.success(`Pool refilled: +${r.data.added} new subdomain${r.data.added > 1 ? "s" : ""} ready`);
      else if (!r.data.cloudflare_ready) toast.error("Cloudflare not configured — save the token + zone + target IP first.");
      else toast.message("Pool is already at target — no refill needed.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    } finally {
      setRefilling(false);
    }
  };

  const runHealer = async () => {
    setHealing(true);
    try {
      const r = await api.post("/admin/routing-healer/run");
      const checked = r.data?.checked ?? 0;
      const healed = r.data?.healed ?? 0;
      const orphans = r.data?.orphans?.released ?? 0;
      if (healed > 0 || orphans > 0) {
        toast.success(`Healer fixed ${healed} app${healed === 1 ? "" : "s"}${orphans > 0 ? ` · released ${orphans} orphan DNS record${orphans === 1 ? "" : "s"}` : ""}`);
      } else if (checked === 0) {
        toast.message("No live apps with managed FQDNs to check.");
      } else {
        toast.success(`All ${checked} app${checked === 1 ? "" : "s"} routing OK — nothing to fix.`);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    } finally {
      setHealing(false);
    }
  };

  const syncProxied = async () => {
    setSyncing(true);
    try {
      const r = await api.post("/admin/subdomain-pool/sync-proxied");
      if (r.data?.error) {
        toast.error(r.data.error);
      } else {
        const tgt = r.data.target ? "orange cloud (proxied)" : "grey cloud (DNS only)";
        toast.success(`Synced ${r.data.updated}/${r.data.total} DNS record${r.data.total === 1 ? "" : "s"} to ${tgt}${r.data.failed > 0 ? ` · ${r.data.failed} failed` : ""}`);
        setStats((r.data.pool) || stats);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    } finally {
      setSyncing(false);
    }
  };

  const free = stats?.free ?? 0;
  const claimed = stats?.claimed ?? 0;
  const tgt = stats?.target ?? target ?? 10;
  const fillPct = tgt > 0 ? Math.min(100, Math.round((free / tgt) * 100)) : 0;
  const healthColor = !stats?.cloudflare_ready ? "text-zinc-500" : free >= tgt ? "text-emerald-400" : free > 0 ? "text-amber-400" : "text-rose-400";
  const healthLabel = !stats?.cloudflare_ready ? "Cloudflare not configured" : free >= tgt ? "Full — instant URLs ready" : free > 0 ? "Partially filled" : "Empty — next deploy will create on-demand";
  const unsynced = stats?.proxied_unsynced ?? 0;

  return (
    <Section
      title="Instant URL pool (pre-warmed Cloudflare DNS)"
      description="Holds a stash of pre-created DNS records so every new app gets a fully-propagated URL the moment it's deployed — no DNS waiting."
    >
      <div className="space-y-5" data-testid="admin-subdomain-pool">
        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="border border-white/[0.06] bg-black/40 p-4">
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Free / target</div>
            <div className="text-2xl font-mono font-medium mt-1 tabular-nums" data-testid="pool-free-count">
              <span className={healthColor}>{loading ? "…" : free}</span>
              <span className="text-zinc-600 text-lg"> / {tgt}</span>
            </div>
            <div className="mt-3 h-1 bg-white/5 overflow-hidden">
              <div className={`h-full ${free >= tgt ? "bg-emerald-500/70" : free > 0 ? "bg-amber-500/70" : "bg-rose-500/40"}`} style={{ width: `${fillPct}%` }} />
            </div>
          </div>
          <div className="border border-white/[0.06] bg-black/40 p-4">
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Claimed</div>
            <div className="text-2xl font-mono font-medium mt-1 tabular-nums">{loading ? "…" : claimed}</div>
            <div className="text-[10px] font-mono text-zinc-600 mt-1">live apps holding a pooled URL</div>
          </div>
          <div className="border border-white/[0.06] bg-black/40 p-4 col-span-2 md:col-span-2">
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Health</div>
            <div className={`text-base font-medium mt-1 ${healthColor}`} data-testid="pool-health-label">{healthLabel}</div>
            <div className="text-[10px] font-mono text-zinc-600 mt-1">
              {stats?.zone_name ? <>Zone: <span className="text-zinc-400">{stats.zone_name}</span></> : "No zone configured"}
            </div>
          </div>
        </div>

        {/* Target + refill controls */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-end">
          <Field label={`Pool target (0–${stats?.hard_max ?? 50})`} hint="0 disables the pool. Higher = more instant URLs ready, slightly more Cloudflare API usage.">
            <Input
              type="number"
              min={0}
              max={stats?.hard_max ?? 50}
              value={target}
              onChange={(e) => onTargetChange(Math.max(0, Math.min(stats?.hard_max ?? 50, parseInt(e.target.value || "0", 10) || 0)))}
              data-testid="admin-pool-target"
            />
          </Field>
          <div className="text-[11px] font-mono text-zinc-500 leading-relaxed md:col-span-1">
            Save platform settings to apply a new target — the scheduler refills automatically every 3 min, or click "Refill now" for an instant top-up.
          </div>
          <div className="flex md:justify-end gap-2">
            <button
              onClick={runHealer}
              disabled={healing}
              className="px-4 py-2 border border-emerald-500 text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium"
              data-testid="admin-routing-heal"
              title="Re-push FQDN to build engine + force-redeploy any apps where Traefik has lost the route. Fixes 'no available server' / no SSL."
            >
              {healing ? "Healing…" : "Heal routing"}
            </button>
            <button
              onClick={refill}
              disabled={refilling || !stats?.cloudflare_ready}
              className="px-4 py-2 border border-brand text-brand hover:bg-brand/10 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium"
              data-testid="admin-pool-refill"
            >
              {refilling ? "Refilling…" : "Refill now"}
            </button>
          </div>
        </div>

        {/* Cloudflare proxy toggle */}
        <div className="border-t border-white/[0.04] pt-4 grid grid-cols-1 md:grid-cols-3 gap-5 items-start">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2">Cloudflare proxy mode</div>
            <label className="flex items-start gap-3 cursor-pointer" data-testid="admin-cf-proxied-toggle">
              <input
                type="checkbox"
                checked={!!proxied}
                onChange={(e) => onProxiedChange(e.target.checked)}
                className="mt-1 accent-brand h-4 w-4"
              />
              <span>
                <span className="text-sm font-medium text-zinc-200 block">
                  Proxy traffic through Cloudflare {proxied ? <span className="text-orange-400 font-mono text-xs">🟠 on</span> : <span className="text-zinc-500 font-mono text-xs">⚪ off</span>}
                </span>
                <span className="text-[11px] font-mono text-zinc-500 leading-relaxed block mt-1">
                  ON (recommended w/ Origin Cert): Cloudflare terminates TLS — instant SSL for every subdomain via your wildcard Origin Cert. No Let's Encrypt needed.<br />
                  OFF: traffic hits the build engine directly — it does Let's Encrypt per app (slower, can rate-limit).
                </span>
              </span>
            </label>
          </div>
          <div className="text-[11px] font-mono text-zinc-500 leading-relaxed md:col-span-1">
            Existing DNS records keep their old proxy state until you click "Sync to Cloudflare" — that flips every managed record on Cloudflare in one go.
            {unsynced > 0 && (
              <div className="mt-2 text-amber-400">
                {unsynced} record{unsynced === 1 ? "" : "s"} still on the old state.
              </div>
            )}
          </div>
          <div className="flex md:justify-end">
            <button
              onClick={syncProxied}
              disabled={syncing || !stats?.cloudflare_ready}
              className="px-4 py-2 border border-orange-500 text-orange-400 hover:bg-orange-500/10 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium"
              data-testid="admin-pool-sync-proxied"
              title="Push the current proxy-mode preference to every existing Cloudflare DNS record (pool + claimed)."
            >
              {syncing ? "Syncing…" : "Sync to Cloudflare"}
            </button>
          </div>
        </div>

        {/* Upcoming preview */}
        {stats?.upcoming?.length ? (
          <div className="border-t border-white/[0.04] pt-4">
            <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2">Next in line (FIFO — oldest claimed first)</div>
            <div className="flex flex-wrap gap-2" data-testid="pool-upcoming">
              {stats.upcoming.map((u) => (
                <span key={u.fqdn} className="text-[11px] font-mono px-2 py-1 bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
                  {u.fqdn}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </Section>
  );
}


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
    subdomain_pool_target: 10,
    cloudflare_proxied: true,
    company_country: "",
    company_name: "",
    company_address: "",
    company_postcode: "",
    company_city: "",
    company_vat_id: "",
    // SMSTools (EU SMS). Client secret stored Fernet-encrypted server-side.
    smstools_client_id: "",
    smstools_client_secret: "",
    smstools_sender_id: "",
    smstools_webhook_url: "",
    smstools_test_mode: false,
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
        subdomain_pool_target: r.data.subdomain_pool_target ?? 10,
        cloudflare_proxied: r.data.cloudflare_proxied ?? true,
        company_country: r.data.company_country || "",
        company_name: r.data.company_name || "",
        company_address: r.data.company_address || "",
        company_postcode: r.data.company_postcode || "",
        company_city: r.data.company_city || "",
        company_vat_id: r.data.company_vat_id || "",
        smstools_client_id: r.data.smstools_client_id || "",
        smstools_client_secret: "", // never round-trip; backend redacts
        smstools_sender_id: r.data.smstools_sender_id || "",
        smstools_webhook_url: r.data.smstools_webhook_url || "",
        smstools_test_mode: !!r.data.smstools_test_mode,
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
        if ((k === "cloudflare_api_token" || k === "smstools_client_secret" || k === "mailersend_api_key") && v === "") return;
        payload[k] = v;
      });
      const r = await api.put("/admin/platform-settings", payload);
      setS(r.data);
      setForm((f) => ({ ...f, cloudflare_api_token: "", smstools_client_secret: "", mailersend_api_key: "" }));
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
        description="Every new app automatically gets a subdomain like {slug}.yourzone.app. DeployUnit creates the DNS A-record via Cloudflare on your behalf."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Field label="Root domain (must be in Cloudflare)" hint="e.g. deployunit.com">
            <Input
              value={form.cloudflare_zone_name}
              onChange={(e) => setForm({ ...form, cloudflare_zone_name: e.target.value })}
              placeholder="deployunit.com"
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
          <Field label="Deploy target IP (A record)" hint="Your build engine server IP">
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
              placeholder="server-1.deployunit.internal"
              data-testid="admin-target-host"
            />
          </Field>
        </div>
      </Section>

      <SubdomainPoolWidget
        target={form.subdomain_pool_target}
        onTargetChange={(n) => setForm({ ...form, subdomain_pool_target: n })}
        proxied={form.cloudflare_proxied}
        onProxiedChange={(v) => setForm({ ...form, cloudflare_proxied: v })}
      />

      <Section
        title="SMSTools (EU SMS gateway)"
        description="GDPR-compliant European SMS provider for customer alerts. Get credentials at smstools.com → Account → Developers → API & Webhooks."
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <Field label="Client ID" hint="SMSTools Dashboard → Developers → API & Webhooks → API keys.">
            <Input
              value={form.smstools_client_id}
              onChange={(e) => setForm({ ...form, smstools_client_id: e.target.value })}
              placeholder="paste client_id here"
              data-testid="admin-smstools-client-id"
            />
          </Field>
          <Field label="Client Secret" hint={s.smstools_client_secret_set ? "A secret is already saved. Leave blank to keep it." : "Same page as Client ID. Stored Fernet-encrypted server-side."}>
            <Input
              type="password"
              value={form.smstools_client_secret}
              onChange={(e) => setForm({ ...form, smstools_client_secret: e.target.value })}
              placeholder={s.smstools_client_secret_set ? "•••••••• (saved)" : "paste secret here"}
              data-testid="admin-smstools-client-secret"
            />
          </Field>
          <Field
            label="Sender ID"
            hint="Brand name (≤11 alphanumeric chars) OR digits-only (≤14). Pre-register your brand with SMSTools for EU carrier acceptance — otherwise carriers return error 111."
          >
            <Input
              value={form.smstools_sender_id}
              onChange={(e) => setForm({ ...form, smstools_sender_id: e.target.value })}
              placeholder="DeployUnit"
              data-testid="admin-smstools-sender"
            />
            <SenderIdValidator value={form.smstools_sender_id} />
          </Field>
          <Field label="Delivery webhook URL (optional)" hint="Have SMSTools call back here when a message status changes — used to refund failed sends. Recommended.">
            <Input
              value={form.smstools_webhook_url}
              onChange={(e) => setForm({ ...form, smstools_webhook_url: e.target.value })}
              placeholder="https://deployunit.com/api/notifications/smstools/status"
              data-testid="admin-smstools-webhook"
            />
          </Field>
          <div className="md:col-span-2 flex items-center gap-2 pt-1">
            <input
              id="smstools_test_mode"
              type="checkbox"
              checked={form.smstools_test_mode}
              onChange={(e) => setForm({ ...form, smstools_test_mode: e.target.checked })}
              data-testid="admin-smstools-test-mode"
            />
            <label htmlFor="smstools_test_mode" className="text-xs font-mono text-zinc-400 cursor-pointer">
              Test mode (validate payload, but don't deliver or charge — useful for first-time setup)
            </label>
          </div>
        </div>
        <SMSToolsTestSend />
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
          <Field label="From name" hint="Display name in the inbox. Default 'DeployUnit' if blank.">
            <Input
              value={form.mailersend_from_name}
              onChange={(e) => setForm({ ...form, mailersend_from_name: e.target.value })}
              placeholder="DeployUnit"
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
    if (!window.confirm(`Switch this Workspace to ${plan}?`)) return;
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
        {data.workspaces.length === 0 && <div className="text-xs font-mono text-zinc-500">User owns no Workspaces.</div>}
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

/* ─────────────────────────── Tickets ─────────────────────────── */
function TicketsAdminTab() {
  const [stats, setStats] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ status: "", priority: "", q: "" });
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filter.status) params.status = filter.status;
      if (filter.priority) params.priority = filter.priority;
      if (filter.q) params.q = filter.q;
      const [list, st] = await Promise.all([
        api.get("/admin/tickets", { params }),
        api.get("/admin/tickets/stats"),
      ]);
      setRows(list.data.tickets || []);
      setStats(st.data || {});
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load tickets");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  if (selected) {
    return (
      <div data-testid="admin-tickets-thread-wrap">
        <TicketThread
          ticketId={selected}
          isAdmin
          onBack={() => { setSelected(null); load(); }}
        />
      </div>
    );
  }

  const KPI = ({ label, value, tone = "zinc" }) => (
    <div className="border border-white/[0.06] bg-[#0a0a0a] p-4">
      <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500">{label}</div>
      <div className={`mt-2 font-display text-2xl tabular-nums ${
        tone === "brand" ? "text-brand" :
        tone === "warn" ? "text-yellow-400" :
        tone === "good" ? "text-emerald-400" : "text-white"}`}
      >{value ?? "—"}</div>
    </div>
  );

  return (
    <div className="space-y-5" data-testid="admin-tickets-tab">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPI label="Needs attention" value={stats?.needs_attention ?? 0} tone="brand" />
        <KPI label="Open" value={stats?.open ?? 0} tone="warn" />
        <KPI label="Awaiting user" value={stats?.awaiting_user ?? 0} />
        <KPI label="Resolved (total)" value={stats?.resolved ?? 0} tone="good" />
      </div>

      <div className="border border-white/[0.06] bg-[#0a0a0a]">
        <div className="p-4 border-b border-white/[0.06] flex flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-zinc-500" />
          <select
            value={filter.status}
            onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
            className="bg-black border border-white/10 px-2 py-1.5 text-xs font-mono focus:border-brand outline-none"
            data-testid="admin-tickets-filter-status"
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="awaiting_support">Awaiting support</option>
            <option value="awaiting_user">Awaiting user</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
          <select
            value={filter.priority}
            onChange={(e) => setFilter((f) => ({ ...f, priority: e.target.value }))}
            className="bg-black border border-white/10 px-2 py-1.5 text-xs font-mono focus:border-brand outline-none"
            data-testid="admin-tickets-filter-priority"
          >
            <option value="">All priorities</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="normal">Normal</option>
            <option value="low">Low</option>
          </select>
          <div className="flex items-center gap-1.5 bg-black border border-white/10 px-2 py-1.5 ml-auto min-w-[220px]">
            <SearchIcon className="h-3.5 w-3.5 text-zinc-500" />
            <input
              value={filter.q}
              onChange={(e) => setFilter((f) => ({ ...f, q: e.target.value }))}
              placeholder="subject or user…"
              className="bg-transparent outline-none text-xs font-mono flex-1"
              data-testid="admin-tickets-filter-q"
            />
          </div>
          <button onClick={load} className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-brand" data-testid="admin-tickets-refresh">
            <RefreshCw className="h-3.5 w-3.5" /> reload
          </button>
        </div>

        {loading ? (
          <div className="p-10 text-center text-zinc-500"><Loader2 className="h-5 w-5 animate-spin mx-auto" /></div>
        ) : rows.length === 0 ? (
          <div className="p-10 text-center text-zinc-500 text-sm" data-testid="admin-tickets-empty">No tickets match the filters.</div>
        ) : (
          <div className="divide-y divide-white/[0.04]">
            {rows.map((t) => (
              <button
                key={t.id}
                onClick={() => setSelected(t.id)}
                className="w-full text-left p-4 hover:bg-white/[0.02] transition-colors grid grid-cols-[1fr_auto] gap-4 items-center"
                data-testid={`admin-ticket-row-${t.id}`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500">
                    <TicketStatusPill s={t.status} />
                    <span>{t.category}</span>
                    <span className={
                      t.priority === "urgent" ? "text-red-400" :
                      t.priority === "high" ? "text-yellow-400" :
                      t.priority === "low" ? "text-zinc-500" : "text-zinc-300"
                    }>{t.priority}</span>
                  </div>
                  <div className="mt-1.5 font-display text-base font-semibold truncate">{t.subject}</div>
                  <div className="text-xs text-zinc-500 mt-0.5 font-mono">
                    {t.user_name || t.user_email} · {t.message_count} msg · #{t.id.slice(0, 8)}
                  </div>
                </div>
                <div className="text-[10px] font-mono text-zinc-500 text-right shrink-0">
                  last {new Date(t.last_msg_at).toLocaleString()}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


/* ─────────────────────────── Credit Packs ─────────────────────────── */
function CreditPacksTab() {
  const [packs, setPacks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/credit-packs");
      setPacks(Array.isArray(r.data) ? r.data.map(p => ({
        id: p.id || "",
        label: p.label || "",
        credits: p.credits ?? 0,
        price_eur: p.price_eur ?? 0,
        bonus_pct: p.bonus_pct ?? 0,
      })) : []);
    } catch (e) {
      toast.error("Could not load credit packs");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const updatePack = (idx, field, value) => {
    setPacks((rows) => rows.map((r, i) => i === idx ? { ...r, [field]: value } : r));
  };

  const addPack = () => {
    const n = packs.length + 1;
    setPacks([...packs, { id: `pack${n}`, label: "New pack", credits: 100, price_eur: 10, bonus_pct: 0 }]);
  };

  const removePack = (idx) => {
    setPacks(packs.filter((_, i) => i !== idx));
  };

  const save = async () => {
    // client-side guardrails so we surface helpful errors before the API call
    const ids = new Set();
    for (const [i, p] of packs.entries()) {
      if (!p.id || !p.id.trim()) return toast.error(`Row ${i + 1}: id is required`);
      const pid = p.id.trim().toLowerCase();
      if (ids.has(pid)) return toast.error(`Row ${i + 1}: duplicate id "${pid}"`);
      ids.add(pid);
      if (Number(p.credits) <= 0) return toast.error(`Row ${i + 1}: credits must be > 0`);
      if (Number(p.price_eur) <= 0) return toast.error(`Row ${i + 1}: price must be > 0`);
    }
    setSaving(true);
    try {
      const payload = {
        packs: packs.map((p) => ({
          id: p.id.trim().toLowerCase(),
          label: (p.label || "").trim() || p.id.trim(),
          credits: Number(p.credits),
          price_eur: Number(p.price_eur),
          bonus_pct: Number(p.bonus_pct) || 0,
        })),
      };
      const r = await api.put("/admin/credit-packs", payload);
      setPacks(r.data.map(p => ({
        id: p.id, label: p.label, credits: p.credits,
        price_eur: p.price_eur, bonus_pct: p.bonus_pct ?? 0,
      })));
      toast.success("Credit packs saved");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (!window.confirm("Revert to the built-in default pricing? Any custom packs will be lost.")) return;
    setResetting(true);
    try {
      const r = await api.post("/admin/credit-packs/reset");
      setPacks(r.data.map(p => ({
        id: p.id, label: p.label, credits: p.credits,
        price_eur: p.price_eur, bonus_pct: p.bonus_pct ?? 0,
      })));
      toast.success("Reverted to defaults");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Reset failed");
    } finally {
      setResetting(false);
    }
  };

  if (loading) return <div className="flex items-center gap-2 text-zinc-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading credit packs…</div>;

  return (
    <div className="space-y-4" data-testid="admin-credit-packs">
      <Section
        title="Credit packs catalog"
        description="These are the one-shot top-up packs users see in the Buy Credits flow. Bulk discount is shown as a + bonus_pct badge on the pack. Changes are live immediately — no redeploy needed."
      >
        <div className="text-[10px] font-mono uppercase tracking-[0.35em] text-zinc-500 mb-3">
          // {packs.length} pack{packs.length === 1 ? "" : "s"} configured · €/credit shown per row
        </div>

        <div className="space-y-3" data-testid="credit-packs-rows">
          {packs.map((p, idx) => {
            const credits = Math.max(0, Number(p.credits) || 0);
            const price = Math.max(0, Number(p.price_eur) || 0);
            const perCredit = credits > 0 ? (price / credits) : 0;
            return (
              <div key={idx} className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end border border-white/[0.06] bg-black p-3" data-testid={`credit-pack-row-${idx}`}>
                <div className="md:col-span-2">
                  <Field label="ID">
                    <Input
                      value={p.id}
                      onChange={(e) => updatePack(idx, "id", e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))}
                      placeholder="small"
                      data-testid={`credit-pack-id-${idx}`}
                    />
                  </Field>
                </div>
                <div className="md:col-span-3">
                  <Field label="Label">
                    <Input
                      value={p.label}
                      onChange={(e) => updatePack(idx, "label", e.target.value)}
                      placeholder="Starter"
                      data-testid={`credit-pack-label-${idx}`}
                    />
                  </Field>
                </div>
                <div className="md:col-span-2">
                  <Field label="Credits">
                    <Input
                      type="number" min="1" step="1"
                      value={p.credits}
                      onChange={(e) => updatePack(idx, "credits", e.target.value)}
                      data-testid={`credit-pack-credits-${idx}`}
                    />
                  </Field>
                </div>
                <div className="md:col-span-2">
                  <Field label="Price (€)">
                    <Input
                      type="number" min="0.01" step="0.01"
                      value={p.price_eur}
                      onChange={(e) => updatePack(idx, "price_eur", e.target.value)}
                      data-testid={`credit-pack-price-${idx}`}
                    />
                  </Field>
                </div>
                <div className="md:col-span-2">
                  <Field label="Bonus %" hint="bulk discount badge">
                    <Input
                      type="number" min="0" max="500" step="1"
                      value={p.bonus_pct}
                      onChange={(e) => updatePack(idx, "bonus_pct", e.target.value)}
                      data-testid={`credit-pack-bonus-${idx}`}
                    />
                  </Field>
                </div>
                <div className="md:col-span-1 flex md:justify-end">
                  <button
                    onClick={() => removePack(idx)}
                    className="inline-flex items-center justify-center h-9 w-9 border border-white/10 text-zinc-400 hover:text-signal-failed hover:border-signal-failed/40 transition-colors"
                    title="Remove pack"
                    data-testid={`credit-pack-remove-${idx}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                <div className="md:col-span-12 text-[11px] font-mono text-zinc-500 -mt-1">
                  {credits > 0 && price > 0 ? (
                    <>€{perCredit.toFixed(3)} / credit · effective rate {(1 / perCredit).toFixed(1)} credits per €</>
                  ) : (
                    <>fill in credits + price to see the per-credit rate</>
                  )}
                </div>
              </div>
            );
          })}
          {packs.length === 0 && (
            <div className="text-sm text-zinc-500 font-mono py-6 text-center border border-dashed border-white/10">
              No packs configured yet. Add at least one — users can&apos;t top up otherwise.
            </div>
          )}
        </div>

        <div className="flex flex-wrap gap-2 mt-4">
          <button
            onClick={addPack}
            className="inline-flex items-center gap-2 px-3 py-2 border border-white/10 text-sm font-mono text-zinc-300 hover:text-brand hover:border-brand/40 transition-colors"
            data-testid="credit-pack-add-btn"
          >
            <Plus className="h-4 w-4" /> Add pack
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-black text-sm font-mono font-medium hover:bg-brand/90 disabled:opacity-50 transition-colors"
            data-testid="credit-pack-save-btn"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {saving ? "Saving…" : "Save catalog"}
          </button>
          <button
            onClick={reset}
            disabled={resetting}
            className="inline-flex items-center gap-2 px-3 py-2 border border-white/10 text-sm font-mono text-zinc-400 hover:text-zinc-100 transition-colors ml-auto"
            data-testid="credit-pack-reset-btn"
          >
            {resetting ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
            Revert to defaults
          </button>
        </div>
      </Section>
    </div>
  );
}


/* ─────────────────────────── Admin shell ─────────────────────────── */
export default function Admin() {
  const [tab, setTab] = useState("integrations");

  return (
    <div className="px-4 py-6 sm:p-8 max-w-screen-2xl mx-auto" data-testid="admin-page">
      <div className="flex items-center gap-3 mb-1">
        <ShieldCheck className="h-5 w-5 text-brand" />
        <h1 className="font-display text-2xl sm:text-3xl tracking-tighter">Admin Console</h1>
      </div>
      <p className="text-sm text-zinc-400 mb-6">Platform-wide configuration. Only visible to admins.</p>

      <TabBar tabs={TABS} value={tab} onChange={setTab} testIdPrefix="admin-tab" />

      {tab === "integrations" && <IntegrationsTab />}
      {tab === "plans" && <PlansTab />}
      {tab === "credit-packs" && <CreditPacksTab />}
      {tab === "resources" && <ResourcesTab />}
      {tab === "platform" && <PlatformTab />}
      {tab === "vat" && <VatTab />}
      {tab === "users" && <UsersTab />}
      {tab === "tickets" && <TicketsAdminTab />}
    </div>
  );
}

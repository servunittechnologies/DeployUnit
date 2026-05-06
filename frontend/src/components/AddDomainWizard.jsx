import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import {
  Globe, ArrowRight, ArrowLeft, CheckCircle2, Copy, Loader2, X,
  ExternalLink, ShieldCheck, AlertTriangle, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

/**
 * 3-step add-domain wizard. Lives inside a full-screen overlay.
 *
 * Props:
 *   open         — boolean, controls visibility
 *   onClose      — close handler
 *   onCreated    — called once verification succeeds (parent should refetch)
 *   apps         — optional list for the "Which app?" selector (omit when
 *                  rendering inside an AppDetail page that already has an app)
 *   presetAppId  — optional, skips the app picker
 */
export default function AddDomainWizard({ open, onClose, onCreated, apps, presetAppId }) {
  const [step, setStep] = useState(1);
  const [domain, setDomain] = useState("");
  const [appId, setAppId] = useState(presetAppId || (apps?.[0]?.id ?? ""));
  const [creating, setCreating] = useState(false);
  const [domainId, setDomainId] = useState(null);
  const [target, setTarget] = useState(null);
  const [status, setStatus] = useState(null);
  const [checking, setChecking] = useState(false);
  const pollRef = useRef(null);

  // Reset when (re)opened
  useEffect(() => {
    if (open) {
      setStep(1);
      setDomain("");
      setAppId(presetAppId || (apps?.[0]?.id ?? ""));
      setDomainId(null);
      setTarget(null);
      setStatus(null);
    } else {
      if (pollRef.current) clearInterval(pollRef.current);
    }
  }, [open, presetAppId, apps]);

  // Auto-poll verify while on step 2
  useEffect(() => {
    if (step !== 2 || !domainId) return;
    const tick = async () => {
      try {
        const r = await api.post(`/domains/${domainId}/verify`);
        setStatus(r.data);
        if (r.data.dns_verified && r.data.ssl_status === "active") {
          clearInterval(pollRef.current);
          setStep(3);
        }
      } catch (e) { /* ignore transient */ }
    };
    pollRef.current = setInterval(tick, 10000);
    tick();  // immediate first run
    return () => clearInterval(pollRef.current);
  }, [step, domainId]);

  if (!open) return null;

  const createDomain = async () => {
    if (!domain.trim() || !appId) return;
    setCreating(true);
    try {
      const r = await api.post("/domains", { app_id: appId, domain: domain.trim() });
      const id = r.data.id;
      setDomainId(id);
      const t = await api.get(`/domains/${id}/dns-target`);
      setTarget(t.data);
      setStep(2);
      toast.success("Domain added — follow the DNS instructions");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not add domain");
    } finally {
      setCreating(false);
    }
  };

  const checkNow = async () => {
    if (!domainId) return;
    setChecking(true);
    try {
      const r = await api.post(`/domains/${domainId}/verify`);
      setStatus(r.data);
      if (r.data.dns_verified && r.data.ssl_status === "active") setStep(3);
    } finally {
      setChecking(false);
    }
  };

  const finish = () => {
    onCreated?.();
    onClose();
  };

  const steps = [
    { id: 1, label: "Enter domain" },
    { id: 2, label: "Configure DNS" },
    { id: 3, label: "Live" },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={onClose}
      data-testid="domain-wizard"
    >
      <div
        className="relative w-full max-w-2xl bg-[#0a0a0a] border border-white/10 flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4 text-brand" />
            <h2 className="font-display text-lg tracking-tight">Add custom domain</h2>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-white" data-testid="domain-wizard-close">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* step indicator */}
        <div className="flex items-center px-6 py-3 border-b border-white/[0.06] text-xs font-mono uppercase tracking-[0.3em]">
          {steps.map((s, i) => (
            <div key={s.id} className="flex items-center gap-3 flex-1">
              <span
                className={`h-6 w-6 inline-flex items-center justify-center border ${
                  step > s.id
                    ? "border-signal-live bg-signal-live/10 text-signal-live"
                    : step === s.id
                      ? "border-brand bg-brand/10 text-brand"
                      : "border-white/10 text-zinc-600"
                }`}
              >
                {step > s.id ? <CheckCircle2 className="h-3.5 w-3.5" /> : s.id}
              </span>
              <span className={step === s.id ? "text-brand" : step > s.id ? "text-signal-live" : "text-zinc-500"}>
                {s.label}
              </span>
              {i < steps.length - 1 && <div className="flex-1 h-px bg-white/[0.06]" />}
            </div>
          ))}
        </div>

        {/* body */}
        <div className="px-6 py-6 overflow-y-auto">
          {step === 1 && (
            <div className="space-y-5" data-testid="wizard-step-1">
              <div>
                <label className="block text-[10px] uppercase tracking-[0.35em] text-zinc-500 font-mono mb-1.5">Domain</label>
                <input
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  placeholder="app.yourdomain.com"
                  autoFocus
                  className="w-full bg-black border border-white/10 px-3 py-2.5 text-sm font-mono focus:border-brand focus:ring-1 focus:ring-brand/60 focus:outline-none"
                  data-testid="wizard-domain-input"
                />
                <div className="mt-2 text-xs font-mono text-zinc-500">
                  Can be a subdomain (<span className="text-zinc-300">app.brand.com</span>) or apex (<span className="text-zinc-300">brand.com</span>).
                </div>
              </div>
              {apps && !presetAppId && (
                <div>
                  <label className="block text-[10px] uppercase tracking-[0.35em] text-zinc-500 font-mono mb-1.5">Link to app</label>
                  <select
                    value={appId}
                    onChange={(e) => setAppId(e.target.value)}
                    className="w-full bg-black border border-white/10 px-3 py-2.5 text-sm font-mono focus:border-brand focus:outline-none"
                    data-testid="wizard-app-select"
                  >
                    {apps.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}

          {step === 2 && target && (
            <div className="space-y-5" data-testid="wizard-step-2">
              {!target.record_type ? (
                <div className="p-4 border border-signal-failed/30 bg-signal-failed/5 text-sm text-signal-failed" data-testid="wizard-no-target">
                  <div className="flex items-center gap-2 font-mono mb-1"><AlertTriangle className="h-4 w-4" /> No DNS target configured</div>
                  <div className="text-zinc-300">Ask your admin to set the platform DNS target in <span className="text-brand">Admin → Platform Domain</span>.</div>
                </div>
              ) : (
                <>
                  <div>
                    <div className="text-xs text-zinc-400 mb-3">
                      Open your DNS provider ({target.is_apex ? "registrar" : "Cloudflare, Route 53, …"}) and add this record for <span className="font-mono text-brand">{target.domain}</span>:
                    </div>
                    <div className="grid grid-cols-12 gap-px bg-white/[0.06] border border-white/10">
                      {[
                        ["Type", target.record_type],
                        ["Name", target.record_name],
                        ["Value", target.record_value],
                        ["TTL", `${target.ttl}`],
                      ].map(([k, v]) => (
                        <div key={k} className="col-span-6 md:col-span-3 bg-background p-3">
                          <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 font-mono">{k}</div>
                          <div className="mt-1 font-mono text-sm text-brand flex items-center gap-2 break-all">
                            {v}
                            <button
                              onClick={() => { navigator.clipboard.writeText(v); toast.success("Copied"); }}
                              className="text-zinc-500 hover:text-brand ml-auto"
                              data-testid={`wizard-copy-${k.toLowerCase()}`}
                              title={`Copy ${k}`}
                            ><Copy className="h-3 w-3" /></button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className={`p-4 border ${status?.dns_verified ? "border-signal-live/30 bg-signal-live/5" : "border-white/10 bg-white/[0.02]"}`} data-testid="wizard-check-status">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 font-mono text-sm">
                        {status?.dns_verified ? (
                          <><CheckCircle2 className="h-4 w-4 text-signal-live" /><span className="text-signal-live">DNS resolved</span></>
                        ) : checking ? (
                          <><Loader2 className="h-4 w-4 animate-spin text-brand" /><span className="text-zinc-400">Checking DNS…</span></>
                        ) : (
                          <><Loader2 className="h-4 w-4 animate-spin text-zinc-500" /><span className="text-zinc-400">Waiting for DNS to propagate…</span></>
                        )}
                      </div>
                      <button
                        onClick={checkNow}
                        disabled={checking}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 border border-white/10 hover:border-brand/70 hover:text-brand text-xs font-mono disabled:opacity-50"
                        data-testid="wizard-check-now"
                      >
                        <RefreshCw className={`h-3 w-3 ${checking ? "animate-spin" : ""}`} /> Check now
                      </button>
                    </div>
                    {status?.last_dns_check?.message && (
                      <div className="mt-2 text-xs font-mono text-zinc-500">{status.last_dns_check.message}</div>
                    )}
                    {status?.last_dns_check?.observed?.length > 0 && (
                      <div className="mt-2 text-xs font-mono text-zinc-500">
                        observed: <span className="text-zinc-300">{status.last_dns_check.observed.join(", ")}</span>
                      </div>
                    )}
                    {status?.dns_verified && status?.ssl_status !== "active" && (
                      <div className="mt-2 flex items-center gap-2 text-xs font-mono text-brand">
                        <ShieldCheck className="h-3.5 w-3.5 animate-pulse" /> issuing Let's Encrypt certificate…
                      </div>
                    )}
                  </div>
                  <div className="text-xs font-mono text-zinc-500">
                    This page polls every 10 seconds. DNS usually propagates in 1–5 minutes; some registrars take up to an hour.
                  </div>
                </>
              )}
            </div>
          )}

          {step === 3 && (
            <div className="text-center py-6" data-testid="wizard-step-3">
              <div className="mx-auto h-12 w-12 border border-signal-live/40 bg-signal-live/10 flex items-center justify-center">
                <CheckCircle2 className="h-6 w-6 text-signal-live" />
              </div>
              <h3 className="mt-4 font-display text-2xl tracking-tight">Your domain is live</h3>
              <p className="mt-2 text-sm text-zinc-400 max-w-sm mx-auto">
                SSL certificate issued, HTTPS enforced. Share your new address.
              </p>
              <a
                href={`https://${domain}`}
                target="_blank"
                rel="noreferrer"
                className="mt-5 inline-flex items-center gap-2 px-4 py-2 border border-brand/40 text-brand hover:bg-brand/10 text-sm font-mono"
                data-testid="wizard-open-site"
              >
                {domain} <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
          )}
        </div>

        {/* footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-white/[0.06]">
          {step > 1 && step < 3 ? (
            <button onClick={() => setStep(step - 1)} className="text-xs font-mono text-zinc-400 hover:text-brand inline-flex items-center gap-1.5">
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </button>
          ) : <div />}
          {step === 1 && (
            <button
              onClick={createDomain}
              disabled={!domain.trim() || !appId || creating}
              className="magnetic-btn inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50"
              data-testid="wizard-next-1"
            >
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Next <ArrowRight className="h-4 w-4" /></>}
            </button>
          )}
          {step === 2 && (
            <button
              onClick={onClose}
              className="text-xs font-mono text-zinc-400 hover:text-brand"
              data-testid="wizard-close-later"
            >
              I'll come back later
            </button>
          )}
          {step === 3 && (
            <button
              onClick={finish}
              className="magnetic-btn inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90"
              data-testid="wizard-finish"
            >
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Custom subdomain provisioning card — lets the user pick a memorable name
 * like `myapp.deployunit.com` instead of the random pool slug.
 *
 * Safety design:
 *  - The old random URL keeps working while the new one is verified.
 *  - Cutover only happens after 3 successful HTTPS probes (≈90s).
 *  - On verification failure, the request is rolled back automatically.
 *  - The UI polls every 5s while a request is pending so the user gets
 *    real-time feedback ("DNS propagating…", "SSL provisioning…", "live").
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, CheckCircle2, AlertTriangle, X, Globe, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { api, getApiErrorMessage } from "../lib/api";

const PROBE_INTERVAL_MS = 5_000;
const CHECK_DEBOUNCE_MS = 350;

export default function CustomSubdomainCard({ appId, onChanged }) {
  const [state, setState] = useState(null);              // {status, fqdn, ...}
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [check, setCheck] = useState(null);              // {available, reason, fqdn, zone_name}
  const [checking, setChecking] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const checkTimer = useRef(null);

  const loadState = async () => {
    try {
      const r = await api.get(`/apps/${appId}/custom-subdomain`);
      setState(r.data);
    } catch {
      setState({ status: "none" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadState();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appId]);

  // Poll while pending so the user sees progress without manual refresh.
  useEffect(() => {
    if (state?.status !== "pending") return undefined;
    const t = setInterval(() => loadState(), PROBE_INTERVAL_MS);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.status]);

  // Debounced availability check while typing.
  useEffect(() => {
    if (!name) { setCheck(null); return undefined; }
    if (checkTimer.current) clearTimeout(checkTimer.current);
    checkTimer.current = setTimeout(async () => {
      setChecking(true);
      try {
        const r = await api.get(`/apps/${appId}/custom-subdomain/check`, { params: { name } });
        setCheck(r.data);
      } catch (e) {
        setCheck({ available: false, reason: getApiErrorMessage(e) || "Check failed" });
      } finally {
        setChecking(false);
      }
    }, CHECK_DEBOUNCE_MS);
    return () => checkTimer.current && clearTimeout(checkTimer.current);
  }, [name, appId]);

  const submit = async () => {
    if (!check?.available) return;
    setSubmitting(true);
    try {
      const r = await api.post(`/apps/${appId}/custom-subdomain`, { name });
      toast.success(r.data.message || "Provisioning started");
      setName("");
      setCheck(null);
      await loadState();
      onChanged?.();
    } catch (e) {
      toast.error(getApiErrorMessage(e) || "Could not start provisioning");
    } finally {
      setSubmitting(false);
    }
  };

  const cancel = async () => {
    const isActive = state?.status === "active";
    const msg = isActive
      ? `Detach the custom subdomain "${state.fqdn}"? Your app will go back to the original random URL — visitors using the custom subdomain will get DNS errors.`
      : `Cancel this pending request? Any DNS records we just created will be removed.`;
    if (!window.confirm(msg)) return;
    setCancelling(true);
    try {
      await api.delete(`/apps/${appId}/custom-subdomain`);
      toast.success(isActive ? "Custom subdomain detached" : "Request cancelled");
      await loadState();
      onChanged?.();
    } catch (e) {
      toast.error(getApiErrorMessage(e) || "Cancel failed");
    } finally {
      setCancelling(false);
    }
  };

  const previewFqdn = useMemo(() => {
    if (check?.fqdn) return check.fqdn;
    if (!check?.zone_name && !name) return null;
    return null;
  }, [check, name]);

  if (loading) {
    return (
      <div className="border border-white/[0.06] p-4 flex items-center gap-2 text-zinc-500 text-sm">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading subdomain status…
      </div>
    );
  }

  // ── ACTIVE: app is using a custom subdomain
  if (state?.status === "active") {
    return (
      <div className="border border-signal-live/30 bg-signal-live/[0.04] p-4" data-testid="custom-subdomain-active">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] font-mono text-signal-live">
              <CheckCircle2 className="h-3.5 w-3.5" /> Custom subdomain · active
            </div>
            <div className="mt-1.5 font-mono text-sm text-zinc-100 truncate" data-testid="custom-subdomain-active-fqdn">
              {state.fqdn}
            </div>
            <div className="mt-1 text-[11px] font-mono text-zinc-500">
              Activated{state.activated_at ? ` ${new Date(state.activated_at).toLocaleString()}` : ""}
              {state.previous_fqdn && (
                <span className="block">Previous random URL ({state.previous_fqdn}) released back to the pool.</span>
              )}
            </div>
          </div>
          <button
            onClick={cancel}
            disabled={cancelling}
            className="inline-flex items-center gap-2 px-3 py-2 text-xs font-mono border border-white/10 text-zinc-300 hover:text-signal-failed hover:border-signal-failed/40 disabled:opacity-50 transition-colors"
            data-testid="custom-subdomain-detach"
          >
            {cancelling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
            Detach
          </button>
        </div>
      </div>
    );
  }

  // ── PENDING: probe loop is running
  if (state?.status === "pending") {
    const successPct = state.probe_success_needed
      ? Math.min(100, Math.round(((state.probe_success || 0) / state.probe_success_needed) * 100))
      : 0;
    return (
      <div className="border border-brand/40 bg-brand/[0.04] p-4" data-testid="custom-subdomain-pending">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] font-mono text-brand">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Verifying · custom subdomain
            </div>
            <div className="mt-1.5 font-mono text-sm text-zinc-100 truncate" data-testid="custom-subdomain-pending-fqdn">
              {state.fqdn}
            </div>
            <div className="mt-1 text-[11px] font-mono text-zinc-400">
              Your existing URL stays online until DNS &amp; SSL are confirmed working.
            </div>
            <div className="mt-3 flex items-center gap-3 text-[11px] font-mono">
              <div className="flex-1 max-w-xs">
                <div className="h-1.5 bg-white/[0.06] overflow-hidden">
                  <div
                    className="h-full bg-brand transition-all duration-500"
                    style={{ width: `${successPct}%` }}
                    data-testid="custom-subdomain-progress"
                  />
                </div>
                <div className="mt-1 text-zinc-500">
                  {state.probe_success || 0} / {state.probe_success_needed} successful probes
                </div>
              </div>
              {state.last_probe_reason && (
                <div className="text-zinc-500">last: {state.last_probe_reason}</div>
              )}
            </div>
          </div>
          <button
            onClick={cancel}
            disabled={cancelling}
            className="inline-flex items-center gap-2 px-3 py-2 text-xs font-mono border border-white/10 text-zinc-300 hover:text-signal-failed hover:border-signal-failed/40 disabled:opacity-50 transition-colors"
            data-testid="custom-subdomain-cancel"
          >
            {cancelling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
            Cancel
          </button>
        </div>
      </div>
    );
  }

  // ── FAILED/CANCELLED/NONE: show the request form
  const recentlyFailed = state?.status === "failed";
  return (
    <div className="border border-white/[0.06] p-4" data-testid="custom-subdomain-form">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">
        <Globe className="h-3.5 w-3.5" /> Custom subdomain
      </div>
      <div className="mt-1 text-sm text-zinc-300">
        Replace the random URL with something memorable on our root domain.
      </div>
      <div className="mt-1 text-[11px] font-mono text-zinc-500">
        We&apos;ll only switch over once DNS resolves and HTTPS is verified — your app stays online during the cutover.
      </div>

      {recentlyFailed && (
        <div className="mt-3 flex items-start gap-2 border border-signal-failed/30 bg-signal-failed/[0.04] p-2.5 text-xs font-mono text-signal-failed" data-testid="custom-subdomain-error">
          <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <div className="min-w-0">
            <div>Last request failed{state.fqdn ? ` for ${state.fqdn}` : ""}.</div>
            {state.reason && <div className="mt-0.5 text-zinc-400">{state.reason}</div>}
          </div>
        </div>
      )}

      <div className="mt-4 flex flex-col sm:flex-row gap-2 items-stretch">
        <div className="flex-1 flex items-stretch bg-black border border-white/10 focus-within:border-brand">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
            placeholder="myapp"
            maxLength={63}
            className="flex-1 bg-transparent px-3 py-2 text-sm font-mono focus:outline-none placeholder:text-zinc-600"
            data-testid="custom-subdomain-name-input"
          />
          {check?.zone_name && (
            <div className="px-3 py-2 text-sm font-mono text-zinc-500 border-l border-white/10 bg-white/[0.02]">
              .{check.zone_name}
            </div>
          )}
        </div>
        <button
          onClick={submit}
          disabled={!check?.available || submitting}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-brand text-brand-fg text-sm font-medium hover:bg-brand/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          data-testid="custom-subdomain-submit"
        >
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
          Provision
        </button>
      </div>

      <div className="mt-2 min-h-[18px] text-[11px] font-mono" data-testid="custom-subdomain-check-msg">
        {!name && (
          <span className="text-zinc-500">3–63 chars · a-z 0-9 - · cannot start/end with -</span>
        )}
        {name && checking && (
          <span className="text-zinc-500 inline-flex items-center gap-1">
            <Loader2 className="h-3 w-3 animate-spin" /> checking…
          </span>
        )}
        {name && !checking && check?.available && (
          <span className="text-signal-live inline-flex items-center gap-1" data-testid="custom-subdomain-available">
            <CheckCircle2 className="h-3 w-3" /> {check.fqdn} is available
          </span>
        )}
        {name && !checking && check && !check.available && (
          <span className="text-signal-failed" data-testid="custom-subdomain-unavailable">
            ✕ {check.reason}
          </span>
        )}
      </div>
    </div>
  );
}

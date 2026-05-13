/**
 * AppDetail → Add-ons tab.
 *
 * Lists every paid feature the workspace can enable for this app. Each
 * card has its own enable/cancel toggle, shows the credits/month cost,
 * the current subscription status (active / grace / cancelled / inactive),
 * and — for heatmaps — links to the in-house heatmap viewer.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, Check, X as XIcon, AlertTriangle, Coins, Server, Gauge, Activity, ExternalLink, Copy as CopyIcon } from "lucide-react";
import { toast } from "sonner";
import { api, getApiErrorMessage } from "../lib/api";

const ICON_BY_ID = {
  "log-retention": Gauge,
  "heatmaps":      Activity,
  "static-ip":     Server,
};

function relTime(iso) {
  if (!iso) return "";
  const ms = new Date(iso) - new Date();
  const days = Math.round(ms / 86400000);
  if (days > 1) return `in ${days} days`;
  if (days === 1) return "tomorrow";
  if (days === 0) return "today";
  return `${-days} days ago`;
}

export default function AddonsCard({ appId, appName }) {
  const [addons, setAddons] = useState(null);
  const [busy, setBusy] = useState({});

  const load = async () => {
    try {
      const r = await api.get(`/apps/${appId}/addons`);
      setAddons(r.data);
    } catch {
      setAddons([]);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [appId]);

  const setBusyFor = (id, v) => setBusy(b => ({ ...b, [id]: v }));

  const enable = async (id) => {
    setBusyFor(id, true);
    try {
      await api.post(`/apps/${appId}/addons/${id}/enable`);
      toast.success("Add-on enabled — credits charged");
      await load();
    } catch (e) {
      const msg = getApiErrorMessage(e) || "Could not enable";
      if (e?.response?.status === 402) {
        toast.error(`Insufficient credits — top up first. (${msg})`);
      } else {
        toast.error(msg);
      }
    } finally {
      setBusyFor(id, false);
    }
  };

  const cancel = async (id, name) => {
    if (!window.confirm(`Cancel "${name}"? The feature stays active until the period ends, then auto-disables. No refund for the current period.`)) return;
    setBusyFor(id, true);
    try {
      await api.post(`/apps/${appId}/addons/${id}/cancel`);
      toast.success("Cancelled — stays active until period ends");
      await load();
    } catch (e) {
      toast.error(getApiErrorMessage(e) || "Cancel failed");
    } finally {
      setBusyFor(id, false);
    }
  };

  if (!addons) return <div className="flex items-center gap-2 text-zinc-500 p-4 text-sm"><Loader2 className="h-4 w-4 animate-spin" /> Loading add-ons…</div>;

  return (
    <div className="space-y-3" data-testid="app-addons">
      {addons.map(a => {
        const Icon = ICON_BY_ID[a.id] || Coins;
        const sub = a.subscription;
        const statusLabel = !a.active ? "inactive"
          : sub?.status === "grace" ? "grace · top up needed"
          : sub?.status === "cancelled" ? "cancelled · ends soon"
          : "active";
        const statusColor = !a.active ? "text-zinc-500 border-zinc-700"
          : sub?.status === "grace" ? "text-amber-300 border-amber-500/40"
          : sub?.status === "cancelled" ? "text-zinc-400 border-zinc-700"
          : "text-signal-live border-signal-live/40";
        const isHeatmaps = a.id === "heatmaps";
        return (
          <div key={a.id} className="border border-white/[0.06] p-4" data-testid={`addon-card-${a.id}`}>
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="flex items-start gap-3 min-w-0">
                <div className="h-10 w-10 border border-brand/40 flex items-center justify-center shrink-0">
                  <Icon className="h-4 w-4 text-brand" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="font-display text-base text-zinc-100">{a.display_name}</div>
                    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider border font-mono ${statusColor}`}>
                      {statusLabel}
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-zinc-400 leading-relaxed max-w-md">{a.description}</div>
                  {sub?.expires_at && a.active && (
                    <div className="mt-1.5 text-[11px] font-mono text-zinc-500">
                      {sub.status === "cancelled" ? "ends" : "renews"} {relTime(sub.expires_at)} · {sub.cost_cr_month} cr / period
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="text-xs font-mono text-brand whitespace-nowrap">{a.cost_cr_month} cr / mo</div>
                {!a.active ? (
                  <button
                    onClick={() => enable(a.id)}
                    disabled={busy[a.id]}
                    className="inline-flex items-center gap-2 px-3 py-2 bg-brand text-brand-fg text-xs font-mono hover:bg-brand/90 disabled:opacity-50 transition-colors"
                    data-testid={`addon-enable-${a.id}`}
                  >
                    {busy[a.id] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                    Enable
                  </button>
                ) : sub?.status !== "cancelled" ? (
                  <button
                    onClick={() => cancel(a.id, a.display_name)}
                    disabled={busy[a.id]}
                    className="inline-flex items-center gap-2 px-3 py-2 text-xs font-mono border border-white/10 text-zinc-300 hover:text-signal-failed hover:border-signal-failed/40 disabled:opacity-50 transition-colors"
                    data-testid={`addon-cancel-${a.id}`}
                  >
                    {busy[a.id] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <XIcon className="h-3.5 w-3.5" />}
                    Cancel
                  </button>
                ) : null}
              </div>
            </div>
            {sub?.status === "grace" && (
              <div className="mt-3 flex items-start gap-2 border border-amber-500/30 bg-amber-950/20 p-2.5 text-xs font-mono text-amber-300">
                <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                <div>Renewal failed — insufficient credits. Top up before {sub.expires_at?.slice(0, 10)} or this feature auto-disables.</div>
              </div>
            )}
            {isHeatmaps && a.active && <HeatmapsSnippet appId={appId} />}
          </div>
        );
      })}
    </div>
  );
}


function HeatmapsSnippet({ appId }) {
  const backend = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
  const tag = useMemo(() => `<script async src="${backend}/api/heatmaps/snippet.js?app=${appId}"></script>`, [backend, appId]);
  const copy = () => {
    navigator.clipboard.writeText(tag).then(() => toast.success("Snippet copied to clipboard"));
  };
  return (
    <div className="mt-4 border-t border-white/[0.06] pt-4">
      <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500 mb-2">Tracking snippet</div>
      <div className="text-xs text-zinc-400 mb-2">Paste this single tag into your site&apos;s &lt;head&gt; — once. Loads asynchronously, ~1.2KB.</div>
      <div className="flex items-stretch gap-2">
        <code className="flex-1 bg-black border border-white/10 p-2.5 text-[11px] font-mono text-zinc-300 break-all leading-relaxed">
          {tag}
        </code>
        <button onClick={copy} className="inline-flex items-center gap-1.5 px-3 py-2 border border-white/10 text-xs font-mono text-zinc-300 hover:text-brand hover:border-brand/40 transition-colors" data-testid="heatmap-snippet-copy">
          <CopyIcon className="h-3.5 w-3.5" /> Copy
        </button>
      </div>
      <Link
        to={`/app/apps/${appId}/heatmaps`}
        className="mt-3 inline-flex items-center gap-1.5 text-xs font-mono text-brand hover:underline"
        data-testid="heatmap-open-viewer"
      >
        Open heatmap viewer <ExternalLink className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}

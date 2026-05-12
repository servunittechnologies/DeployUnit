import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getApiErrorMessage } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import { toast } from "sonner";
import {
  Sparkles, Wallet, Zap, ArrowRight, Loader2, RefreshCw, ChevronLeft,
} from "lucide-react";

/**
 * Dedicated top-up page reachable from the credits pill in the topbar.
 * No "limit" framing — credits are just a wallet that gets a monthly grant
 * added on top. Users can buy a preset pack or any custom amount.
 */
const CUSTOM_RATE_EUR = 0.10;
const CUSTOM_MIN = 10;
const CUSTOM_MAX = 10000;
const PRESETS = [50, 100, 250, 500, 1000];

export default function CreditsTopup() {
  const navigate = useNavigate();
  const { active } = useWorkspace();
  const [credits, setCredits] = useState({ balance: 0, monthly_grant: 0 });
  const [packs, setPacks] = useState([]);
  const [busy, setBusy] = useState(null);
  const [custom, setCustom] = useState(100);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    if (!active?.id) return;
    setLoading(true);
    try {
      const [b, p] = await Promise.all([
        api.get(`/credits/balance?workspace_id=${active.id}`),
        api.get("/credits/packs"),
      ]);
      setCredits(b.data || { balance: 0, monthly_grant: 0 });
      setPacks(p.data || []);
    } catch (e) {
      toast.error(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [active?.id]);

  async function checkout({ pack, custom_credits }) {
    if (!active?.id) return;
    const key = pack || `custom-${custom_credits}`;
    setBusy(key);
    try {
      const r = await api.post("/credits/checkout", {
        workspace_id: active.id,
        pack: pack || null,
        custom_credits: custom_credits || null,
      });
      if (r.data?.checkout_url) {
        window.location.href = r.data.checkout_url;
      } else {
        toast.error("Could not start checkout. Add a billing profile first.");
      }
    } catch (e) {
      toast.error(getApiErrorMessage(e) || "Checkout failed");
    } finally {
      setBusy(null);
    }
  }

  const customPrice = useMemo(() => (custom * CUSTOM_RATE_EUR).toFixed(2), [custom]);

  return (
    <div className="px-4 py-6 sm:p-8 max-w-4xl" data-testid="credits-topup-page">
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-500 hover:text-white mb-4"
        data-testid="credits-back"
      >
        <ChevronLeft className="h-3 w-3" /> back
      </button>

      <div className="flex items-center gap-3 mb-1">
        <Wallet className="h-5 w-5 text-brand" />
        <h1 className="font-display text-2xl sm:text-3xl tracking-tighter">Top up credits</h1>
      </div>
      <p className="text-sm text-zinc-400 mb-6">
        Credits power SMS, WhatsApp alerts and build overages. Add more whenever you want — no limits, no expiration.
      </p>

      {/* Balance card */}
      <div className="border border-white/[0.06] bg-elevated/30 p-5 mb-6 flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Current balance</div>
          {loading ? (
            <Loader2 className="h-6 w-6 animate-spin text-zinc-500 mt-2" />
          ) : (
            <div className="mt-1 flex items-baseline gap-3">
              <span className="font-display text-5xl tracking-tight text-brand" data-testid="credits-balance">
                {credits.balance}
              </span>
              <span className="text-xs font-mono text-zinc-500">
                ≈ €{(credits.balance * CUSTOM_RATE_EUR).toFixed(2)}
              </span>
            </div>
          )}
          {credits.monthly_grant > 0 && (
            <div className="text-xs font-mono text-zinc-500 mt-2 flex items-center gap-1.5">
              <Sparkles className="h-3 w-3 text-brand" />
              <span>+{credits.monthly_grant} added each month from your plan</span>
            </div>
          )}
        </div>
        <button onClick={load} className="text-xs font-mono text-zinc-500 hover:text-brand inline-flex items-center gap-1">
          <RefreshCw className="h-3 w-3" /> reload
        </button>
      </div>

      {/* Preset packs */}
      <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2">Preset packs</div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
        {packs.map((p) => (
          <button
            key={p.id}
            onClick={() => checkout({ pack: p.id })}
            disabled={busy !== null}
            className="text-left border border-white/[0.08] hover:border-brand/60 bg-elevated/30 p-5 transition-colors disabled:opacity-50 group"
            data-testid={`credits-pack-${p.id}`}
          >
            <div className="flex items-center justify-between">
              <span className="font-display text-lg">{p.label}</span>
              {p.bonus_pct && (
                <span className="text-[9px] font-mono uppercase tracking-[0.25em] text-brand border border-brand/40 px-1.5 py-0.5">
                  +{p.bonus_pct}%
                </span>
              )}
            </div>
            <div className="mt-3 font-display text-3xl text-white tabular-nums">{p.credits} <span className="text-sm text-zinc-500 font-mono">credits</span></div>
            <div className="text-sm font-mono text-zinc-500 mt-1">€{p.price_eur}</div>
            <div className="mt-3 inline-flex items-center gap-1 text-xs font-mono text-brand opacity-0 group-hover:opacity-100 transition-opacity">
              {busy === p.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <>Buy <ArrowRight className="h-3 w-3" /></>}
            </div>
          </button>
        ))}
      </div>

      {/* Custom amount */}
      <div className="border border-white/[0.06] bg-elevated/30 p-5" data-testid="credits-custom-section">
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2">Custom amount</div>
        <div className="flex items-baseline gap-3 flex-wrap">
          <input
            type="number"
            min={CUSTOM_MIN}
            max={CUSTOM_MAX}
            step={10}
            value={custom}
            onChange={(e) => setCustom(Math.max(CUSTOM_MIN, Math.min(CUSTOM_MAX, parseInt(e.target.value || "0", 10))))}
            className="bg-black border border-white/10 px-3 py-2 font-mono text-2xl text-white focus:border-brand outline-none w-32 tabular-nums"
            data-testid="credits-custom-input"
          />
          <span className="text-zinc-500 font-mono text-sm">credits</span>
          <div className="ml-auto text-right">
            <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500">Total</div>
            <div className="font-display text-2xl text-brand">€{customPrice}</div>
            <div className="text-[10px] font-mono text-zinc-500">€{CUSTOM_RATE_EUR.toFixed(2)}/credit</div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mt-4">
          {PRESETS.map((n) => (
            <button
              key={n}
              onClick={() => setCustom(n)}
              className={`text-xs font-mono px-3 py-1.5 border transition-colors ${
                custom === n
                  ? "border-brand text-brand"
                  : "border-white/10 text-zinc-400 hover:border-white/30 hover:text-white"
              }`}
              data-testid={`credits-quick-${n}`}
            >
              {n}
            </button>
          ))}
        </div>

        <button
          onClick={() => checkout({ custom_credits: custom })}
          disabled={busy !== null || custom < CUSTOM_MIN}
          className="mt-5 w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-brand text-brand-fg hover:bg-brand/90 disabled:opacity-50 px-5 py-3 font-semibold transition-colors"
          data-testid="credits-custom-checkout"
        >
          {busy === `custom-${custom}` ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Zap className="h-4 w-4" />
              Top up {custom} credits · €{customPrice}
            </>
          )}
        </button>
      </div>

      <p className="text-xs font-mono text-zinc-600 mt-4">
        Payment is processed securely. VAT is added based on your billing profile.
      </p>
    </div>
  );
}

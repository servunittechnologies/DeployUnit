import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { AlertTriangle, Sparkles, Zap } from "lucide-react";

/**
 * Lightweight strip at the top of the workspace dashboard that shows the
 * current plan + how much of each resource is used. Turns amber at 80% and
 * red at 100% — and at 100% we show an inline "Upgrade" CTA.
 *
 * Props:
 *   workspaceId — required
 */
export default function UsageStrip({ workspaceId }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!workspaceId) return;
    api.get(`/workspaces/${workspaceId}/usage`)
      .then((r) => setData(r.data))
      .catch(() => null);
  }, [workspaceId]);

  if (!data) return null;
  const plan = data.plan;
  const usage = data.usage;

  const rows = [
    { key: "apps", label: "Apps", used: usage.apps, cap: plan.limits?.apps },
    { key: "domains", label: "Domains", used: usage.domains, cap: plan.limits?.domains },
    { key: "team", label: "Team", used: usage.team, cap: plan.limits?.team },
  ];
  const isFree = (plan.id === "free") || plan.price === 0;
  const anyMaxed = rows.some((r) => r.cap > 0 && r.used >= r.cap);

  return (
    <div className="border-b border-white/[0.06] bg-white/[0.01]" data-testid="usage-strip">
      <div className="px-6 py-3 flex items-center gap-6 flex-wrap">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 text-[10px] uppercase tracking-[0.3em] ${plan.highlight ? "border border-brand/40 text-brand" : "border border-white/10 text-zinc-400"}`}>
            {plan.name}
          </span>
          <span className="text-xs font-mono text-zinc-500">{plan.price > 0 ? `€${plan.price}/mo` : "free"}</span>
        </div>
        <div className="flex items-center gap-5 flex-1 min-w-[300px]">
          {rows.map((r) => (
            <UsageBar key={r.key} {...r} />
          ))}
          {plan.credits > 0 && (
            <div className="flex items-center gap-1.5 text-xs font-mono text-zinc-500" data-testid="usage-credits">
              <Sparkles className="h-3 w-3 text-brand" /> {plan.credits} credits/mo
            </div>
          )}
        </div>
        {(anyMaxed || isFree) && (
          <Link
            to="/app/billing"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-brand text-brand-fg hover:bg-brand/90 transition-colors"
            data-testid="usage-upgrade"
          >
            <Zap className="h-3 w-3" /> Upgrade
          </Link>
        )}
      </div>
    </div>
  );
}

function UsageBar({ label, used, cap }) {
  const unlimited = cap === -1 || cap === undefined;
  const pct = unlimited ? 0 : Math.min(100, Math.round((used / Math.max(cap, 1)) * 100));
  const color = pct >= 100 ? "bg-signal-failed" : pct >= 80 ? "bg-signal-queued" : "bg-brand";
  const textColor = pct >= 100 ? "text-signal-failed" : pct >= 80 ? "text-signal-queued" : "text-zinc-300";
  return (
    <div className="flex flex-col gap-1 min-w-[110px]" data-testid={`usage-${label.toLowerCase()}`}>
      <div className="flex items-baseline gap-1.5 text-xs font-mono">
        <span className="text-zinc-500">{label}</span>
        <span className={textColor}>
          {used}/{unlimited ? "∞" : cap}
        </span>
        {pct >= 100 && <AlertTriangle className="h-3 w-3 text-signal-failed" />}
      </div>
      {!unlimited && (
        <div className="h-1 bg-white/[0.06] overflow-hidden">
          <div className={`h-full ${color} transition-all duration-300`} style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}

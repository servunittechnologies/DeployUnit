import StatusBadge from "./StatusBadge";
import { GitBranch, GitCommit, Clock, RotateCw, ExternalLink } from "lucide-react";

function fmtDuration(start, end) {
  if (!start) return "—";
  const a = new Date(start).getTime();
  const b = end ? new Date(end).getTime() : Date.now();
  const sec = Math.max(0, Math.round((b - a) / 1000));
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function timeAgo(iso) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function DeploymentStatus({ app, latest, history, onRedeploy }) {
  const inFlight = latest && (latest.status === "queued" || latest.status === "building");
  const lastLive = (history || []).find((d) => d.status === "live");

  return (
    <div className="border border-white/[0.06] bg-elevated/30 p-5 space-y-4 relative" data-testid="deployment-status">
      {inFlight && (
        <div className="absolute -top-px left-0 right-0 h-px overflow-hidden">
          <div className="h-px bg-brand/60 animate-[scan_2.2s_ease-in-out_infinite] w-1/3" />
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <StatusBadge status={latest?.status || app?.status || "pending"} />
          <div>
            <div className="text-sm font-medium">
              {inFlight ? "Deployment in progress" : latest?.status === "failed" ? "Last deployment failed" : "Currently live"}
            </div>
            <div className="text-xs font-mono text-zinc-500 mt-0.5">
              {latest?.commit_message || (app?.primary_url ? "from latest deploy" : "no deployments yet")}
            </div>
          </div>
        </div>
        <button
          onClick={onRedeploy}
          className="inline-flex items-center gap-2 px-3 py-1.5 border border-white/15 hover:border-brand hover:text-brand text-xs font-mono uppercase tracking-[0.2em]"
          data-testid="deploy-status-redeploy"
        >
          <RotateCw className="h-3 w-3" /> Redeploy
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.06] border border-white/[0.06]">
        <div className="bg-background p-3">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Branch</div>
          <div className="mt-1 text-sm font-mono inline-flex items-center gap-1.5">
            <GitBranch className="h-3 w-3 text-brand" />
            {latest?.branch || app?.branch || "main"}
          </div>
        </div>
        <div className="bg-background p-3">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Commit</div>
          <div className="mt-1 text-sm font-mono inline-flex items-center gap-1.5">
            <GitCommit className="h-3 w-3 text-brand" />
            {latest?.commit_sha ? latest.commit_sha.slice(0, 7) : "HEAD"}
          </div>
        </div>
        <div className="bg-background p-3">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Duration</div>
          <div className="mt-1 text-sm font-mono inline-flex items-center gap-1.5">
            <Clock className="h-3 w-3" />
            {fmtDuration(latest?.started_at, latest?.finished_at)}
          </div>
        </div>
        <div className="bg-background p-3">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">{inFlight ? "Started" : "Last deployed"}</div>
          <div className="mt-1 text-sm font-mono">{timeAgo(latest?.started_at || app?.last_deploy_at)}</div>
        </div>
      </div>

      {/* Mini timeline of last 5 deploys */}
      {history && history.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Recent deployments</div>
          <div className="flex gap-1">
            {history.slice(0, 12).map((d) => {
              const cls = d.status === "live" ? "bg-signal-live"
                : d.status === "building" ? "bg-signal-building animate-pulse"
                : d.status === "queued" ? "bg-signal-queued"
                : d.status === "failed" ? "bg-signal-failed"
                : "bg-zinc-700";
              return <span key={d.id} title={`${d.status} · ${timeAgo(d.started_at)}${d.commit_sha ? " · " + d.commit_sha.slice(0, 7) : ""}`} className={`h-5 w-2 ${cls}`} />;
            })}
          </div>
        </div>
      )}

      {app?.primary_url && (
        <a
          href={app.primary_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-brand hover:underline"
          data-testid="deploy-status-open-url"
        >
          {app.primary_url.replace(/^https?:\/\//, "")} <ExternalLink className="h-3 w-3" />
        </a>
      )}
      {lastLive && lastLive.id !== latest?.id && latest?.status === "failed" && (
        <div className="text-xs font-mono text-zinc-500">
          Currently serving last good build · {lastLive.commit_sha ? lastLive.commit_sha.slice(0, 7) : "unknown commit"} · deployed {timeAgo(lastLive.started_at)}
        </div>
      )}
    </div>
  );
}

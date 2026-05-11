import { AlertOctagon, RotateCw, ExternalLink } from "lucide-react";

export default function BuildErrorPanel({ deployment, onRetry }) {
  if (!deployment || deployment.status !== "failed") return null;
  const summary = deployment.failure_summary || "Deployment failed. Check the build log above for the exact error.";
  const branchHint = /branch ['"]?([\w./-]+)['"]?/i.exec(summary);

  return (
    <div className="border border-signal-failed/40 bg-signal-failed/5 p-5" data-testid="build-error-panel">
      <div className="flex items-start gap-3">
        <AlertOctagon className="h-5 w-5 text-signal-failed flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-signal-failed">
            // build failed
          </div>
          <div className="mt-1 text-sm text-zinc-200 leading-relaxed">{summary}</div>
          <div className="mt-3 flex items-center gap-3 flex-wrap">
            {onRetry && (
              <button
                onClick={onRetry}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-white/15 hover:border-brand hover:text-brand text-xs font-mono uppercase tracking-wider"
                data-testid="build-error-retry"
              >
                <RotateCw className="h-3 w-3" /> redeploy
              </button>
            )}
            {branchHint && (
              <span className="text-xs font-mono text-zinc-400">
                tip: open <strong>Settings → Default branch</strong> and update it
              </span>
            )}
            <a
              href="https://docs.nixpacks.com/troubleshooting"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-mono text-zinc-500 hover:text-brand"
            >
              build troubleshooting <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

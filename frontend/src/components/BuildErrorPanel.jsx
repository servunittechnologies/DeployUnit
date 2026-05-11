import { AlertOctagon, RotateCw, ExternalLink, Github, RefreshCw, BookOpen } from "lucide-react";
import { useNavigate } from "react-router-dom";

/**
 * Smart failure panel — reads the failure summary and matches well-known
 * patterns to surface the right next action (e.g. "Reinstall", "Connect
 * GitHub") instead of just "redeploy and pray".
 */
export default function BuildErrorPanel({ deployment, onRetry, onReinstall }) {
  const navigate = useNavigate();
  if (!deployment || deployment.status !== "failed") return null;
  const summary = deployment.failure_summary
    || (deployment.logs || []).slice(-1)[0]
    || "Deployment failed. Check the build log above for the exact error.";
  const s = summary.toLowerCase();

  // Failure pattern detection
  const isPrivateRepo = /private github repo|connect github/i.test(summary);
  const isMissingEngine = /build[- ]?engine.*(missing|no longer exists|gone)|no such container/i.test(summary);
  const isQuotaHit = /plan'?s? .* limit|upgrade to /i.test(summary);
  const isAuthFail = /authentication failed|repository not found|access denied/i.test(s);
  const branchHint = /branch ['"]?([\w./-]+)['"]?/i.exec(summary);

  // Pick the primary CTA
  let primary = null;
  if (isPrivateRepo) {
    primary = {
      label: "Connect GitHub",
      icon: Github,
      onClick: () => navigate("/app/account#profile"),
      testId: "build-error-connect-gh",
      hint: "Reconnect on your Account page so we can register a deploy key for your private repo.",
    };
  } else if (isMissingEngine && onReinstall) {
    primary = {
      label: "Reinstall on build engine",
      icon: RefreshCw,
      onClick: onReinstall,
      testId: "build-error-reinstall",
      hint: "The application is missing on the build engine — click to recreate it from your repo.",
    };
  } else if (isQuotaHit) {
    primary = {
      label: "Upgrade plan",
      icon: ExternalLink,
      onClick: () => navigate("/app/account#plan"),
      testId: "build-error-upgrade",
      hint: "You hit your account plan limit. Bump to a higher tier on the Account page.",
    };
  }

  return (
    <div className="border border-signal-failed/40 bg-signal-failed/5 p-5" data-testid="build-error-panel">
      <div className="flex items-start gap-3">
        <AlertOctagon className="h-5 w-5 text-signal-failed flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-signal-failed">
            // build failed
          </div>
          <div className="mt-1 text-sm text-zinc-200 leading-relaxed break-words">{summary}</div>
          {primary?.hint && (
            <div className="mt-2 text-xs text-zinc-400">{primary.hint}</div>
          )}
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            {primary && (
              <button
                onClick={primary.onClick}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand text-brand-fg text-xs font-mono uppercase tracking-wider hover:bg-brand/90"
                data-testid={primary.testId}
              >
                <primary.icon className="h-3 w-3" /> {primary.label}
              </button>
            )}
            {onReinstall && !isPrivateRepo && primary?.label !== "Reinstall on build engine" && (
              <button
                onClick={onReinstall}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-white/15 hover:border-brand hover:text-brand text-xs font-mono uppercase tracking-wider"
                data-testid="build-error-reinstall-alt"
                title="Wipe and recreate the build-engine app from your repo"
              >
                <RefreshCw className="h-3 w-3" /> reinstall
              </button>
            )}
            {onRetry && (
              <button
                onClick={onRetry}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-white/15 hover:border-brand hover:text-brand text-xs font-mono uppercase tracking-wider"
                data-testid="build-error-retry"
              >
                <RotateCw className="h-3 w-3" /> redeploy
              </button>
            )}
            {isAuthFail && (
              <span className="text-xs font-mono text-zinc-400">tip: check repo access & branch name</span>
            )}
            {branchHint && (
              <span className="text-xs font-mono text-zinc-400">tip: verify branch <strong>{branchHint[1]}</strong> exists</span>
            )}
            <a
              href="https://docs.nixpacks.com/troubleshooting"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-mono text-zinc-500 hover:text-brand ml-auto"
            >
              <BookOpen className="h-3 w-3" /> build troubleshooting <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

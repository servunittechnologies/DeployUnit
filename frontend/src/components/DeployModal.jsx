import { useEffect, useState } from "react";
import { api, getApiErrorMessage } from "../lib/api";
import { X, Loader2, GitBranch, GitCommit, Rocket, ExternalLink, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

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

export default function DeployModal({ app, open, onClose, onDeployed }) {
  const [branches, setBranches] = useState(() => app?.branch ? [{ name: app.branch, commit_sha: null, default: true }] : []);
  const [commits, setCommits] = useState([]);
  const [branch, setBranch] = useState(app?.branch || "main");
  const [commitSha, setCommitSha] = useState("");
  const [pickCommit, setPickCommit] = useState(false);
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [loadingCommits, setLoadingCommits] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open || !app) return;
    setBranch(app.branch || "main");
    setCommitSha("");
    setPickCommit(false);
    setLoadingBranches(true);
    setBranches((prev) => prev.length ? prev : [{ name: app.branch || "main", commit_sha: null, default: true }]);
    api.get("/github/branches", { params: { repo_url: app.repo_url } })
      .then((r) => setBranches((r.data && r.data.length) ? r.data : [{ name: app.branch || "main", commit_sha: null, default: true }]))
      .catch(() => setBranches([{ name: app.branch || "main", commit_sha: null, default: true }]))
      .finally(() => setLoadingBranches(false));
  }, [open, app]);

  useEffect(() => {
    if (!open || !app || !branch || !pickCommit) return;
    setLoadingCommits(true);
    api.get("/github/commits", { params: { repo_url: app.repo_url, branch } })
      .then((r) => setCommits(r.data || []))
      .catch(() => setCommits([]))
      .finally(() => setLoadingCommits(false));
  }, [open, app, branch, pickCommit]);

  const submit = async () => {
    if (!app) return;
    setSubmitting(true);
    try {
      const body = { branch };
      if (commitSha) body.commit_sha = commitSha;
      const { data } = await api.post(`/apps/${app.id}/redeploy`, body);
      toast.success(`Deployment started · ${branch}${commitSha ? ` @ ${commitSha.slice(0, 7)}` : ""}`);
      onDeployed?.(data);
      onClose?.();
    } catch (e) {
      toast.error(getApiErrorMessage(e));
    } finally { setSubmitting(false); }
  };

  if (!open) return null;
  const onlyMain = branches.length === 1 && branches[0]?.commit_sha === null;
  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" data-testid="deploy-modal">
      <div className="bg-elevated border border-white/10 w-full max-w-lg p-6 relative animate-rise">
        <button onClick={onClose} className="absolute top-3 right-3 text-zinc-500 hover:text-white" data-testid="deploy-modal-close">
          <X className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <Rocket className="h-5 w-5 text-brand" />
          <h3 className="font-display text-2xl">Deploy <span className="text-brand">{app?.name}</span></h3>
        </div>

        <div className="mt-2 text-xs font-mono text-zinc-500 flex items-center gap-2 break-all">
          <a href={app?.repo_url} target="_blank" rel="noreferrer" className="hover:text-brand inline-flex items-center gap-1">
            {(app?.repo_url || "").replace(/^https?:\/\//, "")} <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        {onlyMain && (
          <div className="mt-4 p-3 border border-signal-queued/30 bg-signal-queued/5 text-xs flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-signal-queued" />
            Connect GitHub in Settings to pick from real branches & commits.
          </div>
        )}

        <div className="mt-5 space-y-4">
          <div>
            <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 flex items-center gap-1">
              <GitBranch className="h-3 w-3" /> Branch
            </label>
            <select
              value={branch}
              onChange={(e) => { setBranch(e.target.value); setCommitSha(""); }}
              className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
              data-testid="deploy-branch-select"
            >
              {loadingBranches && <option>loading...</option>}
              {branches.map((b) => (
                <option key={b.name} value={b.name}>
                  {b.name}{b.default ? " · default" : ""}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={pickCommit} onChange={(e) => setPickCommit(e.target.checked)} data-testid="deploy-pick-commit" />
              <span className="font-mono text-xs uppercase tracking-wider text-zinc-400">Pin to a specific commit (advanced)</span>
            </label>
            {pickCommit && (
              <div className="mt-2">
                {loadingCommits ? (
                  <div className="text-xs font-mono text-zinc-500 flex items-center gap-2"><Loader2 className="h-3 w-3 animate-spin" /> loading commits...</div>
                ) : commits.length === 0 ? (
                  <div className="space-y-2">
                    <div className="text-xs font-mono text-zinc-500">No commits available (GitHub not connected). Paste a commit SHA manually:</div>
                    <input
                      value={commitSha}
                      onChange={(e) => setCommitSha(e.target.value)}
                      placeholder="abc1234... (full or short SHA)"
                      className="w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                      data-testid="deploy-commit-input"
                    />
                  </div>
                ) : (
                  <select
                    value={commitSha}
                    onChange={(e) => setCommitSha(e.target.value)}
                    className="w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                    data-testid="deploy-commit-select"
                  >
                    <option value="">latest on {branch}</option>
                    {commits.map((c) => (
                      <option key={c.sha} value={c.sha}>
                        {c.short_sha} · {c.message?.slice(0, 60)} · {c.author_name} · {timeAgo(c.author_date)}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </div>

          <div className="p-3 border border-white/10 bg-black/30 text-xs font-mono">
            <div className="text-brand">// will deploy</div>
            <div className="mt-1">
              <span className="inline-flex items-center gap-1"><GitBranch className="h-3 w-3" /> {branch}</span>
              {commitSha && <span className="ml-3 inline-flex items-center gap-1"><GitCommit className="h-3 w-3" /> {commitSha.slice(0, 7)}</span>}
              {!commitSha && <span className="ml-3 text-zinc-500">@ HEAD</span>}
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={submit}
              disabled={submitting || !branch}
              className="flex-1 inline-flex items-center justify-center gap-2 py-2.5 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition disabled:opacity-50 shadow-[0_0_20px_rgba(0,229,255,0.25)]"
              data-testid="deploy-submit"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <><Rocket className="h-4 w-4" /> Deploy</>}
            </button>
            <button onClick={onClose} className="px-4 py-2 border border-white/15">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}

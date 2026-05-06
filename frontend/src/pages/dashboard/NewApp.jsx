import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, getApiErrorMessage } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import { Github, Loader2, ChevronLeft, Boxes, ArrowRight, Lock } from "lucide-react";

const FRAMEWORKS = [
  { id: "nextjs", label: "Next.js", build: "yarn build", start: "yarn start", port: 3000 },
  { id: "node", label: "Node.js", build: "yarn build", start: "node dist/index.js", port: 3000 },
  { id: "static", label: "Static site", build: "yarn build", start: "", port: 80 },
];

export default function NewApp() {
  const { active } = useWorkspace();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [repos, setRepos] = useState([]);
  const [repoUrl, setRepoUrl] = useState("");
  const [framework, setFramework] = useState("nextjs");
  const [name, setName] = useState("");
  const [branch, setBranch] = useState("main");
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [envText, setEnvText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!active) return;
    api.get("/github/repos").then((r) => setRepos(r.data)).catch(() => setRepos([]));
    api.get("/projects", { params: { workspace_id: active.id } }).then((r) => setProjects(r.data));
  }, [active]);

  const pickRepo = (r) => {
    setRepoUrl(r.url);
    setName(r.name.split("/").pop());
    setBranch(r.default_branch);
    setFramework(r.framework);
    setStep(2);
  };

  const submit = async () => {
    if (!active) return;
    setSubmitting(true);
    setError("");
    const env_vars = {};
    envText.split(/\r?\n/).forEach((line) => {
      const i = line.indexOf("=");
      if (i > 0) env_vars[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    });
    try {
      const { data } = await api.post("/apps", {
        workspace_id: active.id,
        project_id: projectId || null,
        name,
        framework,
        repo_url: repoUrl,
        branch,
        env_vars,
      });
      navigate(`/app/apps/${data.id}`);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div data-testid="new-app-page">
      <div className="px-6 py-6 border-b border-white/[0.06]">
        <Link to="/app" className="text-xs font-mono text-zinc-500 hover:text-white inline-flex items-center gap-1">
          <ChevronLeft className="h-3 w-3" /> dashboard
        </Link>
        <h1 className="mt-3 font-display text-4xl font-semibold tracking-tighter">Deploy a new app</h1>
        <p className="mt-1 text-zinc-400 text-sm">Connect a repo, pick a framework, hit deploy.</p>
        <div className="mt-5 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500">
          <span className={step >= 1 ? "text-brand" : ""}>01 repo</span>
          <span>—</span>
          <span className={step >= 2 ? "text-brand" : ""}>02 configure</span>
          <span>—</span>
          <span className={step >= 3 ? "text-brand" : ""}>03 deploy</span>
        </div>
      </div>

      {step === 1 && (
        <div className="p-6">
          <div className="mb-4 p-4 border border-white/10 flex items-center gap-3">
            <Github className="h-5 w-5" />
            <div className="flex-1 text-sm">
              <div>GitHub OAuth not connected yet — using a sample repo list.</div>
              <div className="text-xs text-zinc-500 font-mono">Or paste a public repo URL below.</div>
            </div>
            <span className="text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500 inline-flex items-center gap-1">
              <Lock className="h-3 w-3" /> mocked
            </span>
          </div>

          <div className="border-l border-t border-white/[0.06] grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
            {repos.map((r) => (
              <button
                key={r.id}
                onClick={() => pickRepo(r)}
                className="text-left p-5 border-r border-b border-white/[0.06] hover:bg-white/[0.02] transition"
                data-testid={`repo-${r.id}`}
              >
                <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">{r.framework}</div>
                <div className="mt-1 font-display text-lg group-hover:text-brand">{r.name}</div>
                <div className="mt-2 flex items-center gap-2 text-xs font-mono text-zinc-500">
                  <Github className="h-3 w-3" /> {r.default_branch}
                </div>
              </button>
            ))}
          </div>

          <div className="mt-8 max-w-xl">
            <div className="text-xs font-mono uppercase tracking-[0.3em] text-zinc-500 mb-2">// or paste a repo url</div>
            <div className="flex gap-2">
              <input
                value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/user/repo"
                className="flex-1 bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                data-testid="repo-url-input"
              />
              <button
                disabled={!repoUrl}
                onClick={() => { setName(repoUrl.split("/").pop().replace(/\.git$/, "") || "app"); setStep(2); }}
                className="px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-40"
                data-testid="repo-url-continue"
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="p-6 max-w-3xl">
          <div className="mb-6 p-4 border border-white/10 bg-black/30 text-sm font-mono text-zinc-400">
            <span className="text-brand">repo:</span> {repoUrl}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">App name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none" data-testid="app-name-input" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Branch</label>
              <input value={branch} onChange={(e) => setBranch(e.target.value)} className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none" />
            </div>
          </div>

          <div className="mt-6">
            <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 mb-2 block">Framework</label>
            <div className="grid grid-cols-3 gap-2">
              {FRAMEWORKS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setFramework(f.id)}
                  className={`p-4 border ${framework === f.id ? "border-brand bg-brand/5 text-brand" : "border-white/10 text-zinc-400 hover:border-white/30"}`}
                  data-testid={`framework-${f.id}`}
                >
                  <Boxes className="h-4 w-4 mb-1" />
                  <div className="font-display text-base">{f.label}</div>
                </button>
              ))}
            </div>
          </div>

          {projects.length > 0 && (
            <div className="mt-6">
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Project (optional)</label>
              <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none">
                <option value="">No project</option>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          )}

          <div className="mt-6">
            <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Environment variables (KEY=value, one per line)</label>
            <textarea
              value={envText} onChange={(e) => setEnvText(e.target.value)} rows={4}
              className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
              placeholder={"NODE_ENV=production\nDATABASE_URL=..."}
              data-testid="env-vars-input"
            />
          </div>

          {error && <div className="mt-4 text-signal-failed text-sm">{error}</div>}

          <div className="mt-8 flex gap-3">
            <button onClick={() => setStep(1)} className="px-4 py-2 border border-white/15">Back</button>
            <button
              onClick={submit}
              disabled={submitting || !name || !repoUrl}
              className="inline-flex items-center gap-2 px-5 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-40 active:scale-95 transition shadow-[0_0_20px_rgba(0,229,255,0.25)]"
              data-testid="deploy-submit"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Deploy <ArrowRight className="h-4 w-4" /></>}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

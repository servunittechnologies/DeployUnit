import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, getApiErrorMessage } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import { Plus, FolderKanban, Boxes, X } from "lucide-react";

export default function Projects() {
  const { active } = useWorkspace();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [error, setError] = useState("");

  const load = () => {
    if (!active) return;
    setLoading(true);
    api.get("/projects", { params: { workspace_id: active.id } })
      .then((r) => setProjects(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(load, [active]);

  const create = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/projects", { workspace_id: active.id, name, description: desc });
      setName("");
      setDesc("");
      setOpen(false);
      load();
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  };

  return (
    <div className="px-6 py-6" data-testid="projects-page">
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// projects</div>
          <h1 className="font-display text-4xl font-semibold tracking-tighter">Group your apps</h1>
          <p className="mt-1 text-sm text-zinc-400">Use projects to group apps per client or initiative. Great for agencies.</p>
        </div>
        <button
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition"
          data-testid="projects-new"
        >
          <Plus className="h-4 w-4" /> New project
        </button>
      </div>

      {loading ? (
        <div className="text-zinc-500 font-mono text-sm">Loading projects…</div>
      ) : projects.length === 0 ? (
        <div className="border border-dashed border-white/10 p-16 text-center" data-testid="empty-projects">
          <FolderKanban className="h-10 w-10 text-zinc-600 mx-auto mb-4" />
          <h3 className="font-display text-2xl">No projects yet</h3>
          <p className="mt-2 text-zinc-400">Create a project to group apps together.</p>
        </div>
      ) : (
        <div className="border-t border-l border-white/[0.06] grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Link key={p.id} to={`/app/projects/${p.id}`} className="p-6 border-r border-b border-white/[0.06] hover:bg-white/[0.02] transition group" data-testid={`project-${p.slug}`}>
              <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">
                <FolderKanban className="h-3 w-3" /> project
              </div>
              <h3 className="mt-1 font-display text-xl group-hover:text-brand transition-colors">{p.name}</h3>
              {p.description && <p className="text-sm text-zinc-400 mt-1 line-clamp-2">{p.description}</p>}
              <div className="mt-5 flex items-center gap-2 text-xs font-mono text-zinc-500">
                <Boxes className="h-3.5 w-3.5" /> {p.app_count || 0} apps
              </div>
            </Link>
          ))}
        </div>
      )}

      {open && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-elevated border border-white/10 max-w-md w-full p-6 relative animate-rise">
            <button onClick={() => setOpen(false)} className="absolute top-3 right-3 text-zinc-500 hover:text-white"><X className="h-4 w-4" /></button>
            <h3 className="font-display text-2xl">New project</h3>
            <form onSubmit={create} className="mt-5 space-y-4">
              <div>
                <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Name</label>
                <input
                  required value={name} onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
                  placeholder="Client: Acme"
                  data-testid="project-name-input"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Description</label>
                <textarea
                  value={desc} onChange={(e) => setDesc(e.target.value)} rows={3}
                  className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm focus:border-brand outline-none"
                  placeholder="What this project covers..."
                />
              </div>
              {error && <div className="text-signal-failed text-sm">{error}</div>}
              <div className="flex gap-2">
                <button type="submit" className="flex-1 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90" data-testid="project-create-submit">Create</button>
                <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 border border-white/15">Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

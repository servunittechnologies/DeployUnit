import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../../lib/api";
import AppCard from "../../components/AppCard";
import { ChevronLeft } from "lucide-react";

export default function ProjectDetail() {
  const { id } = useParams();
  const [project, setProject] = useState(null);

  useEffect(() => {
    api.get(`/projects/${id}`).then((r) => setProject(r.data));
  }, [id]);

  if (!project) return <div className="p-6 text-zinc-500 font-mono text-sm">Loading client…</div>;

  return (
    <div data-testid="client-detail">
      <div className="px-6 py-6 border-b border-white/[0.06]">
        <Link to="/app/projects" className="text-xs font-mono text-zinc-500 hover:text-white inline-flex items-center gap-1">
          <ChevronLeft className="h-3 w-3" /> back to projects
        </Link>
        <h1 className="mt-3 font-display text-4xl font-semibold tracking-tighter">{project.name}</h1>
        {project.description && <p className="mt-1 text-zinc-400">{project.description}</p>}
      </div>

      {project.apps.length === 0 ? (
        <div className="m-6 border border-dashed border-white/10 p-16 text-center">
          <h3 className="font-display text-2xl">No apps in this client yet</h3>
          <p className="mt-2 text-zinc-400">Create an app and assign it to this client.</p>
        </div>
      ) : (
        <div className="border-l border-t border-white/[0.06] grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {project.apps.map((a) => <AppCard key={a.id} app={a} />)}
        </div>
      )}
    </div>
  );
}

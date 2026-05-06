import { Link } from "react-router-dom";
import StatusBadge from "./StatusBadge";
import { GitBranch, Boxes, ArrowUpRight } from "lucide-react";

function timeAgo(iso) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

const FW_LABELS = {
  nextjs: "Next.js",
  node: "Node",
  static: "Static",
};

export default function AppCard({ app }) {
  return (
    <Link
      to={`/app/apps/${app.id}`}
      className="group relative block p-6 hover:bg-white/[0.02] transition-colors border-r border-b border-white/[0.07]"
      data-testid={`app-card-${app.slug}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1 text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono">
            <Boxes className="h-3 w-3" />
            {FW_LABELS[app.framework] || app.framework}
          </div>
          <h3 className="font-display text-lg font-medium tracking-tight truncate group-hover:text-brand transition-colors">
            {app.name}
          </h3>
          {app.primary_url ? (
            <div className="mt-1 text-xs font-mono text-zinc-500 truncate">{app.primary_url.replace(/^https?:\/\//, "")}</div>
          ) : (
            <div className="mt-1 text-xs font-mono text-zinc-600">no domain yet</div>
          )}
        </div>
        <ArrowUpRight className="h-4 w-4 text-zinc-600 group-hover:text-brand transition-colors" />
      </div>
      <div className="mt-6 flex items-center justify-between">
        <StatusBadge status={app.status} />
        <div className="flex items-center gap-3 text-[11px] font-mono text-zinc-500">
          <GitBranch className="h-3 w-3" />
          {app.branch || "main"} · {timeAgo(app.last_deploy_at || app.created_at)}
        </div>
      </div>
    </Link>
  );
}

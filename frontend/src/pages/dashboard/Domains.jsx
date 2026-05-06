import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import StatusBadge from "../../components/StatusBadge";
import AddDomainWizard from "../../components/AddDomainWizard";
import { Globe, ExternalLink, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function Domains() {
  const { active } = useWorkspace();
  const [domains, setDomains] = useState([]);
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wizardOpen, setWizardOpen] = useState(false);

  const load = () => {
    if (!active) return;
    setLoading(true);
    Promise.all([
      api.get("/domains", { params: { workspace_id: active.id } }),
      api.get("/apps", { params: { workspace_id: active.id } }),
    ]).then(([d, a]) => {
      setDomains(d.data);
      setApps(a.data);
    }).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [active]);

  const removeDomain = async (id, domain) => {
    if (!window.confirm(`Remove ${domain}? The DNS record on your side stays put — you may want to remove it too.`)) return;
    try {
      await api.delete(`/domains/${id}`);
      toast.success(`${domain} removed`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Remove failed");
    }
  };

  const appById = Object.fromEntries(apps.map((a) => [a.id, a]));

  return (
    <div className="px-6 py-6" data-testid="domains-page">
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// domains</div>
          <h1 className="font-display text-4xl font-semibold tracking-tighter">Custom domains</h1>
          <p className="mt-1 text-sm text-zinc-400">Link any domain to your app. SSL is issued automatically.</p>
        </div>
        <button
          onClick={() => setWizardOpen(true)}
          disabled={apps.length === 0}
          className="magnetic-btn inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50"
          data-testid="domains-add-btn"
        >
          <Plus className="h-4 w-4" /> Add domain
        </button>
      </div>

      {loading ? (
        <div className="text-zinc-500 font-mono text-sm">Loading…</div>
      ) : domains.length === 0 ? (
        <div className="border border-dashed border-white/10 p-16 text-center">
          <Globe className="h-10 w-10 text-zinc-600 mx-auto mb-4" />
          <h3 className="font-display text-2xl">No domains linked yet</h3>
          <p className="mt-2 text-zinc-400">Link your first custom domain and get free SSL.</p>
          {apps.length > 0 ? (
            <button
              onClick={() => setWizardOpen(true)}
              className="mt-5 inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90"
              data-testid="domains-add-empty"
            >
              <Plus className="h-4 w-4" /> Add your first domain
            </button>
          ) : (
            <p className="mt-2 text-xs text-zinc-500">Create an app first, then link a domain.</p>
          )}
        </div>
      ) : (
        <div className="border-t border-l border-white/[0.06]">
          {domains.map((d) => (
            <div key={d.id} className="flex items-center justify-between p-4 border-r border-b border-white/[0.06]" data-testid={`domain-row-${d.id}`}>
              <div className="flex items-center gap-3">
                <Globe className="h-4 w-4 text-zinc-500" />
                <div>
                  <a href={`https://${d.domain}`} target="_blank" rel="noreferrer" className="font-mono text-sm hover:text-brand">{d.domain}</a>
                  <div className="text-xs font-mono text-zinc-500 mt-0.5">
                    {appById[d.app_id]?.name || "—"}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={d.dns_verified ? "live" : "pending"} />
                <span className="text-xs font-mono text-zinc-500">SSL {d.ssl_status}</span>
                {appById[d.app_id] && (
                  <Link to={`/app/apps/${d.app_id}`} className="text-xs font-mono text-zinc-400 hover:text-brand inline-flex items-center gap-1">
                    manage <ExternalLink className="h-3 w-3" />
                  </Link>
                )}
                <button
                  onClick={() => removeDomain(d.id, d.domain)}
                  className="text-xs text-zinc-500 hover:text-signal-failed"
                  data-testid={`domain-delete-${d.id}`}
                  title="Remove domain"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <AddDomainWizard
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onCreated={load}
        apps={apps}
      />
    </div>
  );
}

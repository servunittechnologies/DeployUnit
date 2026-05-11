import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, getApiErrorMessage } from "../../lib/api";
import { useAuth } from "../../contexts/AuthContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import {
  Save, UserPlus, Trash2, Building2, ExternalLink, ArrowRight,
  Users, FileClock, Shield,
} from "lucide-react";
import { toast } from "sonner";

export default function Settings() {
  const { user } = useAuth();
  const { active, refresh: refreshWorkspaces, setActive, workspaces } = useWorkspace();
  const nav = useNavigate();

  // Workspace details
  const [wsName, setWsName] = useState(active?.name || "");
  const [wsType, setWsType] = useState(active?.type || "solo");
  const [wsBusy, setWsBusy] = useState(false);
  const [wsUsage, setWsUsage] = useState(null);

  // Members
  const [members, setMembers] = useState([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("developer");

  useEffect(() => {
    if (active) {
      setWsName(active.name);
      setWsType(active.type || "solo");
    }
  }, [active]);

  useEffect(() => {
    if (!active) return;
    api.get(`/workspaces/${active.id}/usage`).then((r) => setWsUsage(r.data)).catch(() => setWsUsage(null));
  }, [active]);

  const loadMembers = () => {
    if (!active) return;
    api.get(`/workspaces/${active.id}/members`).then((r) => setMembers(r.data));
  };
  useEffect(loadMembers, [active]);

  const saveWorkspace = async () => {
    if (!active) return;
    if (!wsName.trim()) { toast.error("Name required"); return; }
    setWsBusy(true);
    try {
      await api.put(`/workspaces/${active.id}`, { name: wsName.trim(), type: wsType });
      await refreshWorkspaces();
      toast.success("Workspace updated");
    } catch (e) { toast.error(getApiErrorMessage(e)); }
    finally { setWsBusy(false); }
  };

  const deleteWorkspace = async () => {
    if (!active) return;
    const apps = wsUsage?.usage?.apps ?? 0;
    const dbs = wsUsage?.usage?.databases ?? 0;
    const hasResources = apps > 0 || dbs > 0;
    const warning = hasResources
      ? `Delete "${active.name}"?\n\nThis workspace has ${apps} app(s) and ${dbs} database(s) — they will be PERMANENTLY DESTROYED on the build engine. This cannot be undone.\n\nType the workspace name to confirm:`
      : `Delete "${active.name}"?\n\nThis cannot be undone. Type the workspace name to confirm:`;
    const confirmation = window.prompt(warning);
    if (confirmation !== active.name) {
      if (confirmation !== null) toast.error("Name did not match — not deleted");
      return;
    }
    setWsBusy(true);
    try {
      await api.delete(`/workspaces/${active.id}`, { params: hasResources ? { force: true } : {} });
      toast.success("Workspace deleted");
      const others = (workspaces || []).filter((w) => w.id !== active.id);
      if (others[0] && setActive) setActive(others[0].id);
      await refreshWorkspaces();
      nav("/app");
    } catch (e) { toast.error(getApiErrorMessage(e)); setWsBusy(false); }
  };

  const invite = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/workspaces/${active.id}/members`, { email: inviteEmail, role: inviteRole });
      setInviteEmail("");
      loadMembers();
      toast.success("Invite sent");
    } catch (err) { toast.error(getApiErrorMessage(err)); }
  };

  const removeMember = async (uid) => {
    await api.delete(`/workspaces/${active.id}/members/${uid}`);
    loadMembers();
  };

  if (!active) {
    return <div className="px-6 py-10 text-sm font-mono text-zinc-500">No workspace selected.</div>;
  }

  const plan = wsUsage?.plan;
  const usage = wsUsage?.usage || {};

  return (
    <div className="px-6 py-6 max-w-4xl space-y-8" data-testid="settings-page">
      {/* Hero */}
      <div>
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// workspace settings</div>
        <h1 className="font-display text-4xl font-semibold tracking-tighter">{active.name}</h1>
        <p className="text-xs text-zinc-500 mt-2 max-w-2xl">
          Settings for this workspace only — name, type, members. Plan, credits, billing and
          notification preferences are personal and live on your <Link to="/app/account" className="text-brand hover:underline">Account page</Link>.
        </p>
      </div>

      {/* At-a-glance — workspace's slice of the account plan */}
      {wsUsage && plan && (
        <div className="border border-white/[0.06] bg-elevated/30 p-5" data-testid="ws-snapshot">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div className="flex items-center gap-3">
              <span className="px-2 py-1 border border-brand/40 text-brand uppercase text-[10px] font-mono tracking-wider">
                {plan.name} plan
              </span>
              <span className="text-xs text-zinc-500 font-mono">— shared across all your workspaces</span>
            </div>
            <Link
              to="/app/account#plan"
              className="text-xs font-mono text-brand hover:underline inline-flex items-center gap-1"
              data-testid="ws-manage-plan"
            >
              Manage plan <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.06] border border-white/[0.06]">
            <Tile label="Apps in this ws" v={usage.apps ?? 0} />
            <Tile label="Domains in this ws" v={usage.domains ?? 0} />
            <Tile label="Databases in this ws" v={usage.databases ?? 0} />
            <Tile label="Team in this ws" v={usage.team ?? members.length ?? 1} />
          </div>
        </div>
      )}

      {/* General */}
      <section className="border border-white/[0.06] p-6 space-y-4" data-testid="workspace-section">
        <div className="flex items-center gap-2">
          <Building2 className="h-4 w-4 text-brand" />
          <h2 className="font-display text-xl">General</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Name</label>
            <input
              value={wsName}
              onChange={(e) => setWsName(e.target.value)}
              className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
              data-testid="ws-name-input"
            />
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Type</label>
            <select
              value={wsType}
              onChange={(e) => setWsType(e.target.value)}
              className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
              data-testid="ws-type-select"
            >
              <option value="solo" className="bg-black">Solo (personal projects)</option>
              <option value="agency" className="bg-black">Agency (client work)</option>
            </select>
          </div>
        </div>
        <button
          onClick={saveWorkspace}
          disabled={wsBusy || (wsName === active.name && wsType === (active.type || "solo"))}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-40"
          data-testid="ws-save"
        >
          <Save className="h-4 w-4" /> Save changes
        </button>
      </section>

      {/* Members */}
      <section className="border border-white/[0.06] p-6 space-y-4" data-testid="ws-members-section">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-brand" />
          <h2 className="font-display text-xl">Team members</h2>
        </div>
        <p className="text-xs text-zinc-500">
          Invite collaborators to <strong>{active.name}</strong>. Members must already have a DeployUnit account.
        </p>
        <form onSubmit={invite} className="flex gap-2 flex-wrap">
          <input
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="teammate@studio.io"
            className="flex-1 min-w-[200px] bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="invite-email-input"
          />
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
            className="bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
          >
            <option value="admin">Admin</option>
            <option value="developer">Developer</option>
            <option value="billing">Billing</option>
            <option value="viewer">Viewer</option>
          </select>
          <button type="submit" className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium" data-testid="invite-submit">
            <UserPlus className="h-4 w-4" /> Add
          </button>
        </form>
        <div className="border border-white/[0.06] divide-y divide-white/[0.06]">
          {members.map((m) => (
            <div key={m.id} className="flex items-center justify-between p-3" data-testid={`member-${m.user_id}`}>
              <div>
                <div className="text-sm">{m.name || m.email}</div>
                <div className="text-xs font-mono text-zinc-500">{m.email} · {m.role}</div>
              </div>
              {m.role !== "owner" && (
                <button onClick={() => removeMember(m.user_id)} className="text-xs font-mono text-signal-failed hover:underline inline-flex items-center gap-1" data-testid={`member-remove-${m.user_id}`}>
                  <Trash2 className="h-3 w-3" /> remove
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Audit log quick link */}
      <section className="border border-white/[0.06] p-6 flex items-center justify-between gap-4" data-testid="ws-audit-section">
        <div className="flex items-center gap-3">
          <FileClock className="h-5 w-5 text-zinc-400" />
          <div>
            <div className="font-display text-base">Activity & audit log</div>
            <div className="text-xs text-zinc-500">Every action in this workspace is recorded for compliance.</div>
          </div>
        </div>
        <Link
          to="/app/audit"
          className="text-xs font-mono text-brand hover:underline inline-flex items-center gap-1"
          data-testid="ws-audit-link"
        >
          Open audit log <ArrowRight className="h-3 w-3" />
        </Link>
      </section>

      {/* Danger zone */}
      <section className="border border-signal-failed/30 p-6 space-y-3" data-testid="ws-danger-section">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-signal-failed" />
          <h2 className="font-display text-xl text-signal-failed">Danger zone</h2>
        </div>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="text-sm">Delete this workspace</div>
            <div className="text-xs text-zinc-500 mt-1">
              {(usage.apps ?? 0) > 0 || (usage.databases ?? 0) > 0
                ? <span className="text-signal-failed">Will destroy {usage.apps ?? 0} app(s) and {usage.databases ?? 0} database(s) on the build engine.</span>
                : "This workspace is empty — safe to delete."}
            </div>
          </div>
          <button
            onClick={deleteWorkspace}
            disabled={wsBusy}
            className="inline-flex items-center gap-2 px-3 py-2 border border-signal-failed/40 text-signal-failed hover:bg-signal-failed/10 text-sm disabled:opacity-50"
            data-testid="ws-delete"
          >
            <Trash2 className="h-4 w-4" /> Delete workspace
          </button>
        </div>
      </section>
    </div>
  );
}

function Tile({ label, v }) {
  return (
    <div className="bg-background p-3">
      <div className="text-[10px] uppercase tracking-[0.25em] font-mono text-zinc-500">{label}</div>
      <div className="mt-1 font-display text-base text-zinc-200">{v}</div>
    </div>
  );
}

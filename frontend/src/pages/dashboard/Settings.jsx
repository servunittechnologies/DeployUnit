import { useEffect, useState } from "react";
import { api, getApiErrorMessage } from "../../lib/api";
import { useAuth } from "../../contexts/AuthContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import { Save, UserPlus, Trash2 } from "lucide-react";

export default function Settings() {
  const { user, refresh } = useAuth();
  const { active } = useWorkspace();
  const [name, setName] = useState(user?.name || "");
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwError, setPwError] = useState("");
  const [pwSuccess, setPwSuccess] = useState("");
  const [profileMsg, setProfileMsg] = useState("");

  const [members, setMembers] = useState([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("developer");
  const [inviteError, setInviteError] = useState("");

  const [integ, setInteg] = useState(null);

  useEffect(() => {
    setName(user?.name || "");
  }, [user]);

  const loadMembers = () => {
    if (!active) return;
    api.get(`/workspaces/${active.id}/members`).then((r) => setMembers(r.data));
  };

  useEffect(loadMembers, [active]);
  useEffect(() => {
    api.get("/integrations/health").then((r) => setInteg(r.data)).catch(() => setInteg(null));
  }, []);

  const saveProfile = async () => {
    setProfileMsg("");
    try {
      await api.patch("/users/me", { name });
      await refresh();
      setProfileMsg("Saved.");
      setTimeout(() => setProfileMsg(""), 2500);
    } catch (e) {
      setProfileMsg(getApiErrorMessage(e));
    }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    setPwError("");
    setPwSuccess("");
    try {
      await api.post("/users/me/change-password", { current_password: currentPw, new_password: newPw });
      setPwSuccess("Password updated.");
      setCurrentPw("");
      setNewPw("");
    } catch (e) { setPwError(getApiErrorMessage(e)); }
  };

  const invite = async (e) => {
    e.preventDefault();
    setInviteError("");
    try {
      await api.post(`/workspaces/${active.id}/members`, { email: inviteEmail, role: inviteRole });
      setInviteEmail("");
      loadMembers();
    } catch (e) { setInviteError(getApiErrorMessage(e)); }
  };

  const removeMember = async (uid) => {
    await api.delete(`/workspaces/${active.id}/members/${uid}`);
    loadMembers();
  };

  return (
    <div className="px-6 py-6 max-w-3xl space-y-10" data-testid="settings-page">
      <div>
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// settings</div>
        <h1 className="font-display text-4xl font-semibold tracking-tighter">Account & workspace</h1>
      </div>

      {/* Profile */}
      <section className="border border-white/[0.06] p-6 space-y-3">
        <h2 className="font-display text-xl">Profile</h2>
        <div>
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Email</label>
          <div className="mt-1 font-mono text-sm">{user?.email}</div>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none" data-testid="profile-name-input" />
        </div>
        <div className="flex items-center gap-3">
          <button onClick={saveProfile} className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90" data-testid="profile-save">
            <Save className="h-4 w-4" /> Save
          </button>
          {profileMsg && <span className="text-xs font-mono text-signal-live">{profileMsg}</span>}
        </div>
      </section>

      {/* Password */}
      <section className="border border-white/[0.06] p-6 space-y-3">
        <h2 className="font-display text-xl">Change password</h2>
        <form onSubmit={changePassword} className="space-y-3">
          <input
            type="password" required value={currentPw} onChange={(e) => setCurrentPw(e.target.value)}
            placeholder="current password"
            className="w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="settings-current-pw"
          />
          <input
            type="password" required minLength={6} value={newPw} onChange={(e) => setNewPw(e.target.value)}
            placeholder="new password (min 6)"
            className="w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="settings-new-pw"
          />
          {pwError && <div className="text-signal-failed text-sm">{pwError}</div>}
          {pwSuccess && <div className="text-signal-live text-sm">{pwSuccess}</div>}
          <button type="submit" className="px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90" data-testid="settings-pw-save">Update password</button>
        </form>
      </section>

      {/* Members */}
      <section className="border border-white/[0.06] p-6 space-y-3">
        <h2 className="font-display text-xl">Workspace members</h2>
        <p className="text-xs text-zinc-500">{active?.name} · {active?.type}</p>
        <form onSubmit={invite} className="flex gap-2">
          <input
            value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="teammate@studio.io"
            className="flex-1 bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="invite-email-input"
          />
          <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} className="bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none">
            <option value="admin">Admin</option>
            <option value="developer">Developer</option>
            <option value="billing">Billing</option>
            <option value="viewer">Viewer</option>
          </select>
          <button type="submit" className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium" data-testid="invite-submit">
            <UserPlus className="h-4 w-4" /> Add
          </button>
        </form>
        {inviteError && <div className="text-signal-failed text-sm">{inviteError}</div>}
        <div className="border-t border-l border-white/[0.06] mt-3">
          {members.map((m) => (
            <div key={m.id} className="flex items-center justify-between p-3 border-r border-b border-white/[0.06]">
              <div>
                <div className="text-sm">{m.name || m.email}</div>
                <div className="text-xs font-mono text-zinc-500">{m.email} · {m.role}</div>
              </div>
              {m.role !== "owner" && (
                <button onClick={() => removeMember(m.user_id)} className="text-xs font-mono text-signal-failed hover:underline inline-flex items-center gap-1">
                  <Trash2 className="h-3 w-3" /> remove
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Integrations health */}
      <section className="border border-white/[0.06] p-6 space-y-3">
        <h2 className="font-display text-xl">Integrations</h2>
        <p className="text-xs text-zinc-500">Status of platform-level integrations.</p>
        <div className="grid grid-cols-2 gap-px bg-white/[0.06] border border-white/[0.06]">
          {[
            ["coolify", "Coolify (deploy engine)"],
            ["whmcs", "WHMCS (billing)"],
          ].map(([k, label]) => (
            <div key={k} className="bg-background p-4 flex items-center justify-between">
              <div>
                <div className="text-sm">{label}</div>
                <div className="text-xs font-mono text-zinc-500">
                  {integ?.[k]?.configured ? "configured" : "not configured"}
                </div>
              </div>
              <span className={`h-2 w-2 rounded-full ${integ?.[k]?.ok ? "bg-signal-live animate-ping-soft" : "bg-zinc-600"}`} />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

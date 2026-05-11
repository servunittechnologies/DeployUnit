import { useEffect, useState } from "react";
import { api, getApiErrorMessage } from "../../lib/api";
import { useAuth } from "../../contexts/AuthContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import GitHubButton from "../../components/GitHubButton";
import { Save, UserPlus, Trash2, Github, CheckCircle2, Send, MessageSquare, Phone, Mail } from "lucide-react";

const EVENT_LABELS = {
  deploy_failed: "Deploy failed",
  deploy_succeeded: "Deploy succeeded",
  app_down: "App down (uptime)",
  app_recovered: "App recovered",
  build_warning: "Build warning",
  domain_expiring: "Domain expiring soon",
  credits_low: "Credits running low",
};

const CHANNEL_META = {
  sms: { label: "SMS", icon: Phone, hint: "1–2 cr per send (EU = 1 cr)" },
  whatsapp: { label: "WhatsApp", icon: MessageSquare, hint: "1 cr per send" },
  email: { label: "Email", icon: Mail, hint: "Free (in-app)" },
};

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

  // Notification preferences (Sprint 3 — Twilio SMS/WhatsApp + email)
  const [prefsLoaded, setPrefsLoaded] = useState(false);
  const [phoneE164, setPhoneE164] = useState("");
  const [channelMatrix, setChannelMatrix] = useState({}); // {event_type: {sms, whatsapp, email}}
  const [supportedEvents, setSupportedEvents] = useState([]);
  const [prefsMsg, setPrefsMsg] = useState("");
  const [prefsErr, setPrefsErr] = useState("");
  const [testBusy, setTestBusy] = useState(null); // "sms" | "whatsapp" | null
  const [testMsg, setTestMsg] = useState("");
  const [testErr, setTestErr] = useState("");

  useEffect(() => {
    setName(user?.name || "");
  }, [user]);

  const loadMembers = () => {
    if (!active) return;
    api.get(`/workspaces/${active.id}/members`).then((r) => setMembers(r.data));
  };

  useEffect(loadMembers, [active]);

  // Load notification prefs once on mount
  useEffect(() => {
    api.get("/notifications/prefs").then((r) => {
      const data = r.data || {};
      setPhoneE164(data.phone_e164 || "");
      const events = data.supported_events || [];
      setSupportedEvents(events);
      const channels = data.channels || {};
      const matrix = {};
      events.forEach((ev) => {
        matrix[ev] = {
          sms: (channels.sms || []).includes(ev),
          whatsapp: (channels.whatsapp || []).includes(ev),
          email: (channels.email || []).includes(ev),
        };
      });
      setChannelMatrix(matrix);
      setPrefsLoaded(true);
    }).catch(() => setPrefsLoaded(true));
  }, []);

  const toggleEventChannel = (event, channel) => {
    setChannelMatrix((m) => ({
      ...m,
      [event]: { ...(m[event] || {}), [channel]: !(m[event] || {})[channel] },
    }));
  };

  const savePrefs = async () => {
    setPrefsMsg("");
    setPrefsErr("");
    // Convert matrix back to {sms: [events], whatsapp: [events], email: [events]}
    const channels = { sms: [], whatsapp: [], email: [] };
    Object.entries(channelMatrix).forEach(([ev, ch]) => {
      ["sms", "whatsapp", "email"].forEach((c) => {
        if (ch?.[c]) channels[c].push(ev);
      });
    });
    try {
      await api.put("/notifications/prefs", {
        phone_e164: phoneE164.trim() || null,
        channels,
      });
      setPrefsMsg("Preferences saved.");
      setTimeout(() => setPrefsMsg(""), 2500);
    } catch (e) {
      setPrefsErr(getApiErrorMessage(e));
    }
  };

  const sendTest = async (channel) => {
    if (!active) return;
    setTestBusy(channel);
    setTestMsg("");
    setTestErr("");
    try {
      const r = await api.post("/notifications/test", { workspace_id: active.id, channel });
      const result = (r.data?.results || [])[0];
      if (!result) {
        setTestErr(`No ${channel} preference enabled for "deploy_succeeded" — toggle it on first.`);
      } else if (result.status === "sent") {
        setTestMsg(`Test ${channel} sent (cost: ${result.cost} cr). Check your phone.`);
      } else if (result.status === "insufficient_credits") {
        setTestErr("Insufficient credits. Top up your wallet first.");
      } else if (result.status === "skipped") {
        setTestErr(`Skipped — ${result.error || "channel not ready"}.`);
      } else {
        setTestErr(`Test ${channel} ${result.status}: ${result.error || ""}`);
      }
    } catch (e) {
      setTestErr(getApiErrorMessage(e));
    } finally {
      setTestBusy(null);
    }
  };

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

      {/* Notification preferences (Sprint 3 — SMS/WhatsApp via Twilio + Email) */}
      <section className="border border-white/[0.06] p-6 space-y-4" data-testid="notif-prefs-section">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-display text-xl">Notification preferences</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Get pinged on your phone when something breaks. SMS &amp; WhatsApp are billed from your{" "}
              <span className="text-brand">credit wallet</span>; email is free.
            </p>
          </div>
        </div>

        {/* Phone */}
        <div>
          <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">
            Phone (E.164, e.g. +32475123456)
          </label>
          <input
            value={phoneE164}
            onChange={(e) => setPhoneE164(e.target.value)}
            placeholder="+32475123456"
            inputMode="tel"
            className="mt-1 w-full bg-black border border-white/10 px-3 py-2 text-sm font-mono focus:border-brand outline-none"
            data-testid="notif-phone-input"
          />
          <div className="text-[10px] font-mono text-zinc-600 mt-1">
            Must start with <span className="text-brand">+</span> and country code. Required for SMS/WhatsApp.
          </div>
        </div>

        {/* Per-event matrix */}
        <div className="border border-white/[0.06]">
          <div className="grid grid-cols-[1fr_72px_72px_72px] text-[10px] uppercase tracking-[0.25em] font-mono text-zinc-500 border-b border-white/[0.06]">
            <div className="p-3">Event</div>
            {["sms", "whatsapp", "email"].map((c) => {
              const Icon = CHANNEL_META[c].icon;
              return (
                <div key={c} className="p-3 text-center flex flex-col items-center gap-1">
                  <Icon className="h-3 w-3" />
                  {CHANNEL_META[c].label}
                </div>
              );
            })}
          </div>
          {prefsLoaded && supportedEvents.length === 0 && (
            <div className="p-4 text-xs font-mono text-zinc-500">No event types available.</div>
          )}
          {supportedEvents.map((ev) => (
            <div
              key={ev}
              className="grid grid-cols-[1fr_72px_72px_72px] border-b border-white/[0.06] last:border-b-0 items-center"
              data-testid={`notif-event-row-${ev}`}
            >
              <div className="p-3">
                <div className="text-sm">{EVENT_LABELS[ev] || ev}</div>
                <div className="text-[10px] font-mono text-zinc-600">{ev}</div>
              </div>
              {["sms", "whatsapp", "email"].map((c) => {
                const on = !!channelMatrix[ev]?.[c];
                return (
                  <div key={c} className="p-3 flex justify-center">
                    <button
                      type="button"
                      onClick={() => toggleEventChannel(ev, c)}
                      className={`h-6 w-11 relative rounded-full transition-colors ${on ? "bg-brand" : "bg-white/[0.08] hover:bg-white/[0.14]"}`}
                      data-testid={`notif-toggle-${ev}-${c}`}
                      aria-pressed={on}
                      aria-label={`${EVENT_LABELS[ev] || ev} via ${CHANNEL_META[c].label}`}
                    >
                      <span
                        className={`absolute top-0.5 h-5 w-5 rounded-full bg-black transition-all ${on ? "left-[22px]" : "left-0.5"}`}
                      />
                    </button>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        <div className="text-[10px] font-mono text-zinc-600 leading-relaxed">
          Pricing: <span className="text-brand">SMS</span> EU = 1 cr (~€0.10), intl = 2 cr ·{" "}
          <span className="text-brand">WhatsApp</span> = 1 cr · <span className="text-brand">Email</span> = free
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={savePrefs}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand text-brand-fg font-medium hover:bg-brand/90"
            data-testid="notif-prefs-save"
          >
            <Save className="h-4 w-4" /> Save preferences
          </button>
          <button
            onClick={() => sendTest("sms")}
            disabled={testBusy === "sms" || !phoneE164}
            className="inline-flex items-center gap-2 px-3 py-2 border border-white/10 text-sm font-mono hover:border-brand/50 disabled:opacity-40 disabled:cursor-not-allowed"
            data-testid="notif-test-sms"
          >
            <Send className="h-3 w-3" /> {testBusy === "sms" ? "sending…" : "Test SMS"}
          </button>
          <button
            onClick={() => sendTest("whatsapp")}
            disabled={testBusy === "whatsapp" || !phoneE164}
            className="inline-flex items-center gap-2 px-3 py-2 border border-white/10 text-sm font-mono hover:border-brand/50 disabled:opacity-40 disabled:cursor-not-allowed"
            data-testid="notif-test-whatsapp"
          >
            <Send className="h-3 w-3" /> {testBusy === "whatsapp" ? "sending…" : "Test WhatsApp"}
          </button>
          {prefsMsg && <span className="text-xs font-mono text-signal-live">{prefsMsg}</span>}
          {prefsErr && <span className="text-xs font-mono text-signal-failed">{prefsErr}</span>}
          {testMsg && <span className="text-xs font-mono text-signal-live" data-testid="notif-test-success">{testMsg}</span>}
          {testErr && <span className="text-xs font-mono text-signal-failed" data-testid="notif-test-error">{testErr}</span>}
        </div>
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

      {/* Integrations — user-facing only (GitHub) */}
      <section className="border border-white/[0.06] p-6 space-y-3">
        <h2 className="font-display text-xl">Connected accounts</h2>
        <p className="text-xs text-zinc-500">Link your developer accounts to unlock automated deploys.</p>

        {/* GitHub OAuth — per-user */}
        <div className="bg-elevated/30 border border-white/[0.06] p-4 mt-2">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <Github className="h-5 w-5" />
              <div>
                <div className="text-sm font-medium flex items-center gap-2">
                  GitHub
                  {user?.github_login && <CheckCircle2 className="h-4 w-4 text-signal-live" />}
                </div>
                <div className="text-xs font-mono text-zinc-500">
                  {user?.github_login ? `Connected as @${user.github_login}` : "Not connected — link to deploy your repos."}
                </div>
              </div>
            </div>
            <div className="min-w-[220px]">
              {user?.github_login ? (
                <button
                  onClick={async () => {
                    if (!window.confirm("Disconnect GitHub from this account?")) return;
                    await api.post("/auth/github/disconnect");
                    await refresh();
                  }}
                  className="w-full inline-flex items-center justify-center gap-2 py-2 border border-signal-failed/40 text-signal-failed hover:bg-signal-failed/10"
                  data-testid="github-disconnect"
                >
                  <Trash2 className="h-4 w-4" /> Disconnect
                </button>
              ) : (
                <GitHubButton link label="Connect GitHub" testId="settings-connect-github" />
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

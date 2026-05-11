/**
 * Reset password — consumes the one-time token from the URL.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { Lock, ArrowLeft, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [pwd, setPwd] = useState("");
  const [pwd2, setPwd2] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    if (!token) setErr("Missing reset token in the URL.");
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (pwd.length < 6) { setErr("Password must be at least 6 characters"); return; }
    if (pwd !== pwd2) { setErr("Passwords do not match"); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/auth/reset-password`, { token, new_password: pwd }, { withCredentials: true });
      setDone(true);
      setTimeout(() => nav("/login"), 2500);
    } catch (e) { setErr(e?.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6" data-testid="reset-password-page">
      <div className="w-full max-w-md">
        <Link to="/login" className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-brand mb-6">
          <ArrowLeft className="h-3 w-3" /> back to sign in
        </Link>
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// reset</div>
        <h1 className="font-display text-4xl font-semibold tracking-tighter">Choose a new password.</h1>

        {done ? (
          <div className="mt-8 border border-signal-live/30 bg-signal-live/5 p-5 flex items-start gap-3" data-testid="reset-password-done">
            <CheckCircle2 className="h-5 w-5 text-signal-live shrink-0 mt-0.5" />
            <div>
              <div className="text-sm">Password updated. Redirecting to sign-in…</div>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">New password</label>
              <div className="mt-1 relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                <input
                  type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} required minLength={6}
                  className="w-full bg-black border border-white/10 pl-10 pr-3 py-2.5 text-sm font-mono focus:border-brand outline-none"
                  data-testid="reset-password-pwd"
                />
              </div>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Confirm</label>
              <div className="mt-1 relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                <input
                  type="password" value={pwd2} onChange={(e) => setPwd2(e.target.value)} required minLength={6}
                  className="w-full bg-black border border-white/10 pl-10 pr-3 py-2.5 text-sm font-mono focus:border-brand outline-none"
                  data-testid="reset-password-pwd2"
                />
              </div>
            </div>
            {err && <div className="text-xs font-mono text-signal-failed" data-testid="reset-password-error">{err}</div>}
            <button
              type="submit" disabled={busy || !token}
              className="w-full px-4 py-3 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50"
              data-testid="reset-password-submit"
            >
              {busy ? "Updating…" : "Set new password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

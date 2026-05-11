/**
 * Forgot password — request a reset link via email.
 * Always shows the success state to prevent email enumeration.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { Mail, ArrowLeft, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!email.includes("@")) return;
    setBusy(true);
    try {
      await axios.post(`${API}/auth/forgot-password`, { email }, { withCredentials: true });
      setSent(true);
    } catch {
      // Endpoint always returns 200 — only network errors hit here.
      setSent(true);
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6" data-testid="forgot-password-page">
      <div className="w-full max-w-md">
        <Link to="/login" className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-brand mb-6">
          <ArrowLeft className="h-3 w-3" /> back to sign in
        </Link>
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-2">// reset</div>
        <h1 className="font-display text-4xl font-semibold tracking-tighter">Forgot your password?</h1>
        <p className="mt-2 text-sm text-zinc-400">Type your email and we'll send a reset link. Valid for 60 minutes.</p>

        {sent ? (
          <div className="mt-8 border border-signal-live/30 bg-signal-live/5 p-5 flex items-start gap-3" data-testid="forgot-password-sent">
            <CheckCircle2 className="h-5 w-5 text-signal-live shrink-0 mt-0.5" />
            <div>
              <div className="text-sm">If <span className="text-brand font-mono">{email}</span> is registered, a reset link is on its way.</div>
              <div className="text-[11px] font-mono text-zinc-500 mt-2">Check spam if it doesn't arrive in 2 minutes.</div>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Email</label>
              <div className="mt-1 relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="w-full bg-black border border-white/10 pl-10 pr-3 py-2.5 text-sm font-mono focus:border-brand outline-none"
                  data-testid="forgot-password-email"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={busy}
              className="w-full px-4 py-3 bg-brand text-brand-fg font-medium hover:bg-brand/90 disabled:opacity-50"
              data-testid="forgot-password-submit"
            >
              {busy ? "Sending…" : "Send reset link"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

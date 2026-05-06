import { useState } from "react";
import { Link, useNavigate, useLocation, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../contexts/AuthContext";
import Logo from "../components/Logo";
import GitHubButton from "../components/GitHubButton";
import ConstellationCanvas from "../components/ConstellationCanvas";
import useScrambleText from "../hooks/useScrambleText";
import { Loader2, ArrowRight, Activity } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const oauthError = searchParams.get("error");
  const from = location.state?.from?.pathname || "/app";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const welcome = useScrambleText("Your fleet is waiting.", { durationMs: 1200 });

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    const res = await login({ email, password });
    setLoading(false);
    if (res.ok) navigate(from, { replace: true });
    else setErr(res.error);
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background relative overflow-hidden">
      {/* LEFT — immersive */}
      <div className="hidden lg:block relative border-r border-white/[0.06] overflow-hidden">
        <ConstellationCanvas density={60} />
        <div className="absolute inset-0 bg-gradient-to-br from-brand/15 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-grid opacity-25" />
        <div className="aurora-blob" style={{ top: "-15%", left: "-10%", height: 420, width: 420, background: "radial-gradient(circle, #00E5FF 0%, transparent 60%)", animation: "aurora-1 26s ease-in-out infinite" }} />

        <div className="relative h-full flex flex-col justify-between p-12 z-10">
          <Link to="/"><Logo /></Link>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.4em] text-brand mb-3">// welcome back</div>
            <h2 className="font-display text-5xl font-semibold tracking-tighter leading-[1] max-w-md scramble">
              {welcome}
            </h2>
            <p className="mt-5 text-zinc-400 max-w-md">
              Sign back in to manage deployments, stream logs in realtime, and ship the next release.
            </p>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
            className="terminal max-w-md"
          >
            <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5 bg-black/70">
              <span className="h-2 w-2 rounded-full bg-signal-failed/70" />
              <span className="h-2 w-2 rounded-full bg-signal-queued/70" />
              <span className="h-2 w-2 rounded-full bg-signal-live/70 pulse-glow" />
              <span className="ml-2 text-[10px] uppercase tracking-[0.3em] text-zinc-500 inline-flex items-center gap-1">
                <Activity className="h-3 w-3" /> uptime.last_24h
              </span>
            </div>
            <div className="p-4 text-[11px] font-mono text-brand/80 leading-6">
              <div>novabrew-web ─ <span className="text-signal-live">99.99%</span></div>
              <div>novabrew-api ─ <span className="text-signal-live">99.94%</span></div>
              <div>novabrew-admin ─ <span className="text-signal-queued">99.71%</span></div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* RIGHT — form */}
      <div className="flex items-center justify-center p-8 relative">
        <div className="absolute inset-0 bg-grid-fine opacity-20 pointer-events-none" />
        <motion.div
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
          className="w-full max-w-sm relative"
        >
          <Link to="/" className="lg:hidden block mb-6"><Logo /></Link>
          <h1 className="font-display text-4xl font-semibold tracking-tighter">Sign in</h1>
          <p className="mt-1 text-sm text-zinc-400">Welcome back to DeployHub.</p>

          {oauthError && (
            <div className="mt-4 px-3 py-2 border border-signal-failed/30 bg-signal-failed/10 text-signal-failed text-sm" data-testid="oauth-error">
              GitHub sign-in failed ({oauthError.replace(/_/g, " ")}). Try again.
            </div>
          )}

          <div className="mt-6">
            <GitHubButton testId="login-github" />
          </div>
          <div className="mt-5 flex items-center gap-3 text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-600">
            <span className="flex-1 h-px bg-white/10" />
            or with email
            <span className="flex-1 h-px bg-white/10" />
          </div>

          <form onSubmit={submit} className="mt-5 space-y-4" data-testid="login-form">
            <div>
              <label className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 font-mono">Email</label>
              <input
                type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2.5 text-sm font-mono focus:border-brand focus:ring-1 focus:ring-brand/60 focus:outline-none transition-colors"
                placeholder="founder@studio.io"
                data-testid="login-email-input"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 font-mono">Password</label>
              <input
                type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2.5 text-sm font-mono focus:border-brand focus:ring-1 focus:ring-brand/60 focus:outline-none transition-colors"
                placeholder="••••••••"
                data-testid="login-password-input"
              />
            </div>
            {err && (
              <div className="px-3 py-2 border border-signal-failed/30 bg-signal-failed/10 text-signal-failed text-sm" data-testid="login-error">
                {err}
              </div>
            )}
            <button
              type="submit" disabled={loading}
              className="magnetic-btn w-full inline-flex items-center justify-center gap-2 py-2.5 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-[0.98] transition disabled:opacity-50 shadow-[0_0_24px_rgba(0,229,255,0.3)]"
              data-testid="login-submit"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Sign in <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>
          <div className="mt-5 text-xs font-mono text-zinc-500 flex justify-between">
            <Link to="/register" className="hover:text-brand transition-colors" data-testid="link-register">No account? Create one →</Link>
            <Link to="/" className="hover:text-brand transition-colors">← Home</Link>
          </div>
          <div className="mt-8 p-3 border border-white/5 bg-white/[0.02] text-xs font-mono text-zinc-500">
            <div className="text-zinc-400 mb-1">Demo credentials</div>
            demo@deployhub.dev / demo1234
          </div>
        </motion.div>
      </div>
    </div>
  );
}

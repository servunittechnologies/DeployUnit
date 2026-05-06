import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import Logo from "../components/Logo";
import { Loader2, ArrowRight } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/app";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

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
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      <div className="hidden lg:block relative bg-grid noise overflow-hidden border-r border-white/[0.06]">
        <div className="absolute inset-0 bg-gradient-to-br from-brand/10 via-transparent to-transparent" />
        <div className="relative h-full flex flex-col justify-between p-12">
          <Link to="/"><Logo /></Link>
          <div>
            <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-3">// welcome back</div>
            <h2 className="font-display text-5xl font-semibold tracking-tighter leading-tight max-w-md">
              Your apps are waiting.
            </h2>
            <p className="mt-4 text-zinc-400 max-w-md">
              Sign back in to manage deployments, monitor uptime, and ship the next release.
            </p>
          </div>
          <div className="terminal max-w-md">
            <div className="px-3 py-2 border-b border-white/5 bg-black/60 text-[10px] uppercase tracking-[0.3em] text-zinc-500">
              uptime.last_24h
            </div>
            <div className="p-4 text-xs font-mono text-brand/80 leading-6">
              <div>novabrew-web ─ 99.99%</div>
              <div>novabrew-api ─ 99.94%</div>
              <div>novabrew-admin ─ 99.71%</div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <Link to="/" className="lg:hidden block mb-6"><Logo /></Link>
          <h1 className="font-display text-3xl font-semibold tracking-tighter">Sign in</h1>
          <p className="mt-1 text-sm text-zinc-400">Welcome back to DeployHub.</p>

          <form onSubmit={submit} className="mt-8 space-y-4" data-testid="login-form">
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono">Email</label>
              <input
                type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2.5 text-sm font-mono focus:border-brand outline-none"
                placeholder="founder@studio.io"
                data-testid="login-email-input"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono">Password</label>
              <input
                type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2.5 text-sm font-mono focus:border-brand outline-none"
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
              className="w-full inline-flex items-center justify-center gap-2 py-2.5 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition disabled:opacity-50 shadow-[0_0_20px_rgba(0,229,255,0.25)]"
              data-testid="login-submit"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Sign in <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>
          <div className="mt-5 text-xs font-mono text-zinc-500 flex justify-between">
            <Link to="/register" className="hover:text-white" data-testid="link-register">No account? Create one →</Link>
            <Link to="/" className="hover:text-white">← Home</Link>
          </div>
          <div className="mt-8 p-3 border border-white/5 bg-white/[0.02] text-xs font-mono text-zinc-500">
            <div className="text-zinc-400 mb-1">Demo credentials</div>
            demo@deployhub.dev / demo1234
          </div>
        </div>
      </div>
    </div>
  );
}

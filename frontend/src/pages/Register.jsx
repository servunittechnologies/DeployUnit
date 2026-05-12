import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../contexts/AuthContext";
import Logo from "../components/Logo";
import GitHubButton from "../components/GitHubButton";
import ConstellationCanvas from "../components/ConstellationCanvas";
import { Loader2, ArrowRight, Check } from "lucide-react";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const presetPlan = params.get("plan");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    const res = await register({ name, email, password });
    setLoading(false);
    if (res.ok) {
      if (presetPlan) navigate(`/checkout?plan=${presetPlan}`);
      else navigate("/app");
    } else setErr(res.error);
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background relative overflow-hidden">
      {/* LEFT — form */}
      <div className="flex items-center justify-center p-8 order-2 lg:order-1 relative">
        <div className="absolute inset-0 bg-grid-fine opacity-20 pointer-events-none" />
        <motion.div
          initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
          className="w-full max-w-sm relative"
        >
          <Link to="/" className="lg:hidden block mb-6"><Logo /></Link>
          <h1 className="font-display text-4xl font-semibold tracking-tighter">Create account</h1>
          <p className="mt-1 text-sm text-zinc-400">Free forever for 1 app. No credit card.</p>

          <div className="mt-6">
            <GitHubButton label="Sign up with GitHub" testId="register-github" />
          </div>
          <div className="mt-5 flex items-center gap-3 text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-600">
            <span className="flex-1 h-px bg-white/10" />
            or with email
            <span className="flex-1 h-px bg-white/10" />
          </div>

          <form onSubmit={submit} className="mt-5 space-y-4" data-testid="register-form">
            <div>
              <label className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 font-mono">Full name</label>
              <input
                value={name} onChange={(e) => setName(e.target.value)} required autoFocus
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2.5 text-sm font-mono focus:border-brand focus:ring-1 focus:ring-brand/60 focus:outline-none transition-colors"
                placeholder="Jane Devine"
                data-testid="register-name-input"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 font-mono">Email</label>
              <input
                type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2.5 text-sm font-mono focus:border-brand focus:ring-1 focus:ring-brand/60 focus:outline-none transition-colors"
                placeholder="founder@studio.io"
                data-testid="register-email-input"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 font-mono">Password (min 6)</label>
              <input
                type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6}
                className="mt-1 w-full bg-black border border-white/10 px-3 py-2.5 text-sm font-mono focus:border-brand focus:ring-1 focus:ring-brand/60 focus:outline-none transition-colors"
                placeholder="••••••••"
                data-testid="register-password-input"
              />
            </div>
            {err && (
              <div className="px-3 py-2 border border-signal-failed/30 bg-signal-failed/10 text-signal-failed text-sm" data-testid="register-error">
                {err}
              </div>
            )}
            <button
              type="submit" disabled={loading}
              className="magnetic-btn w-full inline-flex items-center justify-center gap-2 py-2.5 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-[0.98] transition disabled:opacity-50 shadow-[0_0_24px_rgba(0,229,255,0.3)]"
              data-testid="register-submit"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <>Create account <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>
          <div className="mt-5 text-xs font-mono text-zinc-500 flex justify-between">
            <Link to="/login" className="hover:text-brand transition-colors" data-testid="link-login">Already have an account? Sign in →</Link>
            <Link to="/" className="hover:text-brand transition-colors">← Home</Link>
          </div>
        </motion.div>
      </div>

      {/* RIGHT — immersive */}
      <div className="hidden lg:block relative border-l border-white/[0.06] order-1 lg:order-2 overflow-hidden">
        <ConstellationCanvas density={55} />
        <div className="absolute inset-0 bg-gradient-to-bl from-brand/15 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-grid opacity-25" />
        <div className="aurora-blob" style={{ top: "-10%", right: "-10%", height: 420, width: 420, background: "radial-gradient(circle, #6B4BFF 0%, transparent 55%)", animation: "aurora-2 26s ease-in-out infinite" }} />

        <div className="relative h-full flex flex-col justify-between p-12 z-10">
          <Link to="/"><Logo /></Link>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.4em] text-brand mb-3">// what's inside</div>
            <h2 className="font-display text-5xl font-semibold tracking-tighter leading-[1] max-w-md">
              Production hosting,<br />
              <span className="text-brand holo">zero config.</span>
            </h2>
            <ul className="mt-8 space-y-3 text-sm text-zinc-300 max-w-md">
              {[
                "Deploy any Next.js or Node app in 2 clicks",
                "Custom domains with auto-SSL",
                "Realtime monitoring + alerts",
                "Teams & team roles for agencies",
              ].map((t, i) => (
                <motion.li
                  key={t}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 + 0.08 * i }}
                  className="flex items-center gap-2"
                >
                  <Check className="h-4 w-4 text-brand" />
                  {t}
                </motion.li>
              ))}
            </ul>
          </div>
          <div className="text-xs font-mono text-zinc-500">© DeployUnit · Hosting for Next.js & Node</div>
        </div>
      </div>
    </div>
  );
}

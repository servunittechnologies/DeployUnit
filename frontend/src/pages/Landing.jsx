import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useScroll, useTransform, useReducedMotion } from "framer-motion";
import {
  ArrowRight, ChevronRight, Sparkles, ShieldCheck, Activity, Globe, Zap,
  GitBranch, Github, Terminal, Cpu, Gauge, Rocket, Lock, Waves,
} from "lucide-react";
import Logo from "../components/Logo";
import ConstellationCanvas from "../components/ConstellationCanvas";
import useTypewriter from "../hooks/useTypewriter";
import useScrambleText from "../hooks/useScrambleText";
import useSpotlight from "../hooks/useSpotlight";

const TECH = [
  "Next.js 14", "Node 20", "Bun", "PNPM", "TypeScript", "Tailwind", "Prisma",
  "Postgres", "Redis", "Edge Functions", "Nginx", "Docker", "Nixpacks", "sslip.io",
];

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0 },
};

function Section({ children, className = "", id }) {
  return (
    <section id={id} className={`relative ${className}`}>
      {children}
    </section>
  );
}

function SectionLabel({ children }) {
  return (
    <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.4em] text-brand">
      <span className="h-px w-6 bg-brand/60" />
      {children}
    </div>
  );
}

/* ---------- Hero: typewriter + constellation + live deploy HUD ---------- */

function HeroTerminal() {
  const lines = useMemo(
    () => [
      { t: "$ deployhub deploy --repo novabrew/web", delay: 200 },
      { t: "→ Detected framework: Next.js 14 (app router)", delay: 220 },
      { t: "→ Build pack: nixpacks", delay: 200 },
      { t: "→ Allocating container on region eu-west", delay: 240 },
      { t: "→ Domain assigned: novabrew.app", delay: 200 },
      { t: "→ SSL: issued · HTTP/3 · Brotli", delay: 200 },
      { t: "✓ Live in 47s", delay: 260 },
    ],
    []
  );

  const [visible, setVisible] = useState(0);
  useEffect(() => {
    if (visible >= lines.length) return;
    const d = lines[visible].delay;
    const t = setTimeout(() => setVisible((v) => v + 1), d);
    return () => clearTimeout(t);
  }, [visible, lines]);

  // Replay periodically so the hero keeps feeling alive
  useEffect(() => {
    if (visible < lines.length) return;
    const t = setTimeout(() => setVisible(0), 7000);
    return () => clearTimeout(t);
  }, [visible, lines]);

  return (
    <div className="terminal w-full max-w-[480px]">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5 bg-black/70">
        <span className="h-2 w-2 rounded-full bg-signal-failed/70" />
        <span className="h-2 w-2 rounded-full bg-signal-queued/70" />
        <span className="h-2 w-2 rounded-full bg-signal-live/70 pulse-glow" />
        <span className="ml-2 text-[10px] uppercase tracking-[0.3em] text-zinc-500">
          ~/novabrew · zsh
        </span>
      </div>
      <div className="p-4 text-[12px] leading-6 min-h-[220px]">
        {lines.slice(0, visible).map((l, i) => {
          const isCmd = l.t.startsWith("$");
          const isOk = l.t.startsWith("✓");
          const cls = isCmd
            ? "text-zinc-300"
            : isOk
              ? "text-signal-live"
              : "text-zinc-400";
          return (
            <motion.div
              key={`${visible}-${i}`}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              className={cls}
            >
              {l.t}
            </motion.div>
          );
        })}
        {visible < lines.length && (
          <div className="text-brand caret" aria-hidden="true" />
        )}
      </div>
    </div>
  );
}

function LiveDeployHUD() {
  // Animated chart values
  const pts = useMemo(
    () => [42, 40, 44, 32, 34, 22, 26, 14, 18, 10, 12, 8, 6],
    []
  );
  const uptime = useScrambleText("99.99%", { durationMs: 900, replayKey: 0 });

  return (
    <div className="relative border border-white/10 p-4 bg-elevated/40 backdrop-blur-md w-full max-w-[480px] ml-auto">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono inline-flex items-center gap-2">
          <Waves className="h-3 w-3 text-brand" /> response latency — p50
        </div>
        <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-signal-live scramble">
          {uptime}
        </div>
      </div>
      <svg viewBox="0 0 260 60" className="w-full h-14">
        <defs>
          <linearGradient id="g1" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="rgba(0,229,255,0.6)" />
            <stop offset="100%" stopColor="rgba(0,229,255,0)" />
          </linearGradient>
        </defs>
        <polyline
          fill="url(#g1)"
          stroke="none"
          points={`0,60 ${pts.map((v, i) => `${(i / (pts.length - 1)) * 260},${v}`).join(" ")} 260,60`}
        />
        <polyline
          fill="none"
          stroke="#00E5FF"
          strokeWidth="1.6"
          points={pts.map((v, i) => `${(i / (pts.length - 1)) * 260},${v}`).join(" ")}
        />
        {pts.map((v, i) => (
          <circle
            key={i}
            cx={(i / (pts.length - 1)) * 260}
            cy={v}
            r={1.8}
            fill="#00E5FF"
            opacity={i === pts.length - 1 ? 1 : 0.4}
          />
        ))}
      </svg>
      <div className="mt-3 grid grid-cols-3 gap-px bg-white/[0.06]">
        {[
          ["requests", "4.2M"],
          ["errors", "0.01%"],
          ["deploys", "38"],
        ].map(([k, v]) => (
          <div key={k} className="bg-background px-2 py-2">
            <div className="text-[9px] uppercase tracking-[0.3em] font-mono text-zinc-500">{k}</div>
            <div className="font-display text-sm mt-0.5">{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function OrbitalOrnament() {
  return (
    <div className="pointer-events-none absolute -top-24 -right-32 h-[560px] w-[560px] opacity-60">
      <div className="absolute inset-0 animate-spin-slow">
        <div className="absolute inset-0 rounded-full border border-brand/20" />
        <div className="absolute inset-8 rounded-full border border-brand/15" />
        <div className="absolute inset-20 rounded-full border border-brand/10" />
      </div>
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-3 w-3 rounded-full bg-brand pulse-glow" />
    </div>
  );
}

/* ---------- Bento grid feature cards with mouse-tracked spotlight ---------- */

function BentoCard({ icon: Icon, label, title, body, className = "", children, testId }) {
  const onMove = useSpotlight();
  return (
    <motion.div
      onMouseMove={onMove}
      variants={fadeUp}
      className={`spotlight group border border-white/[0.08] bg-[#0a0a0a] p-6 md:p-7 overflow-hidden ${className}`}
      data-testid={testId}
    >
      <div className="flex items-center gap-2 mb-4 text-[10px] font-mono uppercase tracking-[0.35em] text-zinc-500">
        <Icon className="h-3.5 w-3.5 text-brand" />
        {label}
      </div>
      <h3 className="font-display text-xl md:text-2xl tracking-tight">{title}</h3>
      <p className="mt-2 text-sm text-zinc-400 leading-relaxed">{body}</p>
      {children}
    </motion.div>
  );
}

function DeployBentoVisual() {
  return (
    <div className="mt-5 font-mono text-[11px] leading-[1.6]">
      {[
        ["[CLONE]", "git fetch origin main", "text-brand"],
        ["[BUILD]", "yarn install · 1.4k modules", "text-brand"],
        ["[NIXPACKS]", "next build · compiled in 18s", "text-brand"],
        ["[DEPLOY]", "container live on eu-west-1", "text-signal-live"],
      ].map(([tag, msg, color], i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -4 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, margin: "-40px" }}
          transition={{ delay: 0.08 * i }}
          className="flex gap-2"
        >
          <span className={color}>{tag}</span>
          <span className="text-zinc-400">{msg}</span>
        </motion.div>
      ))}
    </div>
  );
}

function MonitoringBentoVisual() {
  const bars = useMemo(
    () =>
      Array.from({ length: 32 }, (_, i) =>
        0.4 + 0.6 * Math.abs(Math.sin(i * 0.9) + Math.cos(i * 0.3) * 0.4)
      ),
    []
  );
  return (
    <div className="mt-5 flex items-end gap-[3px] h-14">
      {bars.map((b, i) => (
        <motion.span
          key={i}
          initial={{ scaleY: 0, opacity: 0.3 }}
          whileInView={{ scaleY: b, opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.015, duration: 0.5 }}
          style={{ transformOrigin: "bottom" }}
          className="flex-1 bg-brand/70"
        />
      ))}
    </div>
  );
}

function GitBranchVisual() {
  return (
    <div className="mt-5 relative h-24 font-mono text-[11px]">
      <svg viewBox="0 0 280 90" className="absolute inset-0 w-full h-full text-brand/70">
        <path d="M10,70 L80,70 Q100,70 100,50 L100,28 Q100,18 110,18 L260,18" fill="none" stroke="currentColor" strokeWidth="1.2" />
        <path d="M100,50 L100,70 Q100,82 112,82 L260,82" fill="none" stroke="currentColor" strokeWidth="1.2" strokeDasharray="3 3" />
        <circle cx="80" cy="70" r="3.5" fill="#00E5FF" />
        <circle cx="150" cy="18" r="3.5" fill="#00E5FF" />
        <circle cx="220" cy="18" r="3.5" fill="#00E5FF" />
        <circle cx="180" cy="82" r="3.5" fill="#A1A1AA" />
      </svg>
      <div className="absolute top-[2px] left-[155px] text-[10px] text-brand">main</div>
      <div className="absolute bottom-[-2px] left-[120px] text-[10px] text-zinc-500">staging</div>
    </div>
  );
}

/* ---------- Rotating stats strip ---------- */

function StatStrip() {
  const stats = [
    ["p50 response", "42ms"],
    ["avg deploy", "47s"],
    ["platform uptime", "99.99%"],
    ["active regions", "6"],
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.06] border-y border-white/[0.06]">
      {stats.map(([k, v], i) => (
        <motion.div
          key={k}
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.08 }}
          className="bg-background px-6 py-5 relative overflow-hidden"
        >
          <div className="sweep-bg absolute inset-x-0 top-0 h-px opacity-60" />
          <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono">{k}</div>
          <div className="font-display text-3xl tracking-tighter mt-1">{v}</div>
        </motion.div>
      ))}
    </div>
  );
}

/* ---------- Interactive "deploy" playground with parallax tilt ---------- */

function DeployPlayground() {
  const ref = useRef(null);
  const [rot, setRot] = useState({ x: 0, y: 0 });
  const reduce = useReducedMotion();

  const onMove = (e) => {
    if (reduce) return;
    const r = ref.current.getBoundingClientRect();
    const mx = (e.clientX - r.left) / r.width;
    const my = (e.clientY - r.top) / r.height;
    setRot({ x: (0.5 - my) * 8, y: (mx - 0.5) * 10 });
  };
  const onLeave = () => setRot({ x: 0, y: 0 });

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ perspective: "1600px" }}
      className="relative"
    >
      <motion.div
        style={{
          transform: `rotateX(${rot.x}deg) rotateY(${rot.y}deg)`,
          transformStyle: "preserve-3d",
          transition: "transform 180ms cubic-bezier(0.22, 1, 0.36, 1)",
        }}
        className="border border-white/10 bg-[#0a0a0a] overflow-hidden"
      >
        {/* app tab bar */}
        <div className="flex items-stretch border-b border-white/[0.06]">
          <div className="px-4 py-3 border-r border-white/[0.06] bg-white/[0.02] text-[11px] font-mono text-brand">
            novabrew-web
          </div>
          <div className="px-4 py-3 border-r border-white/[0.06] text-[11px] font-mono text-zinc-500">
            novabrew-api
          </div>
          <div className="px-4 py-3 border-r border-white/[0.06] text-[11px] font-mono text-zinc-500">
            novabrew-admin
          </div>
          <div className="ml-auto px-4 py-3 text-[10px] uppercase tracking-[0.3em] font-mono text-signal-live inline-flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-signal-live animate-ping-soft" />
            live
          </div>
        </div>
        <div className="grid grid-cols-12">
          {/* left — deploy history */}
          <div className="col-span-5 border-r border-white/[0.06] p-5 space-y-3">
            <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono">deploys</div>
            {[
              ["deploy/42", "main@a8f3c", "42s", "live"],
              ["deploy/41", "main@e2a17", "48s", "live"],
              ["deploy/40", "feat/ui", "—",    "failed"],
            ].map(([id, msg, t, state]) => (
              <div key={id} className="flex items-center justify-between font-mono text-[11px]">
                <div className="flex items-center gap-3">
                  <span className={`h-1.5 w-1.5 rounded-full ${
                    state === "live" ? "bg-signal-live"
                    : state === "failed" ? "bg-signal-failed"
                    : "bg-signal-queued"
                  }`} />
                  <span className="text-zinc-300">{id}</span>
                  <span className="text-zinc-500">{msg}</span>
                </div>
                <span className="text-zinc-500">{t}</span>
              </div>
            ))}
          </div>
          {/* right — live preview mock */}
          <div className="col-span-7 relative bg-black/40 min-h-[220px]">
            <div className="absolute inset-0 bg-grid-fine opacity-40" />
            <div className="absolute inset-6 border border-white/10 bg-elevated/50 backdrop-blur-sm p-5 flex flex-col">
              <div className="text-[10px] uppercase tracking-[0.3em] text-brand font-mono">novabrew.app</div>
              <div className="font-display text-2xl tracking-tight mt-1">Single-origin espresso, shipped.</div>
              <div className="mt-auto h-9 w-28 bg-brand flex items-center justify-center text-brand-fg text-xs font-medium">
                Shop now →
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

/* ---------- Main Landing ---------- */

export default function Landing() {
  const scrollRef = useRef(null);
  const { scrollYProgress } = useScroll({ target: scrollRef, offset: ["start start", "end end"] });
  const bgShift = useTransform(scrollYProgress, [0, 1], ["0%", "40%"]);

  const { output: heroLead } = useTypewriter(
    "Production-grade hosting. Built on Coolify. Without the Vercel bill.",
    { cps: 40, startDelayMs: 250 }
  );

  return (
    <div ref={scrollRef} className="min-h-screen bg-background text-foreground relative overflow-x-clip">
      {/* global aurora background layer */}
      <motion.div className="fixed inset-0 -z-10 pointer-events-none" style={{ y: bgShift }}>
        <div className="aurora-blob" style={{ top: "-10%", left: "-10%", height: 520, width: 520, background: "radial-gradient(circle, #00E5FF 0%, transparent 60%)", animation: "aurora-1 22s ease-in-out infinite" }} />
        <div className="aurora-blob" style={{ top: "25%", right: "-10%", height: 620, width: 620, background: "radial-gradient(circle, #6B4BFF 0%, transparent 55%)", animation: "aurora-2 28s ease-in-out infinite" }} />
        <div className="aurora-blob" style={{ bottom: "-15%", left: "25%", height: 560, width: 560, background: "radial-gradient(circle, #00E5FF 0%, transparent 60%)", animation: "aurora-1 34s ease-in-out infinite reverse" }} />
      </motion.div>

      {/* nav */}
      <header className="glass fixed top-0 inset-x-0 z-40">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <Logo />
          <nav className="hidden md:flex items-center gap-7 text-sm text-zinc-400">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#bento" className="hover:text-white transition-colors">Platform</a>
            <Link to="/pricing" className="hover:text-white transition-colors" data-testid="nav-pricing">Pricing</Link>
            <a href="#agency" className="hover:text-white transition-colors">Agencies</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" className="px-3 py-1.5 text-sm border border-white/15 hover:border-brand/70 hover:text-brand transition-colors" data-testid="nav-signin">
              Sign in
            </Link>
            <Link to="/register" className="magnetic-btn px-3 py-1.5 text-sm bg-brand text-brand-fg font-medium hover:bg-brand/90 transition-colors shadow-[0_0_20px_rgba(0,229,255,0.25)]" data-testid="nav-signup">
              Start free
            </Link>
          </div>
        </div>
      </header>

      {/* HERO */}
      <Section className="pt-40 pb-28 overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-grid opacity-40" />
        <ConstellationCanvas className="absolute inset-0 -z-10 w-full h-full pointer-events-none opacity-90" density={75} />
        <OrbitalOrnament />

        <div className="max-w-[1400px] mx-auto px-6 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center relative">
          <div className="lg:col-span-7">
            <motion.div
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
              className="inline-flex items-center gap-2 mb-6 px-3 py-1 border border-brand/30 bg-brand/5 text-brand text-xs font-mono uppercase tracking-[0.3em]"
            >
              <Sparkles className="h-3 w-3" /> v1.0 — public beta · EU-first
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9 }}
              className="font-display text-5xl sm:text-6xl lg:text-7xl font-semibold tracking-tighter leading-[0.95]"
            >
              Ship Next.js & Node{" "}<br />
              <span className="relative inline-block">
                <span className="relative z-10 text-brand holo">in two clicks.</span>
                <span className="absolute inset-x-0 bottom-1 h-3 bg-brand/20 -z-0 blur-md" />
              </span>
            </motion.h1>

            <p className="mt-7 max-w-xl text-zinc-400 text-base leading-relaxed min-h-[52px]">
              {heroLead}
            </p>

            <motion.div
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.6 }}
              className="mt-9 flex flex-wrap items-center gap-3"
            >
              <Link to="/register" className="group magnetic-btn inline-flex items-center gap-2 px-6 py-3 bg-brand text-brand-fg font-medium hover:bg-brand/90 transition shadow-[0_0_28px_rgba(0,229,255,0.45)]" data-testid="hero-cta-start">
                Deploy your first app
                <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link to="/pricing" className="inline-flex items-center gap-2 px-6 py-3 border border-white/15 hover:border-brand/70 hover:text-brand transition-colors text-sm" data-testid="hero-cta-pricing">
                See pricing <ChevronRight className="h-4 w-4" />
              </Link>
            </motion.div>

            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}
              className="mt-12 flex flex-wrap items-center gap-x-7 gap-y-2 text-xs font-mono text-zinc-500"
            >
              <span className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-signal-live animate-ping-soft" /> 99.99% uptime SLA
              </span>
              <span>Auto-SSL · HTTP/3</span>
              <span>EU + US regions</span>
              <span>White-label for agencies</span>
            </motion.div>
          </div>

          <div className="lg:col-span-5 lg:-ml-6 flex flex-col gap-4 relative">
            <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25, duration: 0.8 }} className="animate-float">
              <HeroTerminal />
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, duration: 0.8 }}>
              <LiveDeployHUD />
            </motion.div>
          </div>
        </div>
      </Section>

      {/* STAT STRIP */}
      <StatStrip />

      {/* TECH MARQUEE */}
      <div className="border-y border-white/[0.06] py-4 overflow-hidden">
        <div className="flex gap-10 whitespace-nowrap animate-[shimmer_32s_linear_infinite]">
          {[...TECH, ...TECH].map((t, i) => (
            <span key={i} className="font-mono text-xs uppercase tracking-[0.35em] text-zinc-500">
              {t} <span className="text-brand/60 ml-2">/</span>
            </span>
          ))}
        </div>
      </div>

      {/* BENTO PLATFORM GRID */}
      <Section id="bento" className="max-w-[1400px] mx-auto px-6 py-28">
        <motion.div
          initial="hidden" whileInView="show" viewport={{ once: true, margin: "-120px" }}
          variants={{ show: { transition: { staggerChildren: 0.1 } } }}
        >
          <motion.div variants={fadeUp} className="max-w-3xl mb-10">
            <SectionLabel>// control room</SectionLabel>
            <h2 className="mt-4 font-display text-4xl lg:text-5xl tracking-tighter font-semibold">
              Every primitive you need to run<br />
              <span className="text-brand">a production fleet.</span>
            </h2>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-6 lg:grid-cols-12 gap-4">
            <BentoCard
              testId="bento-deploy"
              className="md:col-span-3 lg:col-span-7"
              icon={Rocket}
              label="deployments"
              title="Two-click deploys from any branch."
              body="Connect GitHub, pick a repo, hit Deploy. We auto-detect Next.js & Node, build with Nixpacks, and expose it behind a domain you pick."
            >
              <DeployBentoVisual />
            </BentoCard>

            <BentoCard
              testId="bento-monitor"
              className="md:col-span-3 lg:col-span-5"
              icon={Gauge}
              label="monitoring"
              title="Realtime uptime + latency."
              body="Per-app probes every 60s. Alerts fire the moment a service drifts."
            >
              <MonitoringBentoVisual />
            </BentoCard>

            <BentoCard
              testId="bento-branches"
              className="md:col-span-3 lg:col-span-5"
              icon={GitBranch}
              label="branching"
              title="Protected branches · rollback in 1 click."
              body="Production apps enforce an allow-list of branches. Every deploy is pinnable — roll back in seconds."
            >
              <GitBranchVisual />
            </BentoCard>

            <BentoCard
              testId="bento-domains"
              className="md:col-span-3 lg:col-span-4"
              icon={Globe}
              label="domains"
              title="Hands-free SSL."
              body="Buy domains inside the dashboard. Auto-provisioned Let's Encrypt. Zero DNS hand-holding."
            />

            <BentoCard
              testId="bento-security"
              className="md:col-span-3 lg:col-span-3"
              icon={Lock}
              label="security"
              title="Env vars, encrypted."
              body="Fernet-sealed at rest. Redacted in logs. Rotated on demand."
            />

            <BentoCard
              testId="bento-agency"
              className="md:col-span-3 lg:col-span-6"
              icon={Cpu}
              label="workspaces"
              title="Solo · Team · Agency."
              body="Multi-workspace tenancy with roles (Owner / Admin / Dev / Billing / Viewer). Bill per workspace, invoice per client."
            />

            <BentoCard
              testId="bento-github"
              className="md:col-span-3 lg:col-span-6"
              icon={Github}
              label="github"
              title="GitHub-native from day zero."
              body="OAuth-linked repo lists, auto-detect default branch, commit picker on every redeploy."
            />
          </div>
        </motion.div>
      </Section>

      {/* LIVE DASHBOARD PREVIEW */}
      <Section className="relative py-28 border-t border-white/[0.06] overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-grid-fine opacity-30" />
        <div className="max-w-[1400px] mx-auto px-6 grid lg:grid-cols-12 gap-14 items-center">
          <motion.div
            initial={{ opacity: 0, x: -30 }} whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-120px" }} transition={{ duration: 0.8 }}
            className="lg:col-span-5"
          >
            <SectionLabel>// the cockpit</SectionLabel>
            <h2 className="mt-4 font-display text-4xl lg:text-5xl tracking-tighter font-semibold">
              One dashboard. Every deployment. <span className="text-brand">Zero noise.</span>
            </h2>
            <p className="mt-5 text-zinc-400 max-w-lg leading-relaxed">
              Live SSE log streams with severity filters, instant rollbacks, per-branch deploys, env var encryption,
              domain management, uptime probes — all wired into a single terminal-first control surface.
            </p>

            <ul className="mt-8 space-y-4">
              {[
                ["Severity-tagged logs", "Filter by error · warning · build · deploy · info"],
                ["Branch-aware deploys", "Commit picker. Branch switcher. Rollback any deployment."],
                ["Mollie billing", "EU VAT + reverse-charge. PDF invoices. No WHMCS screens."],
              ].map(([t, b], i) => (
                <motion.li
                  key={t}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.1 * i }}
                  className="flex gap-4"
                >
                  <span className="mt-2 h-px w-6 bg-brand/50" />
                  <div>
                    <div className="font-display text-lg">{t}</div>
                    <div className="text-sm text-zinc-400">{b}</div>
                  </div>
                </motion.li>
              ))}
            </ul>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 40 }} whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-120px" }} transition={{ duration: 0.9 }}
            className="lg:col-span-7"
          >
            <DeployPlayground />
          </motion.div>
        </div>
      </Section>

      {/* FLOW */}
      <Section id="features" className="max-w-[1400px] mx-auto px-6 py-28 border-t border-white/[0.06]">
        <SectionLabel>// flow</SectionLabel>
        <h2 className="mt-4 font-display text-4xl lg:text-5xl tracking-tighter font-semibold max-w-2xl">
          From repo to live in under a minute.
        </h2>
        <div className="mt-14 grid grid-cols-1 md:grid-cols-4 gap-px bg-white/[0.06]">
          {[
            [Github, "Connect GitHub", "Authorize once. We list every repo you can deploy."],
            [Zap, "Pick a plan", "Hobby is free. Pro & Agency come with Mollie-backed billing."],
            [Terminal, "Hit deploy", "We provision, build, expose, issue SSL — in a single flow."],
            [Activity, "Monitor & scale", "Realtime checks. Alerts. Logs. Redeploy in one click."],
          ].map(([Icon, t, b], i) => (
            <motion.div
              key={t}
              initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }} transition={{ delay: 0.08 * i, duration: 0.6 }}
              className="bg-background p-8 relative group hover:bg-white/[0.02] transition-colors"
            >
              <div className="absolute top-0 left-0 h-px w-0 bg-brand group-hover:w-full transition-all duration-500" />
              <div className="text-[10px] font-mono text-brand tracking-[0.3em]">0{i + 1}</div>
              <Icon className="h-5 w-5 mt-6 text-brand/80" />
              <div className="font-display text-xl tracking-tight mt-4">{t}</div>
              <div className="mt-2 text-sm text-zinc-400 leading-relaxed">{b}</div>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* AGENCY */}
      <Section id="agency" className="border-t border-white/[0.06] py-28 relative overflow-hidden">
        <div className="max-w-[1400px] mx-auto px-6 grid lg:grid-cols-12 gap-14 items-center">
          <motion.div
            initial={{ opacity: 0 }} whileInView={{ opacity: 1 }}
            viewport={{ once: true }} className="lg:col-span-6 order-2 lg:order-1"
          >
            <div className="relative border border-white/10 bg-[#0a0a0a] p-8 overflow-hidden">
              <div className="absolute inset-0 bg-grid opacity-20" />
              <div className="relative text-[10px] uppercase tracking-[0.3em] font-mono text-brand mb-5">
                studio.agency / workspaces
              </div>
              <div className="space-y-2 relative">
                {[
                  ["NovaBrew", "12 apps · €79/mo", "live"],
                  ["Pulse Finance", "4 apps · €29/mo", "live"],
                  ["Acme Health", "8 apps · €79/mo", "live"],
                  ["Kindle Labs", "3 apps · —", "queued"],
                ].map(([name, meta, state], i) => (
                  <motion.div
                    key={name}
                    initial={{ opacity: 0, x: -8 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.1 * i }}
                    className="flex items-center justify-between border border-white/[0.06] bg-elevated/40 px-4 py-3 font-mono text-[12px]"
                  >
                    <div className="flex items-center gap-3">
                      <span className={`h-1.5 w-1.5 rounded-full ${state === "live" ? "bg-signal-live" : "bg-signal-queued"}`} />
                      <span className="text-zinc-200">{name}</span>
                    </div>
                    <span className="text-zinc-500">{meta}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>

          <div className="lg:col-span-6 order-1 lg:order-2">
            <SectionLabel>// for agencies</SectionLabel>
            <h2 className="mt-4 font-display text-4xl lg:text-5xl tracking-tighter font-semibold">
              One platform.<br />
              <span className="text-brand">Every client.</span>
            </h2>
            <p className="mt-5 text-zinc-400 max-w-lg leading-relaxed">
              Group apps by client project, invite team members with granular roles, and let billing flow through
              your white-labeled dashboard. Your clients never see the seams.
            </p>
            <div className="mt-8 grid grid-cols-2 gap-px bg-white/[0.06]">
              {[
                ["Workspaces", "Solo or Agency"],
                ["Roles", "Owner / Admin / Dev / Billing / Viewer"],
                ["Projects", "Group apps per client"],
                ["Branding", "White-label invoices"],
              ].map(([t, b], i) => (
                <motion.div
                  key={t}
                  initial={{ opacity: 0, y: 14 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.08 * i }}
                  className="bg-background p-5"
                >
                  <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono">{t}</div>
                  <div className="text-sm mt-1">{b}</div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* FINAL CTA */}
      <Section className="border-t border-white/[0.06] py-28 relative overflow-hidden">
        <div className="absolute inset-0 -z-10">
          <div className="absolute inset-0 bg-grid-fine opacity-30" />
          <div className="absolute -inset-20 opacity-40" style={{ background: "radial-gradient(700px circle at 50% 50%, rgba(0,229,255,0.18), transparent 60%)" }} />
        </div>
        <div className="max-w-[1400px] mx-auto px-6 text-center">
          <motion.h2
            initial={{ opacity: 0, y: 26 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="font-display text-4xl lg:text-6xl tracking-tighter font-semibold"
          >
            The boring part of hosting,<br />
            made <span className="text-brand holo">brilliantly fast.</span>
          </motion.h2>
          <div className="mt-10 flex justify-center gap-3">
            <Link to="/register" className="magnetic-btn inline-flex items-center gap-2 px-7 py-3.5 bg-brand text-brand-fg font-medium hover:bg-brand/90 transition shadow-[0_0_32px_rgba(0,229,255,0.45)]">
              Start free <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/pricing" className="inline-flex items-center gap-2 px-7 py-3.5 border border-white/15 hover:border-brand/70 hover:text-brand transition-colors">
              Compare plans
            </Link>
          </div>
          <div className="mt-12 flex justify-center items-center gap-6 text-xs font-mono text-zinc-500">
            <span className="inline-flex items-center gap-2">
              <ShieldCheck className="h-3 w-3" /> GDPR · EU data residency
            </span>
            <span>No credit card for Hobby tier</span>
          </div>
        </div>
      </Section>

      <footer className="border-t border-white/[0.06] py-10">
        <div className="max-w-[1400px] mx-auto px-6 flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-zinc-500">
          <Logo small />
          <div>© {new Date().getFullYear()} DeployHub · Built on Coolify · Powered by Mollie</div>
        </div>
      </footer>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useInView, useReducedMotion } from "framer-motion";
import {
  ArrowRight, ArrowUpRight, Check, X as XIcon, Sparkles, Activity,
  Globe, Zap, GitBranch, Github, Terminal, Cpu, Gauge, Rocket, Lock,
  Leaf, Wind, Layers, BarChart3, Bell, Code2, FileText, Mail, Bot,
  Database, ShieldCheck, Server, MapPin, Workflow, ChevronRight, Eye,
  Menu,
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  CartesianGrid, XAxis, YAxis, Tooltip as RTooltip, Bar, BarChart,
} from "recharts";
import Logo from "../components/Logo";
import ConstellationCanvas from "../components/ConstellationCanvas";
import useTypewriter from "../hooks/useTypewriter";
import useSeo from "../hooks/useSeo";

/* ───────────────────────── Shared atoms ───────────────────────── */

const CYAN = "#06B6D4";
const GREEN = "#10B981";

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0 },
};
const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } },
};

function Overline({ children, color = "text-cyan-400" }) {
  return (
    <div className={`inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.4em] ${color}`}>
      <span className={`h-px w-6 ${color === "text-cyan-400" ? "bg-cyan-500/60" : "bg-emerald-500/60"}`} />
      {children}
    </div>
  );
}

function Section({ id, className = "", children }) {
  return (
    <section id={id} className={`relative ${className}`}>{children}</section>
  );
}

function Container({ className = "", children }) {
  return (
    <div className={`relative max-w-7xl mx-auto px-6 lg:px-8 ${className}`}>{children}</div>
  );
}

function PrimaryBtn({ to, href, children, testId, className = "" }) {
  const Comp = to ? Link : "a";
  const props = to ? { to } : { href };
  return (
    <Comp
      {...props}
      data-testid={testId}
      className={`group inline-flex items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-6 py-3 transition-colors ${className}`}
    >
      {children}
      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
    </Comp>
  );
}

function OutlineBtn({ to, href, children, testId, className = "" }) {
  const Comp = to ? Link : "a";
  const props = to ? { to } : { href };
  return (
    <Comp
      {...props}
      data-testid={testId}
      className={`inline-flex items-center gap-2 border border-zinc-700 hover:border-cyan-500 text-white px-6 py-3 transition-colors font-mono text-sm uppercase tracking-wider ${className}`}
    >
      {children}
    </Comp>
  );
}

/* ───────────────────────── Top nav ───────────────────────── */

function Nav() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);
  const links = [
    ["Features",  "#features",  true],
    ["Compare",   "#compare",   true],
    ["Pricing",   "/pricing",   false],
  ];
  return (
    <header className="sticky top-0 z-50 backdrop-blur-xl bg-black/60 border-b border-zinc-800">
      <Container className="flex items-center justify-between h-16">
        <Link to="/" className="flex items-center gap-2.5" data-testid="nav-home">
          <Logo className="h-7 w-auto" />
        </Link>
        <nav className="hidden md:flex items-center gap-6 text-sm">
          <a href="#features" className="text-zinc-300 hover:text-white" data-testid="nav-features">Features</a>
          <a href="#compare" className="text-zinc-300 hover:text-white" data-testid="nav-compare">Compare</a>
          <Link to="/pricing" className="text-zinc-300 hover:text-white" data-testid="nav-pricing">Pricing</Link>
          <Link to="/login" className="text-zinc-300 hover:text-white" data-testid="nav-login">Log in</Link>
        </nav>
        <div className="flex items-center gap-2">
          <PrimaryBtn to="/register" testId="nav-cta" className="text-sm px-3 sm:px-4 py-2">Deploy now</PrimaryBtn>
          <button
            onClick={() => setOpen(true)}
            className="md:hidden p-2 -mr-2 text-zinc-300 hover:text-white"
            aria-label="Open menu"
            data-testid="nav-mobile-toggle"
          >
            <Menu className="h-6 w-6" />
          </button>
        </div>
      </Container>

      {/* Mobile drawer — always rendered for smooth open/close animation */}
      <div
        className={`md:hidden fixed inset-0 z-[60] flex flex-col h-screen bg-black/95 backdrop-blur-xl transition-all duration-200 ease-out ${
          open
            ? "opacity-100 translate-y-0 pointer-events-auto"
            : "opacity-0 -translate-y-1 pointer-events-none"
        }`}
        aria-hidden={!open}
        data-testid="nav-mobile-drawer"
      >
        <div className="flex items-center justify-between h-16 px-4 border-b border-zinc-800 shrink-0">
          <Link to="/" onClick={() => setOpen(false)}><Logo className="h-7 w-auto" /></Link>
          <button
            onClick={() => setOpen(false)}
            className="p-2 -mr-2 text-zinc-300 hover:text-white transition-colors"
            aria-label="Close menu"
            data-testid="nav-mobile-close"
          >
            <XIcon className="h-6 w-6" />
          </button>
        </div>
        <nav className="flex-1 flex flex-col px-6 py-4 overflow-y-auto">
          {links.map(([label, href, isAnchor]) => {
            const Comp = isAnchor ? "a" : Link;
            const props = isAnchor ? { href } : { to: href };
            return (
              <Comp
                key={label}
                {...props}
                onClick={() => setOpen(false)}
                data-testid={`nav-mobile-${label.toLowerCase().replace(/\s+/g, '-')}`}
                className="py-2.5 text-base font-display font-medium text-zinc-200 hover:text-cyan-400 transition-colors border-b border-zinc-900"
              >
                {label}
              </Comp>
            );
          })}
          {/* Account actions — visually separated from content nav */}
          <div className="mt-6 pt-5 border-t border-zinc-800 flex flex-col gap-3">
            <Link
              to="/login"
              onClick={() => setOpen(false)}
              data-testid="nav-mobile-log-in"
              className="inline-flex items-center justify-center gap-2 border border-zinc-700 hover:border-cyan-500 hover:text-cyan-400 text-zinc-200 font-medium px-5 py-2.5 text-sm transition-colors"
            >
              Log in
            </Link>
            <Link
              to="/register"
              onClick={() => setOpen(false)}
              data-testid="nav-mobile-cta"
              className="inline-flex items-center justify-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-5 py-2.5 text-sm transition-colors"
            >
              Deploy now
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </nav>
      </div>
    </header>
  );
}

/* ───────────────────────── Hero ───────────────────────── */

function HeroTerminal() {
  const lines = useMemo(() => [
    { t: "$ deployunit deploy --repo servunit/web", c: "text-zinc-300" },
    { t: "→ Connected: GitHub (oauth · push verified)", c: "text-zinc-500" },
    { t: "→ Detected: Next.js 14 · App Router", c: "text-zinc-500" },
    { t: "→ Buildpack: nixpacks · region eu", c: "text-zinc-500" },
    { t: "→ Container up · 384 MB · 0.5 vCPU", c: "text-zinc-500" },
    { t: "→ Domain assigned: servunit.app · TLS issued", c: "text-emerald-400" },
    { t: "→ Live URL: https://servunit.app  ⏱  41 s", c: "text-cyan-400" },
    { t: "✓ Deploy succeeded · powered by green energy", c: "text-emerald-400" },
  ], []);

  const [idx, setIdx] = useState(0);
  const reduce = useReducedMotion();
  useEffect(() => {
    if (reduce) { setIdx(lines.length); return; }
    if (idx >= lines.length) return;
    const t = setTimeout(() => setIdx((i) => i + 1), 480);
    return () => clearTimeout(t);
  }, [idx, lines.length, reduce]);

  return (
    <div className="relative border border-zinc-800 bg-black/80 backdrop-blur-sm font-mono text-xs sm:text-sm shadow-[0_0_40px_-15px_rgba(6,182,212,0.45)]">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 bg-zinc-950/80">
        <span className="h-2.5 w-2.5 rounded-full bg-red-500/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/70" />
        <span className="ml-3 text-[10px] uppercase tracking-[0.3em] text-zinc-500">~/deployunit</span>
      </div>
      <div className="p-4 sm:p-5 space-y-1 min-h-[260px]">
        {lines.slice(0, idx + 1).map((l, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.25 }}
            className={l.c}
          >
            {l.t}
            {i === idx && idx < lines.length - 1 && <span className="ml-1 inline-block w-1.5 h-3 bg-cyan-400 animate-pulse align-middle" />}
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function Hero() {
  return (
    <Section className="relative pt-32 pb-24 lg:pt-40 lg:pb-32 overflow-hidden">
      <div className="absolute inset-0 -z-10">
        <ConstellationCanvas density={40} />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black/80" />
      </div>
      <Container className="grid lg:grid-cols-[1.05fr_1fr] gap-12 items-center">
        <motion.div initial="hidden" animate="show" variants={stagger}>
          <motion.div variants={fadeUp} className="mb-6"><Overline>The European Vercel alternative</Overline></motion.div>
          <motion.h1
            variants={fadeUp}
            className="font-display text-5xl md:text-6xl lg:text-7xl font-bold tracking-tighter leading-[0.95] text-white"
          >
            Deploy Next.js & Node apps —{" "}
            <span className="text-cyan-400">built for agencies.</span>
          </motion.h1>
          <motion.p variants={fadeUp} className="mt-7 text-lg sm:text-xl text-zinc-400 max-w-xl leading-relaxed">
            Push to Git → live URL in 41 seconds.<br />
            <span className="text-zinc-200">No surprise bills. No DevOps. No extra tools.</span><br />
            Fully EU-hosted.
          </motion.p>
          <motion.div variants={fadeUp} className="mt-9 flex flex-wrap gap-3">
            <PrimaryBtn to="/register" testId="hero-cta-primary">Start deploying</PrimaryBtn>
            <OutlineBtn to="/pricing" testId="hero-cta-secondary">See pricing</OutlineBtn>
          </motion.div>
          <motion.div variants={fadeUp} className="mt-10 flex flex-wrap items-center gap-x-7 gap-y-3 text-[11px] font-mono uppercase tracking-[0.3em] text-zinc-500">
            <span className="inline-flex items-center gap-1.5"><MapPin className="h-3 w-3" /> EU hosted</span>
            <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3 w-3" /> GDPR ready</span>
            <span className="inline-flex items-center gap-1.5"><Lock className="h-3 w-3" /> Predictable pricing</span>
            <span className="inline-flex items-center gap-1.5"><Zap className="h-3 w-3 text-cyan-400" /> 41s deploys</span>
          </motion.div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }}>
          <HeroTerminal />
        </motion.div>
      </Container>
    </Section>
  );
}

/* ───────────────────────── Logo strip ───────────────────────── */

function LogoStrip() {
  const items = ["Next.js 14", "Node 20", "Bun", "TypeScript", "Postgres", "Redis", "Docker", "Tailwind", "Prisma", "Nixpacks"];
  return (
    <Section className="py-10 border-y border-zinc-900 bg-zinc-950/40">
      <Container>
        <div className="text-center text-[10px] font-mono uppercase tracking-[0.4em] text-zinc-500 mb-5">
          Auto-detects every modern stack
        </div>
        <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-3 text-xs font-mono text-zinc-500">
          {items.map((s) => (
            <span key={s} className="hover:text-cyan-400 transition-colors">{s}</span>
          ))}
        </div>
      </Container>
    </Section>
  );
}

/* ───────────────────────── Killer: replaces N tools ───────────────────────── */

function ReplacesStack() {
  // Each card represents a tool DeployUnit subsumes — keeps it short on
  // purpose: this section is a credibility punch, not a feature wall.
  const replaced = [
    { name: "Vercel",     why: "hosting + edge" },
    { name: "Datadog",    why: "monitoring + alerts" },
    { name: "Sentry",     why: "error tracking" },
    { name: "Plausible",  why: "web analytics" },
    { name: "Cloudflare", why: "DNS + SSL" },
    { name: "Linear",     why: "deploy workflows" },
  ];
  return (
    <Section className="py-28 lg:py-36 border-b border-zinc-900">
      <Container>
        <div className="max-w-3xl mb-16 lg:mb-20">
          <Overline>One platform</Overline>
          <h2 className="mt-4 font-display text-4xl md:text-6xl font-bold tracking-tighter text-white leading-[1.05]">
            Stop juggling 6 tools to run one app.
          </h2>
          <p className="mt-6 text-lg text-zinc-400 max-w-xl leading-relaxed">
            Replace your entire stack with one platform.
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-px bg-zinc-900 border border-zinc-900" data-testid="replaces-stack">
          {replaced.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.04 }}
              className="bg-black p-8 md:p-10 relative group"
            >
              <div className="absolute top-4 right-4 text-zinc-700 group-hover:text-signal-failed/70 transition-colors">
                <XIcon className="h-4 w-4" />
              </div>
              <div className="font-display text-2xl md:text-3xl text-zinc-200 line-through decoration-zinc-700 decoration-1">
                {t.name}
              </div>
              <div className="mt-2 text-[11px] font-mono uppercase tracking-[0.3em] text-zinc-500">
                {t.why}
              </div>
            </motion.div>
          ))}
        </div>
        <div className="mt-10 text-center">
          <span className="inline-flex items-center gap-3 text-sm font-mono text-zinc-400">
            <span className="h-px w-12 bg-cyan-500/40" />
            <ArrowRight className="h-4 w-4 text-cyan-400" />
            <span className="text-cyan-400 uppercase tracking-[0.3em] text-xs">DeployUnit</span>
            <span className="h-px w-12 bg-cyan-500/40" />
          </span>
        </div>
      </Container>
    </Section>
  );
}


/* ───────────────────────── Built for agencies (pillar) ───────────────────────── */

function ForAgencies() {
  const bullets = [
    { t: "Workspaces per client", b: "Hard tenant isolation. Switch contexts in one click without leaking data." },
    { t: "Per-client billing", b: "Each workspace bills separately. Invoice your customers with white-label PDFs." },
    { t: "Team permissions & audit logs", b: "Owner / admin / developer / billing roles. Every action logged for compliance." },
    { t: "Staging + production per project", b: "Branch-based environments, PR previews, instant rollback per workspace." },
  ];
  return (
    <Section className="py-28 lg:py-36 border-b border-zinc-900 bg-zinc-950/30">
      <Container className="grid lg:grid-cols-[1fr_1.1fr] gap-16 items-center">
        <div>
          <Overline color="text-emerald-400">For agencies</Overline>
          <h2 className="mt-4 font-display text-4xl md:text-5xl lg:text-6xl font-bold tracking-tighter text-white leading-[1.05]">
            Built for agencies <span className="text-emerald-400">managing real clients.</span>
          </h2>
          <p className="mt-6 text-lg text-zinc-400 leading-relaxed max-w-lg">
            Finally, a platform that matches how agencies actually work — not just how indie devs ship side projects.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <PrimaryBtn to="/register" testId="agency-cta">Start deploying</PrimaryBtn>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-zinc-900 border border-zinc-900" data-testid="agency-bullets">
          {bullets.map((b, i) => (
            <motion.div
              key={b.t}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              className="bg-black p-7"
            >
              <div className="flex items-center gap-2 text-emerald-400 mb-3">
                <Check className="h-4 w-4" />
                <span className="text-xs font-mono uppercase tracking-[0.2em]">included</span>
              </div>
              <div className="font-display text-lg text-zinc-100 leading-tight">{b.t}</div>
              <div className="mt-2 text-sm text-zinc-400 leading-relaxed">{b.b}</div>
            </motion.div>
          ))}
        </div>
      </Container>
    </Section>
  );
}


/* ───────────────────────── How it works ───────────────────────── */

function StepCard({ n, title, body, icon: Icon, anim }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });
  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={inView ? "show" : "hidden"}
      variants={fadeUp}
      transition={{ duration: 0.5 }}
      className="relative border border-zinc-800 bg-zinc-950/40 p-7"
      data-testid={`how-step-${n}`}
    >
      <div className="flex items-start justify-between mb-5">
        <div className="text-[10px] font-mono uppercase tracking-[0.35em] text-zinc-500">step / 0{n}</div>
        <Icon className="h-5 w-5 text-cyan-400" />
      </div>
      <h3 className="font-display text-2xl font-bold tracking-tight text-white mb-2">{title}</h3>
      <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
      <div className="mt-5">{anim}</div>
    </motion.div>
  );
}

function StepAnimGithub() {
  return (
    <div className="flex items-center gap-2 text-[11px] font-mono text-zinc-400 border border-zinc-800 bg-black/50 px-3 py-2">
      <Github className="h-3.5 w-3.5 text-zinc-300" />
      <span>servunit/web</span>
      <span className="ml-auto text-emerald-400">main · synced</span>
    </div>
  );
}
function StepAnimDetect() {
  return (
    <div className="flex flex-wrap gap-1.5">
      {["nextjs", "node", "postgres", "redis", "tailwind"].map((t, i) => (
        <motion.span
          key={t}
          initial={{ opacity: 0, y: 6 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 * i }}
          className="text-[10px] font-mono px-2 py-0.5 bg-cyan-500/10 text-cyan-300 border border-cyan-500/30"
        >
          {t}
        </motion.span>
      ))}
    </div>
  );
}
function StepAnimMetrics() {
  const data = useMemo(
    () => Array.from({ length: 20 }, (_, i) => ({ x: i, cpu: 22 + 18 * Math.sin(i / 2) + (i % 4) * 4 })),
    [],
  );
  return (
    <div style={{ width: "100%", height: 60 }}>
      <ResponsiveContainer>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="cpufill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CYAN} stopOpacity={0.55} />
              <stop offset="100%" stopColor={CYAN} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="cpu" stroke={CYAN} strokeWidth={1.5} fill="url(#cpufill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function HowItWorks() {
  return (
    <Section id="how" className="py-24 lg:py-32">
      <Container>
        <div className="mb-12 text-center">
          <Overline>How it works</Overline>
          <h2 className="mt-3 font-display text-3xl md:text-5xl font-bold tracking-tighter text-white">
            From commit to live URL in 41 seconds.
          </h2>
          <p className="mt-3 text-zinc-400 max-w-2xl mx-auto">
            No Dockerfile to write, no nginx to configure. Connect a repo, we handle the rest.
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-5 relative">
          <StepCard n={1} title="Connect GitHub" body="OAuth in one click. We read public & private repos with a single permission scope." icon={Github} anim={<StepAnimGithub />} />
          <StepCard n={2} title="Auto-detect stack" body="Nixpacks reads your package.json, requirements.txt, or Dockerfile and builds the right image." icon={Workflow} anim={<StepAnimDetect />} />
          <StepCard n={3} title="Ship + observe" body="Live URL, TLS, custom domain, real-time container metrics and alerts — all from day zero." icon={Activity} anim={<StepAnimMetrics />} />
        </div>
      </Container>
    </Section>
  );
}

/* ───────────────────────── Features bento ───────────────────────── */

function MetricsGraphMock() {
  const [data, setData] = useState(() =>
    Array.from({ length: 30 }, (_, i) => ({
      t: i,
      cpu: 30 + Math.sin(i / 3) * 18 + (i % 5) * 2,
      mem: 55 + Math.cos(i / 4) * 12 + Math.sin(i / 6) * 6,
    })),
  );
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => {
      setData((prev) => {
        const last = prev[prev.length - 1];
        const next = {
          t: last.t + 1,
          cpu: Math.max(8, Math.min(95, last.cpu + (Math.random() - 0.5) * 14)),
          mem: Math.max(20, Math.min(95, last.mem + (Math.random() - 0.5) * 9)),
        };
        return [...prev.slice(1), next];
      });
    }, 1600);
    return () => clearInterval(id);
  }, [paused]);

  const latest = data[data.length - 1];
  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      data-testid="metrics-live-chart"
    >
      <div className="flex items-center justify-between mb-1 text-[10px] font-mono">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 text-emerald-400">
            <span className={`h-1.5 w-1.5 rounded-full bg-emerald-400 ${paused ? "" : "animate-pulse"}`} />
            {paused ? "paused" : "live"}
          </span>
          <span className="text-zinc-500">· 1.6s tick</span>
        </div>
        <div className="flex gap-3 tabular-nums">
          <span className="text-cyan-400">CPU {Math.round(latest.cpu)}%</span>
          <span className="text-emerald-400">MEM {Math.round(latest.mem)}%</span>
        </div>
      </div>
      <div style={{ width: "100%", height: 140 }}>
        <ResponsiveContainer>
          <LineChart data={data}>
            <CartesianGrid stroke="#1f1f23" vertical={false} />
            <XAxis dataKey="t" hide />
            <YAxis stroke="#52525b" fontSize={10} tickLine={false} axisLine={false} domain={[0, 100]} />
            <RTooltip
              contentStyle={{ background: "#0a0a0a", border: "1px solid #27272a", fontSize: 11, fontFamily: "JetBrains Mono" }}
              cursor={{ stroke: "#3f3f46", strokeDasharray: "3 3" }}
            />
            <Line type="monotone" dataKey="cpu" name="CPU %" stroke={CYAN} dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line type="monotone" dataKey="mem" name="MEM %" stroke={GREEN} dot={false} strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function PageSpeedGauge() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: false, amount: 0.3 });
  const [target, setTarget] = useState(98);
  const [score, setScore] = useState(0);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (!inView && !running) return;
    let f = score;
    const id = setInterval(() => {
      if (f < target) { f += 2; setScore(Math.min(target, f)); }
      else { clearInterval(id); setRunning(false); }
    }, 22);
    return () => clearInterval(id);
    // eslint-disable-next-line
  }, [target, inView]);

  const run = () => {
    setRunning(true);
    setScore(0);
    setTarget(89 + Math.floor(Math.random() * 11)); // 89..99
  };

  const r = 56;
  const c = 2 * Math.PI * r;
  return (
    <div ref={ref}>
      <div className="flex items-center gap-5">
        <svg width={130} height={130} viewBox="0 0 130 130">
          <circle cx={65} cy={65} r={r} stroke="#1f1f23" strokeWidth={8} fill="none" />
          <circle
            cx={65} cy={65} r={r}
            stroke={CYAN} strokeWidth={8} fill="none"
            strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}
            strokeLinecap="round" transform="rotate(-90 65 65)"
            style={{ transition: "stroke-dashoffset 0.4s ease-out" }}
          />
          <text x="65" y="72" textAnchor="middle" className="fill-cyan-400 font-mono" fontSize="28">{score}</text>
        </svg>
        <div className="text-xs font-mono text-zinc-400 space-y-1 flex-1">
          {[
            { l: "LCP", v: "1.2s", k: "emerald" },
            { l: "FCP", v: "0.8s", k: "emerald" },
            { l: "CLS", v: "0.02", k: "emerald" },
            { l: "TBT", v: "120ms", k: "cyan" },
          ].map((m) => (
            <div key={m.l} className="flex justify-between gap-3 group/m">
              <span className="group-hover/m:text-zinc-200 transition-colors">{m.l}</span>
              <span className={m.k === "emerald" ? "text-emerald-400" : "text-cyan-400"}>{m.v}</span>
            </div>
          ))}
        </div>
      </div>
      <button
        type="button"
        onClick={run}
        disabled={running}
        className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.25em] border border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/10 disabled:opacity-50 transition-colors"
        data-testid="pagespeed-run-audit"
      >
        {running ? "auditing…" : "↺ re-run audit"}
      </button>
    </div>
  );
}

function VisitorMapMock() {
  const baseDots = useMemo(() => [
    { x: 18, y: 35, c: "DE" }, { x: 22, y: 45, c: "FR" }, { x: 28, y: 38, c: "NL" }, { x: 25, y: 50, c: "ES" },
    { x: 40, y: 30, c: "PL" }, { x: 45, y: 42, c: "IT" }, { x: 50, y: 38, c: "AT" }, { x: 60, y: 50, c: "GR" },
    { x: 68, y: 45, c: "TR" }, { x: 78, y: 55, c: "AE" }, { x: 75, y: 38, c: "IN" }, { x: 32, y: 60, c: "PT" },
    { x: 55, y: 65, c: "MA" }, { x: 30, y: 28, c: "UK" }, { x: 65, y: 28, c: "RU" },
  ], []);
  const [visible, setVisible] = useState(() => baseDots.map(() => true));
  const [visitors, setVisitors] = useState(847);
  useEffect(() => {
    const id = setInterval(() => {
      const idx = Math.floor(Math.random() * baseDots.length);
      setVisible((prev) => {
        const out = [...prev];
        out[idx] = !out[idx];
        return out;
      });
      setVisitors((v) => v + (Math.random() < 0.7 ? 1 : 0));
    }, 900);
    return () => clearInterval(id);
  }, [baseDots.length]);

  return (
    <div className="relative h-[160px] border border-zinc-800 bg-zinc-950/60 overflow-hidden" data-testid="visitor-map">
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{ backgroundImage: "radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)", backgroundSize: "16px 16px" }}
      />
      {baseDots.map((d, i) => (
        <motion.span
          key={i}
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: visible[i] ? 1 : 0, scale: visible[i] ? 1 : 0 }}
          transition={{ duration: 0.5 }}
          className="absolute h-1.5 w-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_2px_rgba(6,182,212,0.6)] cursor-pointer hover:scale-150 transition-transform"
          style={{ left: `${d.x}%`, top: `${d.y}%` }}
          title={d.c}
          data-country={d.c}
        />
      ))}
      <div className="absolute bottom-3 left-3 text-[10px] font-mono text-zinc-400 tabular-nums">
        <span className="text-cyan-400">{visitors.toLocaleString()}</span> visitors · <span className="text-emerald-400">14 countries</span>
      </div>
      <div className="absolute top-3 right-3 inline-flex items-center gap-1 text-[10px] font-mono text-emerald-400">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" /> live
      </div>
    </div>
  );
}

function AlertsMock() {
  const pool = useMemo(() => [
    { ch: "slack",   msg: "✓ /api/login healthy · 99.99% 24h",   k: "ok" },
    { ch: "discord", msg: "↗ CPU 78% on web-01 · scaled to 1.5", k: "warn" },
    { ch: "sms",     msg: "→ Deploy succeeded · v1.4.2",         k: "ok" },
    { ch: "discord", msg: "✓ DNS propagated · cdn.app.io",       k: "ok" },
    { ch: "slack",   msg: "↗ Mem 91% on api-02 · auto-restart",  k: "warn" },
    { ch: "wapp",    msg: "→ TLS renewed · servunit.app",         k: "ok" },
    { ch: "slack",   msg: "✓ Build complete · 38s · 245 MB",     k: "ok" },
  ], []);
  const [items, setItems] = useState(() => pool.slice(0, 3).map((p, i) => ({ ...p, id: i, t: nowMin() })));
  useEffect(() => {
    const id = setInterval(() => {
      setItems((prev) => {
        const next = pool[Math.floor(Math.random() * pool.length)];
        return [
          { ...next, id: Date.now(), t: nowMin() },
          ...prev,
        ].slice(0, 3);
      });
    }, 3500);
    return () => clearInterval(id);
  }, [pool]);

  return (
    <div className="space-y-2" data-testid="alerts-live">
      {items.map((it) => (
        <motion.div
          key={it.id}
          initial={{ opacity: 0, y: -10, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.35 }}
          className="flex items-center gap-3 border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-xs font-mono"
        >
          <span className={`uppercase text-[9px] tracking-[0.25em] px-1.5 py-0.5 border ${it.k === "warn" ? "text-yellow-400 border-yellow-500/40" : "text-emerald-400 border-emerald-500/30"}`}>{it.ch}</span>
          <span className="text-zinc-300 flex-1 truncate">{it.msg}</span>
          <span className="text-zinc-600">{it.t}</span>
        </motion.div>
      ))}
    </div>
  );
}

function nowMin() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function WorkspaceSwitcherMock() {
  const ws = useMemo(() => [
    { name: "Beyond Meassure", apps: 4,  deploys: 28 },
    { name: "ServUnit",        apps: 6,  deploys: 41 },
    { name: "Stella Labs",     apps: 8,  deploys: 17 },
    { name: "OakRoot",         apps: 10, deploys: 52 },
  ], []);
  const [active, setActive] = useState(0);
  return (
    <div className="border border-zinc-800 bg-zinc-950/50" data-testid="Workspace-switcher">
      <div className="px-3 py-2 border-b border-zinc-800 text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500 flex items-center justify-between">
        <span>Workspaces</span>
        <span className="text-cyan-400">{ws[active].deploys} deploys / 30d</span>
      </div>
      <div className="divide-y divide-zinc-900">
        {ws.map((w, i) => {
          const isActive = i === active;
          return (
            <button
              type="button"
              key={w.name}
              onClick={() => setActive(i)}
              className="w-full text-left flex items-center justify-between px-3 py-2 text-xs font-mono hover:bg-zinc-900/40 transition-colors group"
              data-testid={`Workspace-${i}`}
            >
              <span className="flex items-center gap-2">
                <motion.span
                  animate={{ scale: isActive ? 1.2 : 1 }}
                  className={`h-1.5 w-1.5 rounded-full ${isActive ? "bg-cyan-400 shadow-[0_0_6px_2px_rgba(6,182,212,0.6)]" : "bg-zinc-700 group-hover:bg-zinc-500"}`}
                />
                <span className={isActive ? "text-cyan-300" : "text-zinc-400 group-hover:text-zinc-200"}>{w.name}</span>
              </span>
              <span className="text-zinc-600">{w.apps} apps</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function BentoCard({ span = "lg:col-span-1 lg:row-span-1", overline, title, body, children, testId }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5 }}
      whileHover={{ y: -3, borderColor: "rgba(6,182,212,0.5)", boxShadow: "0 0 30px -10px rgba(6,182,212,0.35)" }}
      className={`relative border border-zinc-800 bg-zinc-950/40 p-6 lg:p-8 overflow-hidden flex flex-col transition-shadow ${span}`}
      data-testid={testId}
    >
      <motion.div
        className="absolute -top-20 -right-20 w-60 h-60 rounded-full bg-cyan-500/[0.04] blur-3xl pointer-events-none"
        animate={{ scale: [1, 1.15, 1], opacity: [0.4, 0.7, 0.4] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="relative">
        <Overline>{overline}</Overline>
        <h3 className="mt-3 font-display text-xl md:text-2xl font-semibold tracking-tight text-white">{title}</h3>
        <p className="mt-2 text-sm text-zinc-400 leading-relaxed">{body}</p>
      </div>
      <div className="relative mt-5 flex-1">{children}</div>
    </motion.div>
  );
}

function TabbedCard({ tabs, testId }) {
  const [active, setActive] = useState(tabs[0].id);
  const cur = tabs.find((t) => t.id === active) || tabs[0];
  return (
    <div className="flex flex-col h-full" data-testid={testId}>
      <div className="flex gap-1 mb-3 border-b border-zinc-800/80">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActive(t.id)}
            className={`px-2.5 py-1.5 text-[10px] font-mono uppercase tracking-[0.25em] border-b -mb-px inline-flex items-center gap-1.5 transition-colors
              ${active === t.id ? "border-cyan-400 text-cyan-400" : "border-transparent text-zinc-500 hover:text-zinc-300"}`}
            data-testid={`${testId}-tab-${t.id}`}
          >
            {t.icon && <t.icon className="h-3 w-3" />}
            {t.label}
            {t.soon && <span className="ml-1 px-1 py-px text-[8px] tracking-[0.2em] bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 rounded-none">soon</span>}
          </button>
        ))}
      </div>
      <motion.div
        key={active}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="flex-1"
      >
        {cur.content}
      </motion.div>
    </div>
  );
}

function HeatmapPreview() {
  // Fake page-screenshot with overlaid heat blobs that pulse.
  const blobs = useMemo(() => [
    { x: 25, y: 30, r: 38, op: 0.55, c: "rgba(239,68,68,0.55)" }, // red — heavy
    { x: 50, y: 28, r: 28, op: 0.45, c: "rgba(245,158,11,0.55)" }, // orange
    { x: 75, y: 35, r: 24, op: 0.40, c: "rgba(245,158,11,0.45)" },
    { x: 33, y: 70, r: 30, op: 0.50, c: "rgba(234,179,8,0.40)" },
    { x: 65, y: 78, r: 22, op: 0.35, c: "rgba(16,185,129,0.45)" }, // green — light
    { x: 50, y: 55, r: 34, op: 0.45, c: "rgba(239,68,68,0.40)" },
  ], []);
  return (
    <div className="relative h-[160px] border border-zinc-800 overflow-hidden" data-testid="heatmap-preview">
      {/* Wireframe of a fake page */}
      <div className="absolute inset-0 bg-zinc-950">
        <div className="h-5 bg-zinc-900 border-b border-zinc-800 flex items-center px-2 gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-zinc-700" />
          <span className="h-1.5 w-1.5 rounded-full bg-zinc-700" />
          <span className="h-1.5 w-1.5 rounded-full bg-zinc-700" />
          <span className="ml-2 h-1 w-20 bg-zinc-800 rounded" />
        </div>
        <div className="p-3 space-y-1.5">
          <div className="h-1.5 w-2/3 bg-zinc-800 rounded" />
          <div className="h-1.5 w-1/2 bg-zinc-800 rounded" />
          <div className="grid grid-cols-3 gap-1.5 mt-3">
            <div className="h-9 bg-zinc-800/80 border border-zinc-800" />
            <div className="h-9 bg-zinc-800/80 border border-zinc-800" />
            <div className="h-9 bg-zinc-800/80 border border-zinc-800" />
          </div>
          <div className="h-1.5 w-3/4 bg-zinc-800 rounded mt-2" />
          <div className="h-1.5 w-1/3 bg-zinc-800 rounded" />
        </div>
      </div>
      {/* Pulsing heat blobs */}
      {blobs.map((b, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full pointer-events-none"
          style={{
            left: `${b.x}%`,
            top: `${b.y}%`,
            width: b.r * 2,
            height: b.r * 2,
            translateX: "-50%",
            translateY: "-50%",
            background: `radial-gradient(circle, ${b.c} 0%, transparent 70%)`,
            mixBlendMode: "screen",
          }}
          animate={{ opacity: [b.op * 0.6, b.op, b.op * 0.6], scale: [1, 1.08, 1] }}
          transition={{ duration: 3 + (i % 3), repeat: Infinity, ease: "easeInOut", delay: i * 0.3 }}
        />
      ))}
      <div className="absolute top-2 right-2 inline-flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-[0.25em] bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
        <Sparkles className="h-2.5 w-2.5" /> live
      </div>
      <div className="absolute bottom-2 left-2 text-[10px] font-mono text-zinc-400">
        <span className="text-red-400">3 hot</span> · <span className="text-yellow-400">1 mid</span> · <span className="text-emerald-400">1 cool</span>
      </div>
    </div>
  );
}

function BuildPipelineMock() {
  // Cycles through: queued → cloning → building → deploying → live
  const phases = useMemo(() => [
    { label: "QUEUED",    pct: 5,  hint: "git push received" },
    { label: "CLONING",   pct: 22, hint: "fetching servunit/web" },
    { label: "BUILDING",  pct: 58, hint: "nixpacks · 24/40 steps" },
    { label: "DEPLOYING", pct: 88, hint: "rolling out · eu" },
    { label: "LIVE",      pct: 100, hint: "https://servunit.app" },
  ], []);
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setI((x) => (x + 1) % phases.length), 1800);
    return () => clearInterval(id);
  }, [phases.length]);
  const cur = phases[i];
  return (
    <div className="space-y-3" data-testid="build-pipeline">
      <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.3em]">
        <Github className="h-3.5 w-3.5 text-zinc-300" />
        <span className="text-zinc-300">servunit/web</span>
        <span className="text-zinc-600">·</span>
        <span className="text-cyan-400">{cur.label}</span>
        <span className="ml-auto text-zinc-500 normal-case tracking-normal text-[10px]">{cur.hint}</span>
      </div>
      <div className="relative h-1 bg-zinc-900 overflow-hidden">
        <motion.div
          className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyan-500 to-emerald-400"
          animate={{ width: `${cur.pct}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        />
      </div>
      <div className="grid grid-cols-5 gap-1">
        {phases.map((p, idx) => (
          <div key={p.label} className="flex flex-col items-center">
            <span
              className={`h-2 w-2 rounded-full transition-colors ${
                idx <= i ? "bg-cyan-400 shadow-[0_0_6px_2px_rgba(6,182,212,0.5)]" : "bg-zinc-800"
              }`}
            />
            <span className={`mt-1 text-[8px] font-mono ${idx === i ? "text-cyan-400" : "text-zinc-600"}`}>{p.label}</span>
          </div>
        ))}
      </div>
      {/* Tech stack chips that show up under "BUILDING" */}
      <div className="flex flex-wrap gap-1 pt-2 border-t border-zinc-800/60">
        {["nextjs", "node-20", "postgres:15", "redis:7", "tailwind"].map((t, idx) => (
          <motion.span
            key={t}
            animate={{ opacity: i >= 2 ? 1 : 0.3 }}
            transition={{ delay: idx * 0.05 }}
            className={`text-[9px] font-mono px-1.5 py-0.5 border ${
              i >= 2 ? "bg-cyan-500/10 text-cyan-300 border-cyan-500/30" : "bg-zinc-950 text-zinc-600 border-zinc-800"
            }`}
          >
            {t}
          </motion.span>
        ))}
      </div>
    </div>
  );
}

function ScheduleAuditMock() {
  // Mini-cron + live audit feed, side-by-side.
  return (
    <div className="grid grid-cols-1 gap-2" data-testid="schedule-audit">
      <IlluCron />
      <IlluAudit />
    </div>
  );
}

function Features() {
  return (
    <Section id="features" className="py-24 lg:py-32 bg-zinc-950/30">
      <Container>
        <div className="mb-12 max-w-3xl">
          <Overline>What ships today</Overline>
          <h2 className="mt-3 font-display text-3xl md:text-5xl font-bold tracking-tighter text-white">
            Real features. Real data. <span className="text-cyan-400">Built in.</span>
          </h2>
          <p className="mt-3 text-zinc-400 text-base sm:text-lg">
            Every dashboard you'd otherwise stitch together (Datadog · Plausible · Cloudflare · Sentry) — already inside.
          </p>
        </div>

        {/* Compact 5-card bento: 3 wide on top, 2 wide on bottom */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <BentoCard
            span="lg:col-span-2"
            overline="Live observability"
            title="Metrics, audits and alerts — in one pane."
            body="Container stats every 1.6s · daily Lighthouse · Slack/Discord/SMS alerts. Switch tabs without leaving the dashboard."
            testId="feature-observability"
          >
            <TabbedCard
              testId="observability-tabs"
              tabs={[
                { id: "metrics",   label: "Metrics",   icon: Activity, content: <MetricsGraphMock /> },
                { id: "pagespeed", label: "PageSpeed", icon: Gauge,    content: <PageSpeedGauge /> },
                { id: "alerts",    label: "Alerts",    icon: Bell,     content: <AlertsMock /> },
              ]}
            />
          </BentoCard>

          <BentoCard
            overline="Web analytics"
            title="Cookieless visitors + heatmaps."
            body="Privacy-first tracker (1 KB · sendBeacon · GDPR by default). In-house click & rage-click heatmaps — no third-party scripts."
            testId="feature-analytics"
          >
            <TabbedCard
              testId="analytics-tabs"
              tabs={[
                { id: "visitors", label: "Visitors", icon: Globe, content: <VisitorMapMock /> },
                { id: "heatmap",  label: "Heatmap",  icon: Sparkles, content: <HeatmapPreview /> },
              ]}
            />
          </BentoCard>

          <BentoCard
            overline="Build pipeline"
            title="Push → live URL in 41 seconds."
            body="Nixpacks-auto-detected stack, rolling deploy, custom domains + TLS — every step visible end-to-end."
            testId="feature-pipeline"
          >
            <BuildPipelineMock />
          </BentoCard>

          <BentoCard
            overline="Agency multi-tenant"
            title="Workspaces per customer."
            body="Click to switch fleets. Per-Workspace billing, members, audit logs and credit budget — out of the box."
            testId="feature-Workspaces"
          >
            <WorkspaceSwitcherMock />
          </BentoCard>

          <BentoCard
            overline="Audit & schedule"
            title="Cron + event log, live."
            body="Toggle background jobs from the dashboard. Every action — by anyone — is logged with timestamps and actor."
            testId="feature-audit"
          >
            <ScheduleAuditMock />
          </BentoCard>
        </div>

        {/* Quick capability strip — pure copy, no boxes, dense */}
        <div className="mt-10 border-t border-zinc-900 pt-8">
          <div className="text-[10px] uppercase tracking-[0.4em] font-mono text-zinc-500 mb-4">
            Also in the box
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-x-6 gap-y-3">
            {[
              { icon: GitBranch, label: "PR previews" },
              { icon: Database,  label: "Managed DBs" },
              { icon: Globe,     label: "Custom domains + DNS" },
              { icon: Lock,      label: "RBAC + audit" },
              { icon: Cpu,       label: "Resource limits" },
              { icon: ShieldCheck, label: "TLS + Let's Encrypt" },
            ].map((c) => (
              <div key={c.label} className="flex items-center gap-2 text-xs font-mono text-zinc-400 hover:text-zinc-200 transition-colors">
                <c.icon className="h-3.5 w-3.5 text-cyan-400/80 shrink-0" />
                <span className="truncate">{c.label}</span>
              </div>
            ))}
          </div>
        </div>
      </Container>
    </Section>
  );
}

/* ─── Small-feature illustrations ─── */

function IlluPRPreviews() {
  return (
    <div className="bg-black/40 border border-zinc-800 p-3 font-mono text-[10px]">
      <svg viewBox="0 0 200 52" className="w-full h-10">
        <line x1="10" y1="32" x2="190" y2="32" stroke="#3f3f46" strokeWidth="1" />
        {[30, 60, 90, 120, 150, 180].map((x) => (
          <circle key={x} cx={x} cy="32" r="3" fill="#3f3f46" />
        ))}
        <path d="M90 32 Q105 18 120 12" stroke={CYAN} strokeWidth="1.5" fill="none" />
        <circle cx="120" cy="12" r="4" fill={CYAN} />
        <text x="128" y="15" fill="#a1a1aa" fontSize="9" fontFamily="JetBrains Mono">pr-42</text>
        <text x="6" y="48" fill="#52525b" fontSize="8" fontFamily="JetBrains Mono">main</text>
      </svg>
      <div className="mt-1 flex items-center justify-between">
        <span className="text-zinc-500">pr-42-preview.dh.app</span>
        <span className="text-emerald-400">live</span>
      </div>
    </div>
  );
}

function IlluDatabases() {
  const rows = [
    { name: "postgres", port: "5432", state: "attached", color: "text-emerald-400" },
    { name: "redis",    port: "6379", state: "attached", color: "text-emerald-400" },
    { name: "mysql",    port: "3306", state: "ready",    color: "text-cyan-400" },
  ];
  return (
    <div className="bg-black/40 border border-zinc-800 p-2.5 font-mono text-[10px] space-y-1">
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-2">
          <Database className="h-3 w-3 text-zinc-500" />
          <span className="text-zinc-300">{r.name}</span>
          <span className="text-zinc-600">:{r.port}</span>
          <span className={`ml-auto ${r.color}`}>● {r.state}</span>
        </div>
      ))}
    </div>
  );
}

function IlluDomains() {
  return (
    <div className="bg-black/40 border border-zinc-800 p-2.5 font-mono text-[10px] space-y-1">
      <div className="flex items-center gap-1.5 text-zinc-200">
        <Globe className="h-3 w-3 text-cyan-400" />
        <span>yourapp.com</span>
        <Lock className="h-3 w-3 ml-auto text-emerald-400" />
      </div>
      <div className="text-zinc-500">A      <span className="text-zinc-300">76.76.21.21</span></div>
      <div className="text-zinc-500">CNAME  <span className="text-zinc-300">*.yourapp.com → cdn</span></div>
      <div className="text-zinc-500">MX     <span className="text-zinc-300">10 mx.yourapp.com</span></div>
    </div>
  );
}

function IlluAudit() {
  const pool = useMemo(() => [
    { who: "martijn",  what: "deploy v1.4.2",        k: "text-emerald-400" },
    { who: "ci/auto",  what: "resource ↑ 0.5→1.0",   k: "text-cyan-400" },
    { who: "admin",    who2: "invited @bob",         k: "text-zinc-300" },
    { who: "ci/auto",  what: "TLS renewed",          k: "text-emerald-400" },
    { who: "sara",     what: "rollback v1.4.1",      k: "text-yellow-400" },
    { who: "ci/auto",  what: "scaled web-01 →2",     k: "text-cyan-400" },
    { who: "martijn",  what: "edited env vars",      k: "text-zinc-300" },
  ], []);
  const [items, setItems] = useState(() => pool.slice(0, 3).map((p, i) => ({ ...p, id: i, t: nowMin() })));
  useEffect(() => {
    const id = setInterval(() => {
      setItems((prev) => {
        const next = pool[Math.floor(Math.random() * pool.length)];
        return [{ ...next, id: Date.now(), t: nowMin() }, ...prev].slice(0, 3);
      });
    }, 4500);
    return () => clearInterval(id);
  }, [pool]);
  return (
    <div className="bg-black/40 border border-zinc-800 p-2.5 font-mono text-[10px] space-y-1 overflow-hidden" data-testid="illu-audit">
      {items.map((r) => (
        <motion.div
          key={r.id}
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="flex items-center gap-2"
        >
          <span className="text-zinc-600">{r.t}</span>
          <span className="text-zinc-500">{r.who}</span>
          <span className={`ml-auto truncate ${r.k}`}>{r.what || r.who2}</span>
        </motion.div>
      ))}
    </div>
  );
}

function IlluCron() {
  const initial = useMemo(() => [
    { expr: "0 */6 * * *", name: "send_digest_email", state: "✓ 04:00", on: true },
    { expr: "@daily",      name: "cleanup_uploads",   state: "✓ 00:00", on: true },
    { expr: "*/15 * * *",  name: "refresh_cache",     state: "✓ 09:45", on: true },
  ], []);
  const [rows, setRows] = useState(initial);
  const toggle = (i) => setRows((p) => p.map((r, idx) => idx === i ? { ...r, on: !r.on } : r));
  return (
    <div className="bg-black/40 border border-zinc-800 p-2.5 font-mono text-[10px] space-y-1" data-testid="illu-cron">
      {rows.map((r, i) => (
        <button
          type="button"
          key={i}
          onClick={() => toggle(i)}
          className="w-full grid grid-cols-[auto_1fr_auto_auto] gap-2 items-center hover:bg-zinc-900/40 px-1 py-0.5 transition-colors"
          data-testid={`illu-cron-toggle-${i}`}
        >
          <span className={r.on ? "text-cyan-400" : "text-zinc-600 line-through"}>{r.expr}</span>
          <span className={`text-left truncate ${r.on ? "text-zinc-300" : "text-zinc-600 line-through"}`}>{r.name}</span>
          <span className={r.on ? "text-emerald-400" : "text-zinc-600"}>{r.on ? r.state : "paused"}</span>
          <span className={`h-3 w-5 border rounded-sm relative transition-colors ${r.on ? "bg-cyan-500/30 border-cyan-500/60" : "border-zinc-700"}`}>
            <span className={`absolute top-[1px] h-2 w-2 bg-zinc-200 transition-all ${r.on ? "left-[10px]" : "left-[1px]"}`} />
          </span>
        </button>
      ))}
    </div>
  );
}

function IlluResources() {
  const bars = [
    { l: "vCPU", v: 25, max: "0.5 / 2.0" },
    { l: "RAM",  v: 75, max: "768 / 1024 MB" },
    { l: "Disk", v: 15, max: "1.2 / 8.0 GB" },
  ];
  return (
    <div className="bg-black/40 border border-zinc-800 p-2.5 font-mono text-[10px] space-y-1.5">
      {bars.map((b) => (
        <div key={b.l} className="flex items-center gap-2">
          <span className="text-zinc-500 w-9 shrink-0">{b.l}</span>
          <div className="flex-1 h-1.5 bg-zinc-900 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              whileInView={{ width: `${b.v}%` }}
              viewport={{ once: true }}
              transition={{ duration: 1.1, ease: "easeOut" }}
              className="h-full bg-cyan-400"
            />
          </div>
          <span className="text-zinc-500 w-24 text-right shrink-0">{b.max}</span>
        </div>
      ))}
    </div>
  );
}

const SMALL_FEATURES = [
  { id: "pr-previews",   icon: GitBranch, title: "PR previews",            body: "Every pull request gets its own URL + container, killed on merge.",        illu: <IlluPRPreviews /> },
  { id: "databases",     icon: Database,  title: "Managed databases",       body: "Postgres · MySQL · Redis attached to apps with zero-touch creds.",         illu: <IlluDatabases /> },
  { id: "domains",       icon: Globe,     title: "Custom domains + DNS",    body: "Cloudflare DNS provisioned automatically. Auto-SSL via Let's Encrypt.",    illu: <IlluDomains /> },
  { id: "audit",         icon: Lock,      title: "Audit log + RBAC",        body: "Every action logged. Owner / Admin / Developer / Viewer roles.",         illu: <IlluAudit /> },
  { id: "resources",     icon: Cpu,       title: "Per-app resource limits", body: "Dial vCPU, RAM, and storage; pay only what you use via credits.",         illu: <IlluResources /> },
  { id: "cron",          icon: Bell,      title: "Custom cron tasks",       body: "Schedule background jobs without spinning up new infra.",                  illu: <IlluCron /> },
];

/* ───────────────────────── Comparison table ───────────────────────── */

function Compare() {
  // Two-tier comparison: the things that actually move the needle when
  // someone is shopping for an alternative (top table) + the trust-builder
  // "yes we do the basics too" (bottom). One flat list with concrete
  // badges (Add-on / Basic) is more credible than vague "limited" pills —
  // developers want to see the actual gap, not soft language.
  const WHY_SWITCH = [
    { f: "No config required (zero DevOps)",                                vc: false,    rd: false },
    { f: "Single dashboard — no external tools needed",                      vc: false,    rd: false },
    { f: "Built-in analytics + monitoring + alerts",                         vc: false,    rd: false },
    { f: "Agency workspaces — multi-client billing & permissions",           vc: false,    rd: false },
    { f: "White-label PDF invoices per client",                              vc: false,    rd: false },
    { f: "Predictable pricing — no usage surprises",                         vc: false,    rd: false },
    { f: "Full pipeline visibility (deploy + runtime logs)",                 vc: "basic",  rd: "basic" },
    { f: "EU-hosted by default (NL/DE/FR · GDPR-first)",                     vc: false,    rd: "addon" },
  ];
  const ON_PAR = [
    { f: "Push → live deploy in seconds",          vc: true, rd: true },
    { f: "PR preview deployments",                 vc: true, rd: true },
    { f: "Auto-detect stack (Next.js, Node, etc.)",vc: true, rd: true },
    { f: "Custom domains & TLS included",          vc: true, rd: true },
  ];

  function Cell({ v }) {
    if (v === true)
      return <span className="inline-flex items-center gap-1 text-signal-live"><Check className="h-4 w-4" /></span>;
    if (v === false)
      return <span className="inline-flex items-center gap-1 text-zinc-600"><XIcon className="h-4 w-4" /></span>;
    if (v === "basic")
      return <span className="inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider border border-amber-400/40 text-amber-300 font-mono">basic</span>;
    if (v === "addon")
      return <span className="inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider border border-amber-400/40 text-amber-300 font-mono">add-on</span>;
    return <span className="text-zinc-600">—</span>;
  }

  function CompareTable({ rows, accent, testId }) {
    return (
      <div className={`border ${accent} overflow-x-auto`} data-testid={testId}>
        <table className="w-full text-sm min-w-[640px]">
          <thead>
            <tr className="border-b border-white/[0.06] text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">
              <th className="text-left p-4 font-normal w-1/2">Capability</th>
              <th className="p-4 font-normal text-cyan-300">DeployUnit</th>
              <th className="p-4 font-normal">Vercel</th>
              <th className="p-4 font-normal">Render</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <motion.tr
                key={r.f}
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.03 }}
                className="border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02]"
              >
                <td className="p-4 text-zinc-300">{r.f}</td>
                <td className="p-4 text-center"><Cell v={true} /></td>
                <td className="p-4 text-center"><Cell v={r.vc} /></td>
                <td className="p-4 text-center"><Cell v={r.rd} /></td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <Section id="compare" className="py-28 lg:py-36">
      <Container>
        <div className="mb-14 max-w-2xl">
          <Overline>Why switch</Overline>
          <h2 className="mt-4 font-display text-4xl md:text-6xl font-bold tracking-tighter text-white leading-[1.05]">
            Why teams switch from <span className="line-through decoration-zinc-700 decoration-2">Vercel</span>.
          </h2>
          <p className="mt-5 text-lg text-zinc-400 leading-relaxed">
            Apples-to-apples — the four things that send people looking for an alternative.
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="grid md:grid-cols-2 gap-px bg-zinc-900 border border-zinc-900 mb-12"
          data-testid="why-switch-summary"
        >
          {[
            { title: "Predictable pricing", vercel: "Surprise bills at scale", us: "Flat plans. No usage gotchas." },
            { title: "Everything included", vercel: "6 SaaS tools required", us: "Hosting + analytics + monitoring + alerts." },
            { title: "Built for client work", vercel: "Built for solo devs", us: "Workspaces, per-client billing, audit logs." },
            { title: "EU-hosted by default", vercel: "US-only infrastructure", us: "NL/DE/FR data centers · GDPR-first." },
          ].map((row, i) => (
            <motion.div
              key={row.title}
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.04 }}
              className="bg-black p-7"
            >
              <div className="font-display text-xl text-zinc-100 mb-4">{row.title}</div>
              <div className="space-y-2.5 text-sm">
                <div className="flex items-start gap-2.5 text-zinc-500">
                  <XIcon className="h-4 w-4 mt-0.5 text-signal-failed/80 flex-shrink-0" />
                  <span><span className="text-zinc-400 font-mono text-[10px] uppercase tracking-[0.25em] mr-2">Vercel</span>{row.vercel}</span>
                </div>
                <div className="flex items-start gap-2.5 text-zinc-200">
                  <Check className="h-4 w-4 mt-0.5 text-signal-live flex-shrink-0" />
                  <span><span className="text-cyan-400 font-mono text-[10px] uppercase tracking-[0.25em] mr-2">DeployUnit</span>{row.us}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          data-testid="compare-grouped"
        >
          {/* Primary table — 8 reasons to switch */}
          <div className="flex items-end justify-between flex-wrap gap-3 mt-12 mb-4">
            <div>
              <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.35em] text-cyan-300">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
                Reasons to switch
              </div>
              <h3 className="mt-2 font-display text-2xl md:text-3xl tracking-tighter text-white">
                {WHY_SWITCH.length} things you only get on DeployUnit.
              </h3>
            </div>
            <div className="inline-flex items-center px-3 py-1 text-[10px] font-mono uppercase tracking-[0.3em] border bg-cyan-950/40 text-cyan-300 border-cyan-500/40">
              {WHY_SWITCH.length} features
            </div>
          </div>
          <CompareTable rows={WHY_SWITCH} accent="bg-cyan-950/20 border-cyan-500/30" testId="compare-group-new" />

          {/* On-par table — trust builder */}
          <div className="flex items-end justify-between flex-wrap gap-3 mt-14 mb-4">
            <div>
              <div className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.35em] text-zinc-400">
                <span className="h-1.5 w-1.5 rounded-full bg-zinc-500" />
                On par
              </div>
              <h3 className="mt-2 font-display text-2xl md:text-3xl tracking-tighter text-white">
                Table-stakes — yes, we do these too.
              </h3>
            </div>
            <div className="inline-flex items-center px-3 py-1 text-[10px] font-mono uppercase tracking-[0.3em] border bg-zinc-900 text-zinc-400 border-zinc-700">
              {ON_PAR.length} features
            </div>
          </div>
          <CompareTable rows={ON_PAR} accent="bg-zinc-950/60 border-zinc-800" testId="compare-group-on_par" />
        </motion.div>
      </Container>
    </Section>
  );
}

/* ───────────────────────── Green energy spotlight ───────────────────────── */

function GreenEnergy() {
  // Live-counting tree counter — climbs from 0 to current on viewport
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const TARGET_TREES = 1247; // climbs daily — wire to /api/sustainability later
  const [trees, setTrees] = useState(0);
  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    const dur = 1800;
    const tick = (t) => {
      const p = Math.min(1, (t - start) / dur);
      setTrees(Math.round(TARGET_TREES * (1 - Math.pow(1 - p, 3))));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [inView]);

  return (
    <Section id="green" className="relative py-32 overflow-hidden">
      <div className="absolute inset-0 -z-10">
        <img
          src="https://images.unsplash.com/photo-1558725148-e95a6523628c?crop=entropy&cs=srgb&fm=jpg&q=85&w=2400"
          alt=""
          className="w-full h-full object-cover opacity-30"
          loading="lazy"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-black via-black/70 to-black/30" />
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-950/40 to-black/70 mix-blend-overlay" />
      </div>

      {/* Floating particles */}
      {[...Array(14)].map((_, i) => (
        <motion.span
          key={i}
          initial={{ opacity: 0, y: 30 }}
          animate={{
            opacity: [0, 0.6, 0],
            y: [-20, -180],
            x: [0, (i % 2 ? 30 : -25)],
          }}
          transition={{
            duration: 6 + (i % 4),
            delay: i * 0.4,
            repeat: Infinity,
            ease: "easeOut",
          }}
          className="absolute h-1 w-1 rounded-full bg-emerald-400 shadow-[0_0_8px_2px_rgba(16,185,129,0.55)]"
          style={{ left: `${5 + i * 6}%`, bottom: "20%" }}
        />
      ))}

      <Container>
        <div ref={ref} className="grid lg:grid-cols-[1.1fr_1fr] gap-12 items-center">
          <motion.div initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
            <motion.div variants={fadeUp}><Overline color="text-emerald-400">Sustainability</Overline></motion.div>
            <motion.h2
              variants={fadeUp}
              className="mt-4 font-display text-4xl md:text-5xl font-bold tracking-tighter text-white leading-none"
            >
              Greener <span className="text-emerald-400">by design.</span>
            </motion.h2>
            <motion.p variants={fadeUp} className="mt-5 text-base text-zinc-300 max-w-xl">
              Our EU datacenters run mostly on renewable wind & solar — and we invest every quarter to push that further.
              No carbon-offset accounting tricks, just real renewable contracts and full transparency on the journey.
            </motion.p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="relative flex items-center justify-center"
          >
            <div className="relative h-72 w-72 flex items-center justify-center">
              {/* Concentric radar-style pulse rings */}
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="absolute rounded-full border border-emerald-400/30"
                  animate={{
                    width: ["40%", "100%"],
                    height: ["40%", "100%"],
                    opacity: [0.45, 0],
                  }}
                  transition={{
                    duration: 3.6,
                    delay: i * 1.2,
                    repeat: Infinity,
                    ease: "easeOut",
                  }}
                />
              ))}
              {/* Static outer ring */}
              <span className="absolute inset-0 rounded-full border border-emerald-500/20" />
              {/* Static inner medal */}
              <div className="relative z-10 h-40 w-40 rounded-full border border-emerald-500/40 bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center">
                <Leaf className="h-8 w-8 text-emerald-400" strokeWidth={1.5} />
                <div className="mt-2.5 font-display text-base font-bold text-white leading-tight text-center">
                  Carbon<br />Conscious
                </div>
                <div className="mt-1 text-[8px] uppercase tracking-[0.3em] font-mono text-emerald-400/70">by default</div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Team Trees partnership */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mt-16 relative border border-emerald-500/30 bg-gradient-to-r from-emerald-950/40 via-black/70 to-black/40 p-8 lg:p-10 overflow-hidden"
          data-testid="team-trees-block"
        >
          {/* Animated trees grove background */}
          <svg className="absolute right-6 bottom-0 opacity-20 pointer-events-none" width="320" height="160" viewBox="0 0 320 160" aria-hidden>
            {[20, 75, 130, 185, 240, 295].map((x, i) => (
              <g key={i} transform={`translate(${x},${120 - (i % 2) * 14})`}>
                <path d="M0 0 L-14 30 L-7 30 L-18 56 L18 56 L7 30 L14 30 Z" fill="#10b981" />
                <rect x="-3" y="56" width="6" height="14" fill="#064e3b" />
              </g>
            ))}
          </svg>

          <div className="relative grid lg:grid-cols-[auto_1fr_auto] gap-6 items-center">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className="h-14 w-14 border-2 border-emerald-400 bg-emerald-500/10 flex items-center justify-center">
                  <Leaf className="h-7 w-7 text-emerald-400" />
                </div>
                <motion.span
                  animate={{ scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-emerald-400 shadow-[0_0_8px_2px_rgba(16,185,129,0.7)]"
                />
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-emerald-400">Partner · Workspace Trees</div>
                <div className="font-display text-lg font-bold text-white leading-tight">1 deploy = 1 tree.</div>
              </div>
            </div>

            <p className="text-sm sm:text-base text-zinc-300 max-w-xl">
              Every single app you deploy through DeployUnit plants <span className="text-emerald-400 font-semibold">one extra tree</span> through our partnership with{" "}
              <a href="https://teamtrees.org" target="_blank" rel="noreferrer" className="underline text-emerald-400 hover:text-emerald-300" data-testid="team-trees-link">teamtrees.org</a>. Real trees, real coordinates, real impact — verified by the Arbor Day Foundation.
            </p>

            <div className="flex flex-col items-end text-right">
              <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-400 mb-1">trees planted</div>
              <div className="font-display text-4xl font-bold text-emerald-400 tabular-nums" data-testid="team-trees-count">
                {trees.toLocaleString()}
              </div>
              <div className="text-[10px] font-mono text-zinc-500 mt-1">and counting</div>
            </div>
          </div>
        </motion.div>
      </Container>
    </Section>
  );
}

/* ───────────────────────── Roadmap teaser ───────────────────────── */

function Roadmap() {
  const items = [
    { icon: Activity, title: "Session replays (rrweb)",          cat: "Analytics" },
    { icon: GitBranch, title: "Database branching",               cat: "DX" },
    { icon: Bot,      title: "AI Code Co-pilot",                  cat: "DX" },
    { icon: Sparkles, title: "Visual deploy diffs",               cat: "DX" },
    { icon: FileText, title: "Branded client reports",        cat: "Business" },
    { icon: Code2,    title: "Developers API",                    cat: "DX" },
    { icon: Mail,     title: "Mailserver hosting",                cat: "Infra" },
    { icon: Globe,    title: "DNS Manager",                       cat: "Infra" },
  ];
  return (
    <Section className="py-24 lg:py-32 bg-zinc-950/30">
      <Container>
        <div className="flex items-end justify-between flex-wrap gap-4 mb-10">
          <div>
            <Overline>What's next</Overline>
            <h2 className="mt-3 font-display text-3xl md:text-5xl font-bold tracking-tighter text-white">Shipping next.</h2>
            <p className="mt-3 text-zinc-400 max-w-xl">8 features in active development. Join the waitlist to be the first to know.</p>
          </div>
          <OutlineBtn to="/login" testId="roadmap-view-all" className="text-xs">View full roadmap →</OutlineBtn>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {items.map((it, i) => (
            <motion.div
              key={it.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              className="border border-dashed border-zinc-800 p-5 hover:border-cyan-500/40 hover:bg-zinc-950/40 transition-colors"
              data-testid={`roadmap-tile-${i}`}
            >
              <div className="flex items-center justify-between mb-3">
                <it.icon className="h-4 w-4 text-cyan-400/80" />
                <span className="text-[9px] font-mono uppercase tracking-[0.3em] text-zinc-600">soon</span>
              </div>
              <div className="font-display text-sm font-semibold text-zinc-200 leading-snug">{it.title}</div>
              <div className="mt-1 text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-600">{it.cat}</div>
            </motion.div>
          ))}
        </div>
      </Container>
    </Section>
  );
}

/* ───────────────────────── Stats marquee ───────────────────────── */

function StatsTicker() {
  const stats = [
    "1.2M deploys / month",
    "99.99% platform uptime",
    "47ms median response",
    "100% EU-hosted infrastructure",
    "14-day money back",
    "From €9/mo · all-inclusive",
    "Used by 240+ agencies",
  ];
  const doubled = [...stats, ...stats];
  return (
    <Section className="py-10 border-y border-zinc-900 overflow-hidden bg-black">
      <div className="relative">
        <motion.div
          className="flex gap-12 whitespace-nowrap will-change-transform"
          animate={{ x: ["0%", "-50%"] }}
          transition={{ duration: 35, repeat: Infinity, ease: "linear" }}
        >
          {doubled.map((s, i) => (
            <div key={i} className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">
              <Sparkles className="h-3 w-3 text-cyan-500" />
              {s}
            </div>
          ))}
        </motion.div>
        <div className="absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-black to-transparent" />
        <div className="absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-black to-transparent" />
      </div>
    </Section>
  );
}

/* ───────────────────────── Final CTA ───────────────────────── */

function FinalCTA() {
  return (
    <Section className="relative py-32 overflow-hidden">
      <div className="absolute inset-0 -z-10">
        <ConstellationCanvas density={40} />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-black/80 to-black" />
      </div>
      <Container className="text-center">
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
          <motion.div variants={fadeUp}><Overline>Ready when you are</Overline></motion.div>
          <motion.h2
            variants={fadeUp}
            className="mt-4 font-display text-4xl md:text-6xl font-bold tracking-tighter text-white leading-tight max-w-3xl mx-auto"
          >
            Stop managing infrastructure. <span className="text-cyan-400">Start building.</span>
          </motion.h2>
          <motion.p variants={fadeUp} className="mt-5 text-zinc-400 max-w-xl mx-auto">
            14 days free. No credit card required. Deploy your first app in 41 seconds.
          </motion.p>
          <motion.div variants={fadeUp} className="mt-8 flex flex-wrap gap-3 justify-center">
            <PrimaryBtn to="/register" testId="cta-final-primary">Start deploying</PrimaryBtn>
            <OutlineBtn to="/pricing" testId="cta-final-secondary">See pricing</OutlineBtn>
          </motion.div>
        </motion.div>
      </Container>
    </Section>
  );
}

/* ───────────────────────── Footer ───────────────────────── */

function Footer() {
  return (
    <footer className="border-t border-zinc-900 bg-black py-12">
      <Container>
        <div className="grid md:grid-cols-[1.4fr_1fr_1fr_1fr] gap-8">
          <div>
            <Logo className="h-7 w-auto mb-4" />
            <p className="text-xs text-zinc-500 max-w-xs leading-relaxed">
              The EU-hosted, green-powered, agency-friendly PaaS. Build, ship, monitor and grow — all in one platform.
            </p>
            <div className="mt-5 flex gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.3em] border border-emerald-500/30 text-emerald-400">
                <Leaf className="h-3 w-3" /> green-powered
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-[0.3em] border border-cyan-500/30 text-cyan-400">
                <ShieldCheck className="h-3 w-3" /> GDPR
              </span>
            </div>
          </div>
          {[
            { h: "Product",   links: [["Features", "#features"], ["Compare", "#compare"], ["Pricing", "/pricing"], ["Roadmap", "/login"]] },
            { h: "Resources", links: [["Support", "/support"], ["Status", "/status"], ["Changelog", "#"], ["Sustainability", "#green"]] },
            { h: "Company",   links: [["About", "/about"], ["Contact", "/contact"], ["Privacy", "#"], ["Terms", "#"]] },
          ].map((c) => (
            <div key={c.h}>
              <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-zinc-500 mb-3">{c.h}</div>
              <ul className="space-y-2 text-sm text-zinc-400">
                {c.links.map(([label, href]) => (
                  <li key={label}>
                    {href.startsWith("/") ? (
                      <Link to={href} className="hover:text-cyan-400">{label}</Link>
                    ) : (
                      <a href={href} className="hover:text-cyan-400">{label}</a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-10 pt-6 border-t border-zinc-900 flex items-center justify-between flex-wrap gap-3 text-[11px] font-mono text-zinc-600">
          <span>© {new Date().getFullYear()} DeployUnit. Crafted in the EU.</span>
          <span className="inline-flex items-center gap-1.5">
            Powered by <a href="https://servunit.com" target="_blank" rel="noreferrer" className="text-zinc-400 hover:text-cyan-400 transition-colors">ServUnit Technologies BV</a>
          </span>
          <span>Operated under GDPR · Hosted in the EU.</span>
        </div>
      </Container>
    </footer>
  );
}

/* ───────────────────────── Page ───────────────────────── */

export default function Landing() {
  useSeo({
    title: "DeployUnit — The European Vercel alternative, built for agencies",
    description:
      "Deploy Next.js & Node apps in 41 seconds. No surprise bills. No DevOps. EU hosting, GDPR ready, agency-grade workspaces and billing. Predictable flat pricing.",
    path: "/",
  });
  return (
    <div className="bg-black text-white min-h-screen">
      <Nav />
      <Hero />
      <LogoStrip />
      <ReplacesStack />
      <HowItWorks />
      <ForAgencies />
      <Features />
      <Compare />
      <GreenEnergy />
      <Roadmap />
      <StatsTicker />
      <FinalCTA />
      <Footer />
    </div>
  );
}

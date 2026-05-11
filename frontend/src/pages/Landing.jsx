import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useInView, useReducedMotion } from "framer-motion";
import {
  ArrowRight, ArrowUpRight, Check, X as XIcon, Sparkles, Activity,
  Globe, Zap, GitBranch, Github, Terminal, Cpu, Gauge, Rocket, Lock,
  Leaf, Wind, Layers, BarChart3, Bell, Code2, FileText, Mail, Bot,
  Database, ShieldCheck, Server, MapPin, Workflow, ChevronRight, Eye,
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  CartesianGrid, XAxis, YAxis, Tooltip as RTooltip, Bar, BarChart,
} from "recharts";
import Logo from "../components/Logo";
import ConstellationCanvas from "../components/ConstellationCanvas";
import useTypewriter from "../hooks/useTypewriter";

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
  return (
    <header className="sticky top-0 z-50 backdrop-blur-xl bg-black/60 border-b border-zinc-800">
      <Container className="flex items-center justify-between h-16">
        <Link to="/" className="flex items-center gap-2.5" data-testid="nav-home">
          <Logo className="h-7 w-auto" />
        </Link>
        <nav className="hidden md:flex items-center gap-6 text-sm">
          <a href="#features" className="text-zinc-300 hover:text-white" data-testid="nav-features">Features</a>
          <a href="#compare" className="text-zinc-300 hover:text-white" data-testid="nav-compare">Compare</a>
          <a href="#green" className="text-zinc-300 hover:text-white" data-testid="nav-green">Green</a>
          <Link to="/pricing" className="text-zinc-300 hover:text-white" data-testid="nav-pricing">Pricing</Link>
          <Link to="/login" className="text-zinc-300 hover:text-white" data-testid="nav-login">Log in</Link>
        </nav>
        <PrimaryBtn to="/register" testId="nav-cta" className="text-sm px-4 py-2">Deploy now</PrimaryBtn>
      </Container>
    </header>
  );
}

/* ───────────────────────── Hero ───────────────────────── */

function HeroTerminal() {
  const lines = useMemo(() => [
    { t: "$ deployhub deploy --repo servunit/web", c: "text-zinc-300" },
    { t: "→ Connected: GitHub (oauth · push verified)", c: "text-zinc-500" },
    { t: "→ Detected: Next.js 14 · App Router", c: "text-zinc-500" },
    { t: "→ Buildpack: nixpacks · region eu-west", c: "text-zinc-500" },
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
        <span className="ml-3 text-[10px] uppercase tracking-[0.3em] text-zinc-500">~/deployhub</span>
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
        <ConstellationCanvas density={60} />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black/80" />
      </div>
      <Container className="grid lg:grid-cols-[1.05fr_1fr] gap-12 items-center">
        <motion.div initial="hidden" animate="show" variants={stagger}>
          <motion.div variants={fadeUp} className="mb-5"><Overline>The European agency PaaS</Overline></motion.div>
          <motion.h1
            variants={fadeUp}
            className="font-display text-5xl md:text-6xl lg:text-7xl font-bold tracking-tighter leading-[0.95] text-white"
          >
            Deploy anything.<br />
            <span className="text-cyan-400">Faster.</span>
          </motion.h1>
          <motion.p variants={fadeUp} className="mt-6 text-base sm:text-lg text-zinc-400 max-w-xl leading-relaxed">
            The all-in-one PaaS built for agencies and modern teams.
            Push to Git → live URL, container metrics, analytics and
            uptime alerts. Zero config, full white-label, EU-hosted.
          </motion.p>
          <motion.div variants={fadeUp} className="mt-8 flex flex-wrap gap-3">
            <PrimaryBtn to="/register" testId="hero-cta-primary">Start deploying</PrimaryBtn>
            <OutlineBtn to="/pricing" testId="hero-cta-secondary">See pricing</OutlineBtn>
          </motion.div>
          <motion.div variants={fadeUp} className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-[11px] font-mono uppercase tracking-[0.3em] text-zinc-500">
            <span className="inline-flex items-center gap-1.5"><MapPin className="h-3 w-3" /> EU-hosted</span>
            <span className="inline-flex items-center gap-1.5"><Leaf className="h-3 w-3 text-emerald-400" /> green energy</span>
            <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3 w-3" /> GDPR ready</span>
            <span className="inline-flex items-center gap-1.5"><Eye className="h-3 w-3" /> 100% white-label</span>
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
    <div className="border border-zinc-800 bg-zinc-950/50" data-testid="workspace-switcher">
      <div className="px-3 py-2 border-b border-zinc-800 text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500 flex items-center justify-between">
        <span>workspaces</span>
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
              data-testid={`workspace-${i}`}
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

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 auto-rows-[minmax(280px,auto)]">
          <BentoCard
            span="lg:col-span-2"
            overline="Live container metrics"
            title="Watch CPU, RAM, network and disk in real time."
            body="A first-party agent on your VPS pushes Docker stats every tick. Drawn as silky 60fps charts in your dashboard — auto-mapped to apps."
            testId="feature-metrics"
          >
            <MetricsGraphMock />
          </BentoCard>

          <BentoCard
            overline="Google PageSpeed"
            title="Lighthouse audits on autopilot."
            body="Daily mobile + desktop scores. Core Web Vitals trend. Manual re-runs in one click."
            testId="feature-pagespeed"
          >
            <PageSpeedGauge />
          </BentoCard>

          <BentoCard
            overline="Cookieless analytics"
            title="Privacy-first pageview tracker."
            body="1 KB script, sendBeacon, anonymized visitor hash that rotates daily. No banners. No cookies. GDPR by default."
            testId="feature-analytics"
          >
            <VisitorMapMock />
          </BentoCard>

          <BentoCard
            overline="Alerts everywhere"
            title="Uptime + deploys → Slack · Discord · SMS · WhatsApp."
            body="Wire every signal to the channel you actually watch. Credit-billed only when SMS or WhatsApp fire."
            testId="feature-alerts"
          >
            <AlertsMock />
          </BentoCard>

          <BentoCard
            overline="Agency multi-tenant"
            title="Workspaces per customer, in seconds."
            body="Switch between your customers' fleets without losing context. Per-workspace billing, members, and audit logs."
            testId="feature-workspaces"
          >
            <WorkspaceSwitcherMock />
          </BentoCard>

          {/* Six capability cards, each with its own micro-illustration */}
          {SMALL_FEATURES.map((c) => (
            <motion.div
              key={c.id}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4 }}
              className="border border-zinc-800 bg-zinc-950/30 p-5 hover:border-cyan-500/40 transition-colors flex flex-col"
              data-testid={`feature-small-${c.id}`}
            >
              <div className="flex items-center gap-2 mb-2">
                <c.icon className="h-4 w-4 text-cyan-400" />
                <div className="font-display text-base font-semibold text-white">{c.title}</div>
              </div>
              <div className="text-xs text-zinc-400 leading-relaxed mb-3">{c.body}</div>
              <div className="mt-auto">{c.illu}</div>
            </motion.div>
          ))}
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
  const rows = [
    { f: "EU data residency",         dh: true, vc: false, rd: "partial", coolify: "self-host" },
    { f: "Included container metrics", dh: true, vc: false, rd: "partial", coolify: false },
    { f: "Built-in web analytics",     dh: true, vc: false, rd: false,     coolify: false },
    { f: "100% white-label",           dh: true, vc: false, rd: false,     coolify: "DIY" },
    { f: "Agency multi-tenant",        dh: true, vc: false, rd: false,     coolify: false },
    { f: "Green energy by default",    dh: true, vc: false, rd: false,     coolify: "self-host" },
    { f: "Credit-based pricing",       dh: true, vc: false, rd: false,     coolify: false },
    { f: "Push-to-deploy from GitHub", dh: true, vc: true,  rd: true,      coolify: "DIY" },
    { f: "PR previews",                dh: true, vc: true,  rd: true,      coolify: false },
    { f: "Managed support",            dh: true, vc: true,  rd: true,      coolify: false },
  ];

  function Cell({ v }) {
    if (v === true) return <Check className="h-4 w-4 text-cyan-400 mx-auto" />;
    if (v === false) return <XIcon className="h-4 w-4 text-zinc-700 mx-auto" />;
    return <span className="block text-center text-[10px] font-mono uppercase tracking-[0.25em] text-zinc-500">{v}</span>;
  }

  return (
    <Section id="compare" className="py-24 lg:py-32">
      <Container>
        <div className="mb-12 max-w-2xl">
          <Overline>Compare</Overline>
          <h2 className="mt-3 font-display text-3xl md:text-5xl font-bold tracking-tighter text-white">
            Why teams switch to DeployHub.
          </h2>
          <p className="mt-3 text-zinc-400">
            Apples-to-apples against the platforms you already know.
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="border border-zinc-800 overflow-x-auto"
          data-testid="compare-table"
        >
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-zinc-800 text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">
                <th className="text-left p-4 font-normal">Capability</th>
                <th className="p-4 font-normal bg-cyan-950/30 border-x border-cyan-500/30 text-cyan-300">DeployHub</th>
                <th className="p-4 font-normal">Vercel</th>
                <th className="p-4 font-normal">Render</th>
                <th className="p-4 font-normal">Coolify (DIY)</th>
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
                  className="border-b border-zinc-900 last:border-b-0 hover:bg-zinc-950/50"
                >
                  <td className="p-4 text-zinc-300">{r.f}</td>
                  <td className="p-4 bg-cyan-950/20 border-x border-cyan-500/20"><Cell v={r.dh} /></td>
                  <td className="p-4"><Cell v={r.vc} /></td>
                  <td className="p-4"><Cell v={r.rd} /></td>
                  <td className="p-4"><Cell v={r.coolify} /></td>
                </motion.tr>
              ))}
            </tbody>
          </table>
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
            initial={{ opacity: 0, scale: 0.85, rotate: -8 }}
            whileInView={{ opacity: 1, scale: 1, rotate: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="relative flex items-center justify-center"
          >
            <div className="relative h-72 w-72 border border-emerald-500/30 bg-black/60 backdrop-blur-sm flex items-center justify-center">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
                className="absolute inset-0 flex items-center justify-center"
              >
                <Wind className="h-32 w-32 text-emerald-400/40" strokeWidth={1} />
              </motion.div>
              <div className="relative text-center">
                <Leaf className="h-10 w-10 text-emerald-400 mx-auto" />
                <div className="mt-4 font-display text-3xl font-bold text-emerald-400">Carbon</div>
                <div className="mt-1 font-display text-3xl font-bold text-white">Conscious</div>
                <div className="mt-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-400">by default</div>
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
                <div className="text-[10px] uppercase tracking-[0.35em] font-mono text-emerald-400">Partner · Team Trees</div>
                <div className="font-display text-lg font-bold text-white leading-tight">1 deploy = 1 tree.</div>
              </div>
            </div>

            <p className="text-sm sm:text-base text-zinc-300 max-w-xl">
              Every single app you deploy through DeployHub plants <span className="text-emerald-400 font-semibold">one extra tree</span> through our partnership with{" "}
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
    { icon: Activity, title: "Native heatmaps & session replays", cat: "Analytics" },
    { icon: GitBranch, title: "Database branching",               cat: "DX" },
    { icon: Bot,      title: "AI Code Co-pilot",                  cat: "DX" },
    { icon: Sparkles, title: "Visual deploy diffs",               cat: "DX" },
    { icon: FileText, title: "White-label client reports",        cat: "Business" },
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
    "EU eu-west · eu-central · eu-north",
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
            14 days free. No credit card. Deploy your first app in 41 seconds.
          </motion.p>
          <motion.div variants={fadeUp} className="mt-8 flex flex-wrap gap-3 justify-center">
            <PrimaryBtn to="/register" testId="cta-final-primary">Create free account</PrimaryBtn>
            <OutlineBtn to="/pricing" testId="cta-final-secondary">View pricing</OutlineBtn>
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
            { h: "Product", links: [["Features", "#features"], ["Compare", "#compare"], ["Pricing", "/pricing"], ["Roadmap", "/login"]] },
            { h: "Resources", links: [["Docs", "#"], ["Status", "#"], ["Blog", "#"], ["Changelog", "#"]] },
            { h: "Company", links: [["About", "#"], ["Sustainability", "#green"], ["Privacy", "#"], ["Contact", "mailto:hello@deployhub.app"]] },
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
          <span>© {new Date().getFullYear()} DeployHub. Crafted in the EU.</span>
          <span>Operated under GDPR · Hosted in the EU.</span>
        </div>
      </Container>
    </footer>
  );
}

/* ───────────────────────── Page ───────────────────────── */

export default function Landing() {
  return (
    <div className="bg-black text-white min-h-screen">
      <Nav />
      <Hero />
      <LogoStrip />
      <HowItWorks />
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

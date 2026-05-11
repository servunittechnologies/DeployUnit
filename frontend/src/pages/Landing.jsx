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
    { t: "✓ Deploy succeeded · 100% green energy", c: "text-emerald-400" },
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
            <span className="text-cyan-400">Faster.</span> <span className="text-emerald-400">Greener.</span>
          </motion.h1>
          <motion.p variants={fadeUp} className="mt-6 text-base sm:text-lg text-zinc-400 max-w-xl leading-relaxed">
            The all-in-one PaaS built for agencies and modern teams.
            Push to Git → live URL, container metrics, analytics and
            uptime alerts — on 100% renewable EU infrastructure.
            Zero config, full white-label.
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
  const data = useMemo(
    () => Array.from({ length: 30 }, (_, i) => ({
      t: i, cpu: 30 + Math.sin(i / 3) * 18 + (i % 5) * 2,
      mem: 55 + Math.cos(i / 4) * 12 + Math.sin(i / 6) * 6,
    })),
    [],
  );
  return (
    <div style={{ width: "100%", height: 160 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="#1f1f23" vertical={false} />
          <XAxis dataKey="t" hide />
          <YAxis stroke="#52525b" fontSize={10} tickLine={false} axisLine={false} domain={[0, 100]} />
          <RTooltip
            contentStyle={{ background: "#0a0a0a", border: "1px solid #27272a", fontSize: 11, fontFamily: "JetBrains Mono" }}
            cursor={{ stroke: "#3f3f46", strokeDasharray: "3 3" }}
          />
          <Line type="monotone" dataKey="cpu" name="CPU %" stroke={CYAN} dot={false} strokeWidth={2} animationDuration={1800} />
          <Line type="monotone" dataKey="mem" name="MEM %" stroke={GREEN} dot={false} strokeWidth={2} animationDuration={1800} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function PageSpeedGauge() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const [score, setScore] = useState(0);
  useEffect(() => {
    if (!inView) return;
    const target = 98;
    let f = 0;
    const id = setInterval(() => { f += 2; setScore(Math.min(target, f)); if (f >= target) clearInterval(id); }, 22);
    return () => clearInterval(id);
  }, [inView]);
  const r = 56;
  const c = 2 * Math.PI * r;
  return (
    <div ref={ref} className="flex items-center gap-5">
      <svg width={130} height={130} viewBox="0 0 130 130">
        <circle cx={65} cy={65} r={r} stroke="#1f1f23" strokeWidth={8} fill="none" />
        <circle
          cx={65} cy={65} r={r}
          stroke={CYAN} strokeWidth={8} fill="none"
          strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}
          strokeLinecap="round" transform="rotate(-90 65 65)"
          style={{ transition: "stroke-dashoffset 1s ease-out" }}
        />
        <text x="65" y="72" textAnchor="middle" className="fill-cyan-400 font-mono" fontSize="28">{score}</text>
      </svg>
      <div className="text-xs font-mono text-zinc-400 space-y-1">
        <div className="flex justify-between gap-3"><span>LCP</span><span className="text-emerald-400">1.2s</span></div>
        <div className="flex justify-between gap-3"><span>FCP</span><span className="text-emerald-400">0.8s</span></div>
        <div className="flex justify-between gap-3"><span>CLS</span><span className="text-emerald-400">0.02</span></div>
        <div className="flex justify-between gap-3"><span>TBT</span><span className="text-cyan-400">120ms</span></div>
      </div>
    </div>
  );
}

function VisitorMapMock() {
  const dots = useMemo(() => [
    { x: 18, y: 35 }, { x: 22, y: 45 }, { x: 28, y: 38 }, { x: 25, y: 50 },
    { x: 40, y: 30 }, { x: 45, y: 42 }, { x: 50, y: 38 }, { x: 60, y: 50 },
    { x: 68, y: 45 }, { x: 78, y: 55 }, { x: 75, y: 38 }, { x: 32, y: 60 },
    { x: 55, y: 65 }, { x: 30, y: 28 }, { x: 65, y: 28 },
  ], []);
  return (
    <div className="relative h-[160px] border border-zinc-800 bg-zinc-950/60 overflow-hidden">
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{ backgroundImage: "radial-gradient(circle at 1px 1px, #fff 1px, transparent 0)", backgroundSize: "16px 16px" }}
      />
      {dots.map((d, i) => (
        <motion.span
          key={i}
          initial={{ opacity: 0, scale: 0 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.06, duration: 0.35 }}
          className="absolute h-1.5 w-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_2px_rgba(6,182,212,0.6)]"
          style={{ left: `${d.x}%`, top: `${d.y}%` }}
        />
      ))}
      <div className="absolute bottom-3 left-3 text-[10px] font-mono text-zinc-400">
        <span className="text-cyan-400">847</span> visitors · <span className="text-emerald-400">14 countries</span>
      </div>
    </div>
  );
}

function AlertsMock() {
  const items = [
    { ch: "slack", msg: "✓ /api/login healthy · 99.99% 24h", t: "12:04", k: "ok" },
    { ch: "discord", msg: "↗ CPU 78% on web-01 · scaled", t: "12:08", k: "warn" },
    { ch: "sms", msg: "→ Deploy succeeded · v1.4.2", t: "12:11", k: "ok" },
  ];
  return (
    <div className="space-y-2">
      {items.map((it, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -10 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.15 * i }}
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

function WorkspaceSwitcherMock() {
  const ws = ["Beyond Meassure", "ServUnit", "Stella Labs", "OakRoot"];
  return (
    <div className="border border-zinc-800 bg-zinc-950/50">
      <div className="px-3 py-2 border-b border-zinc-800 text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">workspaces</div>
      <div className="divide-y divide-zinc-900">
        {ws.map((w, i) => (
          <motion.div
            key={w}
            initial={{ opacity: 0, x: -8 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center justify-between px-3 py-2 text-xs font-mono"
          >
            <span className="flex items-center gap-2">
              <span className={`h-1.5 w-1.5 rounded-full ${i === 0 ? "bg-cyan-400" : "bg-zinc-700"}`} />
              <span className={i === 0 ? "text-cyan-300" : "text-zinc-400"}>{w}</span>
            </span>
            <span className="text-zinc-600">{4 + i * 2} apps</span>
          </motion.div>
        ))}
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
      whileHover={{ borderColor: "rgba(6,182,212,0.5)" }}
      className={`relative border border-zinc-800 bg-zinc-950/40 p-6 lg:p-8 overflow-hidden flex flex-col ${span}`}
      data-testid={testId}
    >
      <div className="absolute -top-20 -right-20 w-60 h-60 rounded-full bg-cyan-500/[0.04] blur-3xl pointer-events-none" />
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

          {/* Three small icon-led capability tiles */}
          {[
            { icon: GitBranch, title: "PR previews", body: "Every pull request gets its own URL + container, killed on merge." },
            { icon: Database, title: "Managed databases", body: "Postgres · MySQL · Redis attached to apps with zero-touch creds." },
            { icon: Globe, title: "Custom domains + DNS", body: "Cloudflare DNS provisioned automatically. Auto-SSL via Let's Encrypt." },
            { icon: Lock, title: "Audit log + RBAC", body: "Every action logged. Owner / Admin / Developer / Viewer roles." },
            { icon: Cpu, title: "Per-app resource limits", body: "Dial vCPU, RAM, and storage; pay only what you use via credits." },
            { icon: Bell, title: "Custom cron tasks", body: "Schedule background jobs without spinning up new infra." },
          ].map((c) => (
            <motion.div
              key={c.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4 }}
              className="border border-zinc-800 bg-zinc-950/30 p-5 hover:border-cyan-500/40 transition-colors"
            >
              <c.icon className="h-5 w-5 text-cyan-400 mb-3" />
              <div className="font-display text-base font-semibold text-white">{c.title}</div>
              <div className="mt-1.5 text-xs text-zinc-400 leading-relaxed">{c.body}</div>
            </motion.div>
          ))}
        </div>
      </Container>
    </Section>
  );
}

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

      <Container className="grid lg:grid-cols-[1.1fr_1fr] gap-12 items-center">
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true }} variants={stagger}>
          <motion.div variants={fadeUp}><Overline color="text-emerald-400">Sustainability · USP</Overline></motion.div>
          <motion.h2
            variants={fadeUp}
            className="mt-4 font-display text-4xl md:text-6xl font-bold tracking-tighter text-white leading-none"
          >
            100% wind & solar<br />
            <span className="text-emerald-400">powered.</span>
          </motion.h2>
          <motion.p variants={fadeUp} className="mt-5 text-base sm:text-lg text-zinc-300 max-w-xl">
            Every deploy on DeployHub runs in EU datacenters powered by renewable energy. No carbon offsets,
            no greenwashing — your apps tick along on real wind and solar, with verifiable energy contracts.
          </motion.p>
          <motion.div variants={fadeUp} className="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { k: "100%", v: "renewable" },
              { k: "0g", v: "CO₂ per deploy" },
              { k: "EU", v: "datacenters only" },
              { k: "ISO", v: "14001 partners" },
            ].map((s) => (
              <div key={s.v} className="border border-emerald-500/30 bg-black/40 p-4 text-center">
                <div className="font-display text-2xl text-emerald-400 font-bold">{s.k}</div>
                <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-400 mt-1">{s.v}</div>
              </div>
            ))}
          </motion.div>
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
              <div className="mt-1 font-display text-3xl font-bold text-white">Neutral</div>
              <div className="mt-2 text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-400">by default</div>
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
    "0g CO₂ per build",
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
                <Leaf className="h-3 w-3" /> 100% green
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
          <span>Built on wind & solar · Operated under GDPR · Hosted in eu-west, eu-central, eu-north.</span>
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

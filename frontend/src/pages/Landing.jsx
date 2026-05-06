import { Link } from "react-router-dom";
import { Github, ArrowRight, Sparkles, ShieldCheck, Activity, Globe, Zap, GitBranch, ChevronRight } from "lucide-react";
import Logo from "../components/Logo";

const heroImg =
  "https://static.prod-images.emergentagent.com/jobs/5fed0a66-6655-41bc-a461-78244f817ef5/images/51d46d5ed33552961486aeeafbca5ab7ae2225742c10449492914fbf4634b138.png";
const featureImg =
  "https://static.prod-images.emergentagent.com/jobs/5fed0a66-6655-41bc-a461-78244f817ef5/images/f6fe650f9de126469ea48b176c020827fff6e51aa7a515ea758c3ac4b57625b6.png";
const developerImg =
  "https://images.unsplash.com/photo-1625838144804-300f3907c110?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzB8MHwxfHNlYXJjaHwzfHxkZXZlbG9wZXIlMjBjb2RpbmclMjBkYXJrfGVufDB8fHx8MTc3ODA3MzgzM3ww&ixlib=rb-4.1.0&q=85";

const TECH = ["Next.js", "Node 20", "Bun", "PNPM", "TypeScript", "Tailwind", "Prisma", "Postgres", "Redis", "Edge", "Nginx", "Docker"];

function Feature({ icon: Icon, title, body }) {
  return (
    <div className="p-8 border-r border-b border-white/[0.07] hover:bg-white/[0.02] transition-colors">
      <div className="flex items-center gap-3 mb-4">
        <div className="h-9 w-9 border border-brand/40 text-brand flex items-center justify-center">
          <Icon className="h-4 w-4" />
        </div>
        <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-500">primitive</div>
      </div>
      <h3 className="font-display text-xl font-medium tracking-tight mb-2">{title}</h3>
      <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
    </div>
  );
}

export default function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* nav */}
      <header className="glass fixed top-0 inset-x-0 z-40">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <Logo />
          <nav className="hidden md:flex items-center gap-7 text-sm text-zinc-400">
            <a href="#features" className="hover:text-white">Features</a>
            <a href="#how" className="hover:text-white">How it works</a>
            <Link to="/pricing" className="hover:text-white" data-testid="nav-pricing">Pricing</Link>
            <a href="#agency" className="hover:text-white">Agencies</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" className="px-3 py-1.5 text-sm border border-white/15 hover:border-white/40 transition" data-testid="nav-signin">
              Sign in
            </Link>
            <Link to="/register" className="px-3 py-1.5 text-sm bg-brand text-brand-fg font-medium hover:bg-brand/90 transition shadow-[0_0_20px_rgba(0,229,255,0.25)]" data-testid="nav-signup">
              Start free
            </Link>
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="relative pt-40 pb-28 overflow-hidden">
        <div
          className="absolute inset-0 -z-10 opacity-50"
          style={{ backgroundImage: `url(${heroImg})`, backgroundSize: "cover", backgroundPosition: "center" }}
        />
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-background/30 via-background/85 to-background" />
        <div className="absolute inset-0 -z-10 bg-grid opacity-30" />

        <div className="max-w-[1400px] mx-auto px-6 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-7 animate-rise">
            <div className="inline-flex items-center gap-2 mb-6 px-3 py-1 border border-brand/30 bg-brand/5 text-brand text-xs font-mono uppercase tracking-[0.25em]">
              <Sparkles className="h-3 w-3" />
              v1.0 — public beta
            </div>
            <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-semibold tracking-tighter leading-[0.95]">
              Ship Next.js & Node<br />
              <span className="text-brand">in two clicks.</span>
            </h1>
            <p className="mt-6 max-w-xl text-zinc-400 text-base leading-relaxed">
              DeployHub is a production-grade hosting platform built on Coolify with hidden billing, monitoring,
              alerts, and an agency-ready workspace model — minus the Vercel bill.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to="/register" className="group inline-flex items-center gap-2 px-5 py-3 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition shadow-[0_0_24px_rgba(0,229,255,0.35)]" data-testid="hero-cta-start">
                Deploy your first app
                <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </Link>
              <Link to="/pricing" className="inline-flex items-center gap-2 px-5 py-3 border border-white/15 hover:border-white/40 transition text-sm" data-testid="hero-cta-pricing">
                See pricing <ChevronRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs font-mono text-zinc-500">
              <span className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-signal-live animate-ping-soft" /> 99.99% uptime SLA</span>
              <span>Auto-SSL via Coolify</span>
              <span>EU + US regions</span>
              <span>White-label for agencies</span>
            </div>
          </div>

          <div className="lg:col-span-5 lg:-ml-12 relative animate-rise" style={{ animationDelay: "120ms" }}>
            <div className="terminal max-w-[460px] ml-auto">
              <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5 bg-black/60">
                <span className="h-2 w-2 rounded-full bg-signal-failed/70" />
                <span className="h-2 w-2 rounded-full bg-signal-queued/70" />
                <span className="h-2 w-2 rounded-full bg-signal-live/70" />
                <span className="ml-2 text-[10px] uppercase tracking-[0.3em] text-zinc-500">~/novabrew $ deploy</span>
              </div>
              <div className="p-4 text-xs leading-6">
                <div><span className="text-zinc-500">$</span> deployhub deploy --repo novabrew/web</div>
                <div className="text-zinc-400">→ Detected: <span className="text-brand">Next.js 14</span></div>
                <div className="text-zinc-400">→ Build: <span className="text-brand">nixpacks</span></div>
                <div className="text-zinc-400">→ Domain: <span className="text-brand">novabrew.app</span></div>
                <div className="text-zinc-400">→ SSL: <span className="text-signal-live">issued</span></div>
                <div className="mt-2 text-signal-live">✓ Live in 47s</div>
                <div className="mt-3 inline-flex items-center gap-2 px-2 py-0.5 text-[10px] uppercase tracking-wider border border-signal-live/30 text-signal-live">
                  <span className="h-1.5 w-1.5 rounded-full bg-signal-live animate-ping-soft" /> running
                </div>
              </div>
            </div>
            <div className="mt-4 ml-auto max-w-[380px] border border-white/10 p-4 bg-elevated/40 backdrop-blur">
              <div className="flex items-center justify-between mb-2">
                <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono">monitoring</div>
                <div className="text-[10px] uppercase tracking-[0.3em] text-signal-live font-mono">99.99%</div>
              </div>
              <svg viewBox="0 0 200 50" className="w-full h-12 text-brand">
                <polyline fill="none" stroke="currentColor" strokeWidth="1.5"
                  points="0,40 20,38 40,42 60,30 80,32 100,18 120,20 140,12 160,16 180,8 200,10" />
                <polyline fill="rgba(0,229,255,0.12)" stroke="none"
                  points="0,40 20,38 40,42 60,30 80,32 100,18 120,20 140,12 160,16 180,8 200,10 200,50 0,50" />
              </svg>
            </div>
          </div>
        </div>
      </section>

      {/* tech marquee */}
      <section className="border-y border-white/[0.06] py-5 overflow-hidden">
        <div className="flex gap-10 whitespace-nowrap animate-[shimmer_24s_linear_infinite]">
          {[...TECH, ...TECH].map((t, i) => (
            <span key={i} className="font-mono text-xs uppercase tracking-[0.3em] text-zinc-500">{t}</span>
          ))}
        </div>
      </section>

      {/* features */}
      <section id="features" className="max-w-[1400px] mx-auto px-6 py-24">
        <div className="max-w-3xl mb-12">
          <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-3">// platform</div>
          <h2 className="font-display text-4xl lg:text-5xl tracking-tighter font-semibold">
            Everything you need to run Next.js & Node in production.
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 border-l border-t border-white/[0.07]">
          <Feature icon={Zap} title="2-click deploys" body="Connect GitHub, pick a repo, hit Deploy. Auto-detects Next.js & Node. Build, expose, SSL — done." />
          <Feature icon={Globe} title="Hands-free domains" body="Buy domains from inside the dashboard, link them to apps, get SSL via Coolify. No DNS PhDs required." />
          <Feature icon={Activity} title="Realtime monitoring" body="Uptime, response time, status codes. Alerts when an app goes down or starts to crawl." />
          <Feature icon={ShieldCheck} title="Hidden billing" body="WHMCS does the heavy lifting behind the scenes. Your users see clean invoices, not config screens." />
          <Feature icon={GitBranch} title="Agency-ready" body="Multiple workspaces, projects, roles. Bill per workspace, white-label for clients." />
          <Feature icon={Github} title="GitHub-native" body="Sync repos, deploy from any branch. Preview environments and rollbacks coming soon." />
        </div>
      </section>

      {/* how it works */}
      <section id="how" className="border-t border-white/[0.06] py-24">
        <div className="max-w-[1400px] mx-auto px-6 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-5">
            <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-3">// flow</div>
            <h2 className="font-display text-4xl lg:text-5xl tracking-tighter font-semibold">From repo to live in under a minute.</h2>
            <ol className="mt-8 space-y-5">
              {[
                ["Connect GitHub", "Authorize once. We'll list every repo you can deploy."],
                ["Pick a plan", "Hobby is free. Pro and Agency come with WHMCS-backed invoicing."],
                ["Hit deploy", "We provision a Coolify container, run your build, and assign a domain."],
                ["Monitor & scale", "Realtime checks. Alerts. Logs. Redeploy in one click."],
              ].map(([t, b], i) => (
                <li key={i} className="flex gap-4">
                  <div className="font-mono text-xs text-brand pt-1">0{i + 1}</div>
                  <div>
                    <div className="font-display text-lg">{t}</div>
                    <div className="text-sm text-zinc-400">{b}</div>
                  </div>
                </li>
              ))}
            </ol>
          </div>
          <div className="lg:col-span-7 relative">
            <img src={featureImg} alt="infrastructure" className="w-full border border-white/10 grayscale opacity-90" />
            <div className="absolute -bottom-6 -left-6 hidden lg:block terminal max-w-[280px]">
              <div className="px-3 py-2 border-b border-white/5 bg-black/60 text-[10px] uppercase tracking-[0.3em] text-zinc-500">deploy.log</div>
              <div className="p-3 text-[11px] leading-5 font-mono">
                <div className="text-brand">[BUILD] yarn install</div>
                <div className="text-brand">[BUILD] yarn build</div>
                <div className="text-brand">[NIXPACKS] container ready</div>
                <div className="text-signal-live">[STATUS] live</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* agency */}
      <section id="agency" className="border-t border-white/[0.06] py-24">
        <div className="max-w-[1400px] mx-auto px-6 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-6 order-2 lg:order-1">
            <img src={developerImg} alt="developer" className="w-full border border-white/10 saturate-50" />
          </div>
          <div className="lg:col-span-6 order-1 lg:order-2">
            <div className="text-xs font-mono uppercase tracking-[0.3em] text-brand mb-3">// for agencies</div>
            <h2 className="font-display text-4xl lg:text-5xl tracking-tighter font-semibold">
              One platform. Every client.
            </h2>
            <p className="mt-4 text-zinc-400 max-w-lg">
              Group apps by client project, invite team members with granular roles, and let billing flow through
              your white-labeled WHMCS install. Your clients never see the seams.
            </p>
            <div className="mt-8 grid grid-cols-2 gap-px bg-white/[0.06]">
              {[
                ["Workspaces", "Solo or Agency"],
                ["Roles", "Owner / Admin / Dev / Billing / Viewer"],
                ["Projects", "Group apps per client"],
                ["Branding", "White-label invoices"],
              ].map(([t, b]) => (
                <div key={t} className="bg-background p-4">
                  <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 font-mono">{t}</div>
                  <div className="text-sm mt-1">{b}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* footer cta */}
      <section className="border-t border-white/[0.06] py-24 bg-grid-fine">
        <div className="max-w-[1400px] mx-auto px-6 text-center">
          <h2 className="font-display text-4xl lg:text-6xl tracking-tighter font-semibold">
            The boring part of hosting,<br /> made <span className="text-brand">brilliantly fast.</span>
          </h2>
          <div className="mt-8 flex justify-center gap-3">
            <Link to="/register" className="inline-flex items-center gap-2 px-6 py-3 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition shadow-[0_0_24px_rgba(0,229,255,0.35)]">
              Start free <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/pricing" className="inline-flex items-center gap-2 px-6 py-3 border border-white/15 hover:border-white/40">
              Compare plans
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/[0.06] py-8">
        <div className="max-w-[1400px] mx-auto px-6 flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-zinc-500">
          <Logo small />
          <div>© {new Date().getFullYear()} DeployHub. Built on Coolify · Powered by WHMCS.</div>
        </div>
      </footer>
    </div>
  );
}

import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowRight, Leaf, ShieldCheck, Menu, X } from "lucide-react";
import Logo from "./Logo";

const NAV_LINKS = [
  { to: "/#features", label: "Features", testId: "marketing-nav-features" },
  { to: "/#compare",  label: "Compare",  testId: "marketing-nav-compare" },
  { to: "/about",     label: "About",    testId: "marketing-nav-about" },
  { to: "/pricing",   label: "Pricing",  testId: "marketing-nav-pricing" },
  { to: "/support",   label: "Support",  testId: "marketing-nav-support" },
  { to: "/contact",   label: "Contact",  testId: "marketing-nav-contact" },
];

const FOOTER_COLS = [
  { h: "Product",   links: [["Features", "/#features"], ["Compare", "/#compare"], ["Pricing", "/pricing"], ["Roadmap", "/login"]] },
  { h: "Resources", links: [["Support", "/support"], ["Status", "/status"], ["Docs", "/support"], ["Changelog", "#"]] },
  { h: "Company",   links: [["About", "/about"], ["Sustainability", "/about#sustainability"], ["Contact", "/contact"], ["Privacy", "#"]] },
];

export function MarketingNav() {
  const { hash, pathname } = useLocation();
  const [open, setOpen] = useState(false);
  // Lock body scroll while drawer is open
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);
  // Close drawer on route change
  useEffect(() => { setOpen(false); }, [pathname, hash]);

  return (
    <header className="sticky top-0 z-50 backdrop-blur-xl bg-black/60 border-b border-zinc-800">
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
        <Link to="/" className="flex items-center gap-2.5" data-testid="marketing-nav-home">
          <Logo className="h-7 w-auto" />
        </Link>
        <nav className="hidden md:flex items-center gap-6 text-sm">
          {NAV_LINKS.map((n) => {
            const isAnchor = n.to.startsWith("/#");
            const props = isAnchor ? { href: n.to } : { to: n.to };
            const Comp = isAnchor ? "a" : Link;
            const active = !isAnchor && window.location.pathname === n.to;
            return (
              <Comp
                key={n.to}
                {...props}
                data-testid={n.testId}
                className={`transition-colors hover:text-white ${active ? "text-cyan-400" : "text-zinc-300"}`}
              >
                {n.label}
              </Comp>
            );
          })}
          <Link to="/login" className="text-zinc-300 hover:text-white" data-testid="marketing-nav-login">Log in</Link>
        </nav>
        <div className="flex items-center gap-2">
          <Link
            to="/register"
            className="hidden sm:inline-flex group items-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-4 py-2 text-sm transition-colors"
            data-testid="marketing-nav-cta"
          >
            Deploy now
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <button
            onClick={() => setOpen(true)}
            className="md:hidden p-2 -mr-2 text-zinc-300 hover:text-white"
            aria-label="Open menu"
            data-testid="marketing-nav-mobile-toggle"
          >
            <Menu className="h-6 w-6" />
          </button>
        </div>
      </div>

      {/* Mobile drawer — always rendered for smooth open/close animation */}
      <div
        className={`md:hidden fixed inset-0 z-[60] flex flex-col h-screen bg-black/95 backdrop-blur-xl transition-all duration-200 ease-out ${
          open
            ? "opacity-100 translate-y-0 pointer-events-auto"
            : "opacity-0 -translate-y-1 pointer-events-none"
        }`}
        aria-hidden={!open}
        data-testid="marketing-nav-mobile-drawer"
      >
        <div className="flex items-center justify-between h-16 px-4 border-b border-zinc-800 shrink-0">
          <Link to="/" onClick={() => setOpen(false)}><Logo className="h-7 w-auto" /></Link>
          <button
            onClick={() => setOpen(false)}
            className="p-2 -mr-2 text-zinc-300 hover:text-white transition-colors"
            aria-label="Close menu"
            data-testid="marketing-nav-mobile-close"
          >
            <X className="h-6 w-6" />
          </button>
        </div>
        <nav className="flex-1 flex flex-col px-6 py-4 overflow-y-auto">
          {NAV_LINKS.map((n) => {
            const isAnchor = n.to.startsWith("/#");
            const props = isAnchor ? { href: n.to } : { to: n.to };
            const Comp = isAnchor ? "a" : Link;
            return (
              <Comp
                key={n.to}
                {...props}
                onClick={() => setOpen(false)}
                data-testid={`${n.testId}-mobile`}
                className="py-2.5 text-base font-display font-medium text-zinc-200 hover:text-cyan-400 transition-colors border-b border-zinc-900"
              >
                {n.label}
              </Comp>
            );
          })}
          {/* Account actions — visually separated from content nav */}
          <div className="mt-6 pt-5 border-t border-zinc-800 flex flex-col gap-3">
            <Link
              to="/login"
              onClick={() => setOpen(false)}
              data-testid="marketing-nav-login-mobile"
              className="inline-flex items-center justify-center gap-2 border border-zinc-700 hover:border-cyan-500 hover:text-cyan-400 text-zinc-200 font-medium px-5 py-2.5 text-sm transition-colors"
            >
              Log in
            </Link>
            <Link
              to="/register"
              onClick={() => setOpen(false)}
              data-testid="marketing-nav-cta-mobile"
              className="inline-flex items-center justify-center gap-2 bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-5 py-2.5 text-sm transition-colors"
            >
              Deploy now
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </nav>
        <div className="px-6 py-3 border-t border-zinc-900 text-[10px] font-mono text-zinc-500 shrink-0">
          © {new Date().getFullYear()} DeployUnit · EU · GDPR
        </div>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="border-t border-zinc-900 bg-black py-12">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
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
          {FOOTER_COLS.map((c) => (
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
      </div>
    </footer>
  );
}

export default function MarketingLayout({ children }) {
  return (
    <div className="bg-black text-white min-h-screen flex flex-col">
      <MarketingNav />
      <main className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  );
}

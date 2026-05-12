import { useEffect, useState, useRef, useCallback } from "react";
import { api } from "../lib/api";
import { ExternalLink, RefreshCw, Globe, ShieldX, Loader2, Zap, Monitor, Tablet, Smartphone } from "lucide-react";

function fmtMs(ms) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function timeAgo(iso) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

function statusColor(code, ok) {
  if (code == null) return "text-zinc-500";
  if (code >= 200 && code < 300) return "text-signal-live";
  if (code >= 300 && code < 400) return "text-brand";
  if (code >= 400 && code < 500) return "text-signal-queued";
  return "text-signal-failed";
}

// Viewport presets — the iframe is rendered at this nominal size and then
// scaled with CSS transform so the user sees how the site responds at each
// breakpoint without leaving the dashboard.
const VIEWPORTS = {
  desktop: { w: 1440, h: 900, icon: Monitor, label: "Desktop" },
  tablet:  { w: 768, h: 1024, icon: Tablet, label: "Tablet" },
  mobile:  { w: 390, h: 844, icon: Smartphone, label: "Mobile" },
};

export default function SitePreview({ appId, monitoring }) {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [iframeFailed, setIframeFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [viewport, setViewport] = useState("desktop");
  const iframeRef = useRef(null);
  const stageRef = useRef(null);
  const [stageWidth, setStageWidth] = useState(0);

  // Measure the available width of the iframe stage so we can scale a
  // 1440px-wide iframe to fit. ResizeObserver keeps this current on layout
  // changes (sidebar collapses, window resize, etc).
  useEffect(() => {
    if (!stageRef.current) return;
    const ro = new ResizeObserver(entries => {
      for (const e of entries) setStageWidth(e.contentRect.width);
    });
    ro.observe(stageRef.current);
    setStageWidth(stageRef.current.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);

  const probe = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/apps/${appId}/health`);
      setHealth(data);
      setIframeFailed(false);
    } finally { setLoading(false); }
  }, [appId]);

  useEffect(() => { probe(); }, [probe]);

  // Auto-refresh health every 30s
  useEffect(() => {
    const t = setInterval(probe, 30000);
    return () => clearInterval(t);
  }, [probe]);

  const reload = () => {
    setReloadKey((k) => k + 1);
    probe();
  };

  const url = health?.url;
  const isInsecureOrigin = !!(url && /^http:\/\//i.test(url));
  const canIframe = url && health?.available && !health?.framing_blocked && !isInsecureOrigin;
  const showFallback = !canIframe || iframeFailed;
  const vp = VIEWPORTS[viewport] || VIEWPORTS.desktop;
  // Scale the viewport-sized iframe to fit horizontally, capped at 1 so
  // tablet/mobile don't blow up larger than their real size.
  const scale = stageWidth > 0 ? Math.min(1, stageWidth / vp.w) : 1;
  const scaledH = vp.h * scale;

  return (
    <div className="border border-white/[0.06] bg-elevated/30 overflow-hidden" data-testid="site-preview">
      {/* browser-style header */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-white/[0.06] bg-black/40">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-signal-failed/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-signal-queued/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-signal-live/60" />
        </div>
        <div className="flex-1 px-3 py-1 bg-black/60 border border-white/10 text-[11px] font-mono text-zinc-400 truncate">
          {url ? url.replace(/^https?:\/\//, "") : "no domain assigned"}
        </div>
        {/* Viewport toggle — desktop / tablet / mobile */}
        <div className="hidden sm:flex items-center gap-px bg-black/60 border border-white/10" data-testid="preview-viewport-toggle">
          {Object.entries(VIEWPORTS).map(([k, v]) => {
            const Icon = v.icon;
            const active = viewport === k;
            return (
              <button
                key={k}
                onClick={() => setViewport(k)}
                className={`px-2 py-1.5 transition-colors ${active ? "bg-brand/20 text-brand" : "text-zinc-500 hover:text-zinc-200 hover:bg-white/5"}`}
                title={`${v.label} (${v.w}×${v.h})`}
                data-testid={`preview-viewport-${k}`}
              >
                <Icon className="h-3.5 w-3.5" />
              </button>
            );
          })}
        </div>
        <button
          onClick={reload}
          className="p-1.5 hover:bg-white/5 text-zinc-400 hover:text-brand"
          title="Reload"
          data-testid="preview-reload"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
        </button>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="p-1.5 hover:bg-white/5 text-zinc-400 hover:text-brand"
            title="Open in new tab"
            data-testid="preview-open"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>

      {/* preview surface */}
      <div
        ref={stageRef}
        className="relative bg-black/40 overflow-auto flex items-start justify-center"
        style={{ height: showFallback || !url ? Math.round(vp.w * 0.5625) : Math.max(scaledH, 320) }}
      >
        {!url ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-zinc-500 font-mono text-sm">
            <Globe className="h-8 w-8 mb-3" />
            No domain assigned yet · deploy to see your site here
          </div>
        ) : showFallback ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-zinc-400 px-6 text-center" data-testid="preview-fallback">
            <ShieldX className="h-8 w-8 text-signal-queued mb-3" />
            <div className="font-mono text-sm">
              {isInsecureOrigin ? "Preview blocked by browser security" : "Preview blocked by site headers"}
            </div>
            <div className="text-xs text-zinc-500 mt-1 font-mono max-w-md">
              {isInsecureOrigin
                ? "Your site is served over http:// but this dashboard is https://. Browsers block mixed-content iframes. Enable SSL for this app to embed it here."
                : health?.framing_blocked
                  ? "X-Frame-Options / CSP frame-ancestors prevents embedding."
                  : "Site is unreachable or blocked iframing."}
            </div>
            <a href={url} target="_blank" rel="noreferrer" className="mt-4 inline-flex items-center gap-1 px-3 py-1.5 border border-brand/40 text-brand text-xs font-mono uppercase tracking-wider hover:bg-brand/10" data-testid="preview-fallback-open">
              Open full site <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        ) : (
          <div
            style={{
              width: vp.w,
              height: vp.h,
              transform: `scale(${scale})`,
              transformOrigin: "top center",
              flexShrink: 0,
            }}
          >
            <iframe
              key={reloadKey}
              ref={iframeRef}
              src={url}
              title="Live site preview"
              sandbox="allow-scripts allow-same-origin allow-forms"
              referrerPolicy="no-referrer"
              className="border-0 bg-white"
              style={{ width: vp.w, height: vp.h }}
              data-testid="preview-iframe"
              onError={() => setIframeFailed(true)}
            />
          </div>
        )}
      </div>

      {/* stats footer */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-white/[0.06] border-t border-white/[0.06]">
        <div className="bg-background p-3">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Status</div>
          <div className={`mt-1 font-display text-lg ${statusColor(health?.status_code, health?.ok)}`} data-testid="preview-status-code">
            {health?.status_code ?? (loading ? "…" : "ERR")}
          </div>
        </div>
        <div className="bg-background p-3">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500 inline-flex items-center gap-1">
            <Zap className="h-3 w-3" /> Response
          </div>
          <div className="mt-1 font-display text-lg" data-testid="preview-response-time">
            {fmtMs(health?.response_time_ms)}
          </div>
        </div>
        <div className="bg-background p-3">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Uptime 24h</div>
          <div className="mt-1 font-display text-lg text-signal-live">
            {monitoring?.uptime_pct != null ? `${monitoring.uptime_pct}%` : "—"}
          </div>
        </div>
        <div className="bg-background p-3">
          <div className="text-[10px] uppercase tracking-[0.3em] font-mono text-zinc-500">Avg 24h</div>
          <div className="mt-1 font-display text-lg">
            {monitoring?.avg_response_ms != null ? fmtMs(monitoring.avg_response_ms) : "—"}
          </div>
        </div>
      </div>
      {health?.title && (
        <div className="px-4 py-2 text-xs font-mono text-zinc-500 border-t border-white/[0.06] truncate">
          <span className="text-zinc-600">title:</span> {health.title}
          <span className="ml-3 text-zinc-600">checked {timeAgo(health.checked_at)}</span>
        </div>
      )}
    </div>
  );
}

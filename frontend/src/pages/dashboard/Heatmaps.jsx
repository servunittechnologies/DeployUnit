/**
 * In-house heatmap viewer.
 *
 * Two panes:
 *   left  — list of URLs we have data on, sorted by total events
 *   right — a canvas that paints a heatmap of click x/y for the selected URL.
 *
 * Rendering uses a simple density additive blend so we don't need any heatmap
 * library (heatmap.js, simpleheat etc.) — keeps the JS bundle small and
 * everything self-hosted.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Loader2, ArrowLeft, MousePointerClick, Eye, ScrollText, Flame } from "lucide-react";
import { api } from "../../lib/api";

const TYPE_LABELS = {
  click: { label: "Clicks", icon: MousePointerClick, color: "#06B6D4" },
  rage:  { label: "Rage clicks", icon: Flame, color: "#EF4444" },
  view:  { label: "Views", icon: Eye, color: "#10B981" },
  scroll:{ label: "Scrolls", icon: ScrollText, color: "#A855F7" },
};

export default function Heatmaps() {
  const { id } = useParams();
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isActive, setIsActive] = useState(false);
  const [days, setDays] = useState(30);
  const [selectedUrl, setSelectedUrl] = useState(null);
  const [type, setType] = useState("click");
  const [events, setEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get(`/apps/${id}/heatmaps/pages`, { params: { days } })
      .then(r => {
        setPages(r.data.pages || []);
        setIsActive(!!r.data.is_active);
        if (r.data.pages?.[0]) setSelectedUrl(r.data.pages[0].url);
      })
      .finally(() => setLoading(false));
  }, [id, days]);

  useEffect(() => {
    if (!selectedUrl) return;
    setEventsLoading(true);
    api.get(`/apps/${id}/heatmaps/page`, { params: { url: selectedUrl, type, days, limit: 5000 } })
      .then(r => setEvents(r.data.events || []))
      .finally(() => setEventsLoading(false));
  }, [id, selectedUrl, type, days]);

  const summary = useMemo(() => {
    return pages.find(p => p.url === selectedUrl);
  }, [pages, selectedUrl]);

  return (
    <div className="p-6" data-testid="heatmaps-page">
        <Link to={`/app/apps/${id}`} className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-brand mb-4" data-testid="heatmaps-back">
          <ArrowLeft className="h-3.5 w-3.5" /> back to app
        </Link>

        <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.35em] text-brand">In-house heatmaps</div>
            <h1 className="mt-1 font-display text-3xl tracking-tighter text-white">Where visitors actually click.</h1>
            <p className="mt-1 text-sm text-zinc-400">No third-party scripts. Anonymous by default.</p>
          </div>
          <div className="flex items-center gap-2 text-[11px] font-mono">
            {[7, 14, 30, 90].map(d => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-2.5 py-1.5 border ${days === d ? "border-brand text-brand bg-brand/[0.06]" : "border-white/10 text-zinc-400 hover:text-zinc-100"}`}
                data-testid={`heatmaps-range-${d}`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-zinc-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
        ) : !isActive ? (
          <div className="border border-amber-500/30 bg-amber-950/20 p-6 text-sm text-amber-200" data-testid="heatmaps-inactive">
            Heatmaps are not active on this app. Go to <Link to={`/app/apps/${id}`} className="text-brand underline">App → Add-ons</Link> to enable for 100 credits / month.
          </div>
        ) : pages.length === 0 ? (
          <div className="border border-white/[0.06] p-6 text-sm text-zinc-400" data-testid="heatmaps-empty">
            No events captured yet. Make sure the tracking snippet is installed on your site and visit a page to start collecting data.
          </div>
        ) : (
          <div className="grid lg:grid-cols-[280px_1fr] gap-6">
            {/* URL picker */}
            <div className="space-y-1 max-h-[600px] overflow-y-auto pr-1" data-testid="heatmap-url-list">
              {pages.map(p => {
                const active = p.url === selectedUrl;
                return (
                  <button
                    key={p.url}
                    onClick={() => setSelectedUrl(p.url)}
                    className={`w-full text-left p-3 border ${active ? "border-brand bg-brand/[0.06]" : "border-white/[0.06] hover:border-white/20"} transition-colors`}
                    data-testid={`heatmap-url-${p.url.replace(/\W/g, "_")}`}
                  >
                    <div className="font-mono text-xs text-zinc-200 truncate">{p.url || "/"}</div>
                    <div className="mt-1 text-[10px] font-mono text-zinc-500">
                      {p.total} events · {p.clicks} clicks · {p.rage} rage
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Canvas + filters */}
            <div>
              <div className="flex items-center gap-1.5 mb-3 flex-wrap">
                {Object.entries(TYPE_LABELS).map(([k, v]) => {
                  const Icon = v.icon;
                  const count = summary?.[`${k}s`] ?? summary?.[k] ?? 0;
                  return (
                    <button
                      key={k}
                      onClick={() => setType(k)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border transition-colors ${type === k ? "border-brand text-brand bg-brand/[0.06]" : "border-white/10 text-zinc-400 hover:text-zinc-100"}`}
                      data-testid={`heatmap-type-${k}`}
                    >
                      <Icon className="h-3 w-3" /> {v.label} ({count})
                    </button>
                  );
                })}
              </div>

              <HeatmapCanvas events={events} loading={eventsLoading} color={TYPE_LABELS[type]?.color} />
            </div>
          </div>
        )}
      </div>
  );
}


function HeatmapCanvas({ events, loading, color }) {
  const canvasRef = useRef(null);
  const [size, setSize] = useState({ w: 800, h: 600 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    canvas.width = size.w;
    canvas.height = size.h;
    ctx.clearRect(0, 0, size.w, size.h);

    if (!events || events.length === 0) return;

    // Find bounds — most events carry a viewport width (w); use the median
    // so an outlier doesn't squish the heatmap. Y goes up to scroll depth.
    const widths = events.map(e => e.w || 1200).filter(w => w > 0);
    const refW = widths.length ? widths[Math.floor(widths.length / 2)] : 1200;
    const refH = Math.max(...events.map(e => e.y || 0), 800);
    const scaleX = size.w / refW;
    const scaleY = size.h / refH;

    // Render additive radial gradients so overlapping points stack into
    // a true density heat.
    ctx.globalCompositeOperation = "lighter";
    const radius = Math.max(12, Math.min(40, size.w / 30));
    for (const e of events) {
      const x = (e.x || 0) * scaleX;
      const y = (e.y || 0) * scaleY;
      const grd = ctx.createRadialGradient(x, y, 0, x, y, radius);
      grd.addColorStop(0, `${color}cc`);
      grd.addColorStop(0.5, `${color}55`);
      grd.addColorStop(1, `${color}00`);
      ctx.fillStyle = grd;
      ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
    }
    ctx.globalCompositeOperation = "source-over";
  }, [events, size, color]);

  useEffect(() => {
    const update = () => {
      const w = Math.min(1200, Math.max(400, window.innerWidth - 380));
      setSize({ w, h: Math.round(w * 0.7) });
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  return (
    <div className="relative bg-zinc-950 border border-white/[0.06]" style={{ width: size.w, height: size.h }} data-testid="heatmap-canvas-container">
      <canvas ref={canvasRef} className="absolute inset-0" />
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center text-zinc-400 text-sm font-mono">
          <Loader2 className="h-4 w-4 animate-spin mr-2" /> rendering…
        </div>
      )}
      {!loading && events.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-zinc-500 text-sm font-mono" data-testid="heatmap-canvas-empty">
          No events of this type yet for the selected page.
        </div>
      )}
      <div className="absolute bottom-2 right-2 text-[10px] font-mono text-zinc-600">
        {events.length} events plotted
      </div>
    </div>
  );
}

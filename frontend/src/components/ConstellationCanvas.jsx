import { useEffect, useRef } from "react";

/**
 * Animated particle + constellation field. Pure canvas, no deps.
 * Particles drift slowly; whenever two are within `LINK_DIST`, a cyan line
 * is drawn between them (opacity by distance). GPU-cheap, ~60fps at ~80 pts.
 *
 * Props:
 *  - density: number of particles (default 70)
 *  - color:   base stroke/fill color (default "#00E5FF")
 *  - className: extra classes to position the <canvas>
 */
export default function ConstellationCanvas({
  density = 70,
  color = "#00E5FF",
  className = "absolute inset-0 w-full h-full pointer-events-none",
}) {
  const canvasRef = useRef(null);
  const rafRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let width = 0;
    let height = 0;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      const rect = canvas.parentElement.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas.parentElement);

    // Particle init
    const rand = (a, b) => a + Math.random() * (b - a);
    const particles = Array.from({ length: density }, () => ({
      x: rand(0, width),
      y: rand(0, height),
      vx: rand(-0.18, 0.18),
      vy: rand(-0.18, 0.18),
      r: rand(0.6, 1.6),
    }));

    const LINK_DIST = 130;
    const LINK_DIST_SQ = LINK_DIST * LINK_DIST;

    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;

    const frame = () => {
      ctx.clearRect(0, 0, width, height);
      // draw lines
      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        if (!reduce) {
          a.x += a.vx;
          a.y += a.vy;
          if (a.x < 0 || a.x > width) a.vx *= -1;
          if (a.y < 0 || a.y > height) a.vy *= -1;
        }
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < LINK_DIST_SQ) {
            const t = 1 - d2 / LINK_DIST_SQ;
            ctx.strokeStyle = `rgba(0, 229, 255, ${0.12 * t})`;
            ctx.lineWidth = 0.6;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }
      // draw points
      ctx.fillStyle = color;
      for (const p of particles) {
        ctx.globalAlpha = 0.85;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      rafRef.current = requestAnimationFrame(frame);
    };

    rafRef.current = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, [density, color]);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}

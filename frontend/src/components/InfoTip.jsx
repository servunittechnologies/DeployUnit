import { Info } from "lucide-react";
import { useState, useRef, useLayoutEffect } from "react";

/**
 * Tiny info tooltip — hover or focus the icon, get an inline popover with
 * the explanation. No portal; positions itself with viewport awareness so
 * the tooltip never clips the right edge or jumps the layout.
 *
 * Usage:
 *   <InfoTip>Number of credits consumed in the last 30 days, broken down by category.</InfoTip>
 *
 * Props:
 *   - children: explanation copy (string or React node)
 *   - size: icon size in px (default 14)
 *   - align: "left" | "right" — which side the popover anchors to. Default "left".
 */
export default function InfoTip({ children, size = 14, align = "left", className = "" }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const [flip, setFlip] = useState(false);

  // If the popover would overflow the viewport, flip it to the other side.
  useLayoutEffect(() => {
    if (!open || !wrapRef.current) return;
    const rect = wrapRef.current.getBoundingClientRect();
    const popoverW = 260;
    const wouldOverflow = align === "left"
      ? rect.left + popoverW > window.innerWidth - 16
      : rect.right - popoverW < 16;
    setFlip(wouldOverflow);
  }, [open, align]);

  const actualAlign = flip ? (align === "left" ? "right" : "left") : align;

  return (
    <span
      ref={wrapRef}
      className={`relative inline-flex items-center align-middle ${className}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <button
        type="button"
        tabIndex={0}
        aria-label="More info"
        className="ml-1.5 text-zinc-500 hover:text-brand transition-colors focus:outline-none focus:text-brand cursor-help"
        data-testid="info-tip-trigger"
      >
        <Info width={size} height={size} />
      </button>
      {open && (
        <span
          className={`absolute top-full mt-2 z-50 w-[260px] p-3 bg-black/95 border border-white/10 shadow-xl text-[11px] leading-relaxed font-mono text-zinc-300 normal-case tracking-normal ${actualAlign === "left" ? "left-0" : "right-0"}`}
          role="tooltip"
          data-testid="info-tip-popover"
        >
          {children}
        </span>
      )}
    </span>
  );
}

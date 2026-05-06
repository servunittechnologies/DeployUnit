import { useEffect, useRef, useState } from "react";

/**
 * Matrix-style text scramble — reveals each character from a pool of glyphs.
 * Stable per `text` change, triggers once on mount, and can optionally replay
 * on `replayKey` change.
 */
const GLYPHS = "!<>-_\\/[]{}—=+*^?#________";

export default function useScrambleText(text, { durationMs = 900, replayKey = 0 } = {}) {
  const [output, setOutput] = useState(text);
  const rafRef = useRef(0);
  const startRef = useRef(0);

  useEffect(() => {
    const t0 = performance.now();
    startRef.current = t0;
    const duration = Math.max(250, durationMs);

    const tick = (now) => {
      const elapsed = now - startRef.current;
      const progress = Math.min(1, elapsed / duration);
      const chars = text.split("").map((ch, i) => {
        // Reveal order: left to right
        const revealAt = i / text.length;
        if (progress >= revealAt || ch === " ") return ch;
        return GLYPHS[(Math.floor((elapsed + i * 31) / 50)) % GLYPHS.length];
      });
      setOutput(chars.join(""));
      if (progress < 1) rafRef.current = requestAnimationFrame(tick);
      else setOutput(text);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, durationMs, replayKey]);

  return output;
}

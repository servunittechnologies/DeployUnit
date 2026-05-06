import { useEffect, useState } from "react";

/**
 * Typewriter — prints a string char-by-char. Emits a `done` flag when finished.
 * Respects prefers-reduced-motion.
 */
export default function useTypewriter(text, { startDelayMs = 0, cps = 28 } = {}) {
  const [output, setOutput] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    setOutput("");
    setDone(false);
    if (!text) {
      setDone(true);
      return;
    }

    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    if (reduce) {
      setOutput(text);
      setDone(true);
      return;
    }

    const intervalMs = Math.max(16, 1000 / cps);
    let i = 0;
    let iv = null;
    const startT = setTimeout(() => {
      iv = setInterval(() => {
        i += 1;
        setOutput(text.slice(0, i));
        if (i >= text.length) {
          clearInterval(iv);
          iv = null;
          setDone(true);
        }
      }, intervalMs);
    }, startDelayMs);

    return () => {
      clearTimeout(startT);
      if (iv) clearInterval(iv);
    };
  }, [text, startDelayMs, cps]);

  return { output, done };
}

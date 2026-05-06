import { useCallback } from "react";

/**
 * Binds `--mx` and `--my` CSS vars to the mouse position over an element.
 * Plug into any element via `onMouseMove={handleMouseMove}` and add the
 * `.spotlight` class (defined in index.css).
 */
export default function useSpotlight() {
  return useCallback((e) => {
    const t = e.currentTarget;
    const rect = t.getBoundingClientRect();
    t.style.setProperty("--mx", `${e.clientX - rect.left}px`);
    t.style.setProperty("--my", `${e.clientY - rect.top}px`);
  }, []);
}

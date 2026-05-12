import { useEffect } from "react";

/**
 * Lightweight per-route SEO updater — no react-helmet dep needed.
 * Updates <title>, <meta name="description">, <meta property="og:title"|
 * "og:description"|"og:url"> and the canonical link so link previews and
 * Google snippets match the page you're on.
 *
 * Crawlers like Googlebot DO execute JS now (and re-render after main),
 * but social previews (WhatsApp/Slack/Twitter/LinkedIn) DO NOT — they
 * read the static HTML. The defaults in /public/index.html cover the
 * landing page, and that's the link people will share 95% of the time.
 * This hook handles the rest for SEO indexing of inner pages.
 */
export default function useSeo({ title, description, path = "" }) {
  useEffect(() => {
    if (title) {
      document.title = title;
    }
    const set = (sel, attr, value) => {
      if (!value) return;
      let el = document.head.querySelector(sel);
      if (!el) {
        el = document.createElement("meta");
        // selector example: 'meta[name="description"]' or 'meta[property="og:title"]'
        const m = sel.match(/(name|property)="([^"]+)"/);
        if (m) el.setAttribute(m[1], m[2]);
        document.head.appendChild(el);
      }
      el.setAttribute(attr, value);
    };
    if (description) {
      set('meta[name="description"]', "content", description);
      set('meta[property="og:description"]', "content", description);
      set('meta[name="twitter:description"]', "content", description);
    }
    if (title) {
      // Strip the brand suffix for og:title — keep it punchy.
      const og = title.replace(/\s*[—|·]\s*DeployUnit.*$/i, "");
      set('meta[property="og:title"]', "content", og || title);
      set('meta[name="twitter:title"]', "content", og || title);
    }
    if (path && typeof window !== "undefined") {
      const url = `${window.location.origin}${path}`;
      set('meta[property="og:url"]', "content", url);
      set('meta[name="twitter:url"]', "content", url);
      let link = document.head.querySelector('link[rel="canonical"]');
      if (!link) {
        link = document.createElement("link");
        link.setAttribute("rel", "canonical");
        document.head.appendChild(link);
      }
      link.setAttribute("href", url);
    }
  }, [title, description, path]);
}

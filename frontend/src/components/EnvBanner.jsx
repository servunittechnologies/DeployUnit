import { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { api } from "../lib/api";

/**
 * Shows a sticky warning banner whenever the dashboard is being served
 * from a NON-production backend (preview / staging / unknown).
 *
 * On preview, writes to shared infra (Coolify, Cloudflare, Mollie,
 * MailerSend, SMS, GitHub deploy keys) are silently dropped by the
 * backend — so without a visual cue the user could believe they're
 * making real changes when they're not.
 *
 * The banner is dismissible per-session (sessionStorage so it returns
 * after a reload), and the toggle ID `env-banner` lets tests assert
 * presence/absence reliably.
 */
export default function EnvBanner() {
  const [info, setInfo] = useState(null);
  const [dismissed, setDismissed] = useState(
    typeof window !== "undefined" && sessionStorage.getItem("env-banner-dismissed") === "1"
  );

  useEffect(() => {
    let alive = true;
    api.get("/env-info").then((r) => { if (alive) setInfo(r.data); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  if (!info || info.is_production || dismissed) return null;

  const dismiss = () => {
    sessionStorage.setItem("env-banner-dismissed", "1");
    setDismissed(true);
  };

  return (
    <div
      className="bg-amber-500/15 border-b border-amber-500/40 text-amber-100 text-xs"
      data-testid="env-banner"
      data-env={info.env}
    >
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-2 flex items-start gap-3">
        <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0 text-amber-300" />
        <div className="flex-1 leading-relaxed">
          <span className="font-mono uppercase tracking-[0.2em] text-amber-300 mr-2">
            preview · {info.env}
          </span>
          This backend is <span className="font-semibold">isolated from live infra</span>.
          Toggles persist in this preview database only — writes to the build engine, DNS, payments,
          email and SMS are blocked. Use{" "}
          <a href="https://deployunit.com/app" className="underline hover:text-white">
            deployunit.com
          </a>{" "}
          for changes that should affect real customers.
        </div>
        <button
          onClick={dismiss}
          aria-label="Dismiss preview banner"
          data-testid="env-banner-dismiss"
          className="text-amber-300 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

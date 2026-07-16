import { Loader2, KeyRound } from "lucide-react";
import { useState } from "react";
import { api, getApiErrorMessage } from "../lib/api";

// "Login with WHMCS" — mirrors GitHubButton. Hands off to the WHMCS launcher,
// which authenticates the customer with their WHMCS login and bounces them
// back into DeployUnit via the internal SSO one-time link.
export default function WhmcsButton({ label, className = "", testId = "whmcs-login-button" }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const start = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/auth/whmcs/start");
      window.location.href = data.authorization_url;
    } catch (e) {
      setError(getApiErrorMessage(e));
      setLoading(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={start}
        disabled={loading}
        className={`w-full inline-flex items-center justify-center gap-2 py-2.5 border border-white/15 hover:border-white/40 hover:bg-white/[0.02] transition disabled:opacity-50 ${className}`}
        data-testid={testId}
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
        {label || "Continue with ServUnit"}
      </button>
      {error && <div className="mt-2 text-signal-failed text-xs font-mono">{error}</div>}
    </>
  );
}

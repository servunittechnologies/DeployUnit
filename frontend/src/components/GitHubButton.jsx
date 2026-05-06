import { Github, Loader2 } from "lucide-react";
import { useState } from "react";
import { api, getApiErrorMessage } from "../lib/api";

export default function GitHubButton({ redirectTo = null, link = false, label, className = "", testId = "github-oauth-button" }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const start = async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (redirectTo) params.redirect_to = redirectTo;
      if (link) params.link = true;
      const { data } = await api.get("/auth/github/start", { params });
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
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Github className="h-4 w-4" />}
        {label || "Continue with GitHub"}
      </button>
      {error && <div className="mt-2 text-signal-failed text-xs font-mono">{error}</div>}
    </>
  );
}

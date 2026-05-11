import axios from "axios";

// Resolve the backend base URL at RUNTIME, not build-time:
//  - On localhost (dev), fall back to REACT_APP_BACKEND_URL (.env)
//  - On any deployed host (preview, production, custom domain like
//    deployunit.com), use the current origin so requests are same-origin
//    and the Kubernetes ingress routes /api/* to the backend pod.
// This makes the same JS bundle work across all environments without rebuilds.
function resolveBackendUrl() {
  const envUrl = process.env.REACT_APP_BACKEND_URL || "";
  if (typeof window === "undefined") return envUrl;
  const origin = window.location.origin;
  if (!origin) return envUrl;
  if (origin.includes("localhost") || origin.startsWith("http://127.")) {
    // Local dev — call the configured remote (or local) backend
    return envUrl || origin;
  }
  return origin;
}

const BACKEND_URL = resolveBackendUrl();

export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export function getApiErrorMessage(err) {
  if (!err) return "Network error";
  if (err.response?.data?.detail) return formatApiErrorDetail(err.response.data.detail);
  if (err.message) return err.message;
  return "Unexpected error";
}

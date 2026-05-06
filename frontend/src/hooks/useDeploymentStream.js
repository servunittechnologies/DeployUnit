import { useEffect, useRef, useState } from "react";

/** Subscribe to /api/deployments/{id}/stream when active=true.
 * Returns { lines, status, ended } where lines is an array of {text, severity}.
 */
export default function useDeploymentStream(deploymentId, { active, initialLines = [], onStatusChange }) {
  const [lines, setLines] = useState(initialLines);
  const [status, setStatus] = useState(null);
  const [failureSummary, setFailureSummary] = useState(null);
  const [ended, setEnded] = useState(false);
  const [connected, setConnected] = useState(false);
  const esRef = useRef(null);
  const linesRef = useRef(initialLines);

  // Reset when deploymentId or active changes
  useEffect(() => {
    linesRef.current = initialLines;
    setLines(initialLines);
    setStatus(null);
    setFailureSummary(null);
    setEnded(false);
    setConnected(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deploymentId, active]);

  useEffect(() => {
    if (!deploymentId || !active) return undefined;

    const url = `${process.env.REACT_APP_BACKEND_URL}/api/deployments/${deploymentId}/stream`;
    const es = new EventSource(url, { withCredentials: true });
    esRef.current = es;
    setConnected(false);

    es.onopen = () => setConnected(true);

    es.addEventListener("line", (e) => {
      try {
        const data = JSON.parse(e.data);
        linesRef.current = [...linesRef.current, data];
        setLines(linesRef.current);
      } catch (err) { /* ignore */ }
    });

    es.addEventListener("status", (e) => {
      try {
        const data = JSON.parse(e.data);
        setStatus(data.status);
        setFailureSummary(data.failure_summary || null);
        onStatusChange?.(data);
      } catch (err) { /* ignore */ }
    });

    es.addEventListener("end", () => {
      setEnded(true);
      es.close();
    });

    es.onerror = () => {
      setConnected(false);
      // browser will auto-retry; if deployment finished, we already closed.
    };

    return () => {
      try { es.close(); } catch { /* */ }
      esRef.current = null;
    };
  }, [deploymentId, active, onStatusChange]);

  return { lines, status, failureSummary, ended, connected, setLines };
}

import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading || user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="font-mono text-xs uppercase tracking-[0.3em] text-zinc-500">
          <span className="inline-block w-2 h-2 rounded-full bg-brand mr-3 animate-ping-soft" />
          Booting workspace...
        </div>
      </div>
    );
  }
  if (user === false) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
}

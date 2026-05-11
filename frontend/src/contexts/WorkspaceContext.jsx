import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { useAuth } from "./AuthContext";

const WorkspaceContext = createContext(null);
const STORAGE_KEY = "deployunit.activeWorkspace";

export function WorkspaceProvider({ children }) {
  const { user } = useAuth();
  const [workspaces, setWorkspaces] = useState([]);
  const [activeId, setActiveId] = useState(() => localStorage.getItem(STORAGE_KEY) || null);
  const [loading, setLoading] = useState(false);

  const fetchWorkspaces = useCallback(async () => {
    if (!user || user === false) return;
    setLoading(true);
    try {
      const { data } = await api.get("/workspaces");
      setWorkspaces(data);
      if (data.length) {
        const stored = localStorage.getItem(STORAGE_KEY);
        const match = stored && data.find((w) => w.id === stored);
        if (!match) {
          setActiveId(data[0].id);
          localStorage.setItem(STORAGE_KEY, data[0].id);
        } else if (!activeId) {
          setActiveId(stored);
        }
      }
    } finally {
      setLoading(false);
    }
  }, [user, activeId]);

  useEffect(() => {
    fetchWorkspaces();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const setActive = (id) => {
    setActiveId(id);
    localStorage.setItem(STORAGE_KEY, id);
  };

  const createWorkspace = async ({ name, type = "solo" }) => {
    const { data } = await api.post("/workspaces", { name, type });
    setWorkspaces((prev) => [...prev, { ...data, my_role: "owner" }]);
    setActive(data.id);
    return data;
  };

  const active = workspaces.find((w) => w.id === activeId) || workspaces[0] || null;

  return (
    <WorkspaceContext.Provider
      value={{ workspaces, activeId: active?.id, active, setActive, loading, refresh: fetchWorkspaces, createWorkspace }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export const useWorkspace = () => useContext(WorkspaceContext);

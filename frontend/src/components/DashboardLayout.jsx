import { useState, useEffect } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import Logo from "./Logo";
import {
  LayoutGrid, FolderKanban, Globe, Activity, Bell, CreditCard, Settings, LogOut,
  Plus, Boxes, Search, BellRing, ChevronsUpDown, Check, Building2, User as UserIcon,
  ShieldCheck, Layers, Database, FileClock,
} from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  DropdownMenuLabel, DropdownMenuSeparator,
} from "./ui/dropdown-menu";
import { Button } from "./ui/button";

const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutGrid, end: true },
  { to: "/app/projects", label: "Projects", icon: FolderKanban },
  { to: "/app/fleet", label: "Fleet", icon: Layers, agencyOnly: true },
  { to: "/app/databases", label: "Databases", icon: Database },
  { to: "/app/domains", label: "Domains", icon: Globe },
  { to: "/app/monitoring", label: "Monitoring", icon: Activity },
  { to: "/app/alerts", label: "Alerts", icon: BellRing },
  { to: "/app/audit", label: "Audit log", icon: FileClock },
  { to: "/app/billing", label: "Billing", icon: CreditCard },
  { to: "/app/settings", label: "Settings", icon: Settings },
];
const ADMIN_NAV = { to: "/app/admin", label: "Admin Console", icon: ShieldCheck };

function WorkspaceSwitcher() {
  const { workspaces, active, setActive, createWorkspace } = useWorkspace();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const handleCreate = async () => {
    if (!name.trim()) return;
    await createWorkspace({ name: name.trim(), type: "agency" });
    setName("");
    setCreating(false);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="w-full flex items-center justify-between gap-2 px-3 py-2 border border-white/10 hover:border-white/30 transition-colors group"
          data-testid="workspace-switcher"
        >
          <div className="min-w-0 text-left">
            <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500">Workspace</div>
            <div className="font-display text-sm font-medium truncate">{active?.name || "—"}</div>
          </div>
          <ChevronsUpDown className="h-4 w-4 text-zinc-500 group-hover:text-white" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel className="font-mono text-[10px] uppercase tracking-[0.3em] text-zinc-500">
          Switch workspace
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {workspaces.map((w) => (
          <DropdownMenuItem
            key={w.id}
            onClick={() => setActive(w.id)}
            data-testid={`workspace-option-${w.slug}`}
            className="flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              {w.type === "agency" ? <Building2 className="h-4 w-4" /> : <UserIcon className="h-4 w-4" />}
              <span>{w.name}</span>
            </div>
            {active?.id === w.id && <Check className="h-4 w-4 text-brand" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        {!creating ? (
          <DropdownMenuItem onSelect={(e) => { e.preventDefault(); setCreating(true); }} className="text-brand">
            <Plus className="h-4 w-4 mr-2" /> Create new workspace
          </DropdownMenuItem>
        ) : (
          <div className="p-2 space-y-2">
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Acme Studio"
              className="w-full px-2 py-1.5 bg-black border border-white/10 text-sm font-mono focus:border-brand outline-none"
              data-testid="new-workspace-input"
            />
            <div className="flex gap-2">
              <Button size="sm" className="rounded-none flex-1 bg-brand text-brand-fg hover:bg-brand/80" onClick={handleCreate} data-testid="new-workspace-confirm">Create</Button>
              <Button size="sm" variant="ghost" className="rounded-none" onClick={() => setCreating(false)}>Cancel</Button>
            </div>
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function NotificationsBell() {
  const { active } = useWorkspace();
  const [notifs, setNotifs] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!active) return;
    api.get("/notifications", { params: { workspace_id: active.id } })
      .then((r) => setNotifs(r.data || []))
      .catch(() => setNotifs([]));
  }, [active, open]);

  const unread = notifs.filter((n) => !n.read).length;

  const markAll = async () => {
    if (!active) return;
    await api.post("/notifications/read-all", null, { params: { workspace_id: active.id } }).catch(() => {});
    setNotifs((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button className="relative p-2 hover:bg-white/5 border border-white/10" data-testid="notifications-trigger">
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-brand animate-ping-soft" />
          )}
          {unread > 0 && (
            <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-brand" />
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-96 max-h-[480px] overflow-auto">
        <div className="flex items-center justify-between px-2 py-1.5">
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-zinc-500">Notifications</span>
          {unread > 0 && (
            <button onClick={markAll} className="text-xs text-brand hover:underline" data-testid="notifications-mark-all">
              Mark all read
            </button>
          )}
        </div>
        <DropdownMenuSeparator />
        {notifs.length === 0 ? (
          <div className="px-3 py-6 text-sm text-zinc-500 text-center">All clear. No notifications.</div>
        ) : (
          notifs.slice(0, 12).map((n) => (
            <div key={n.id} className={`px-3 py-2 border-b border-white/5 ${n.read ? "opacity-60" : ""}`}>
              <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                <span className={`h-1.5 w-1.5 rounded-full ${n.severity === "error" ? "bg-signal-failed" : n.severity === "warning" ? "bg-signal-queued" : n.severity === "success" ? "bg-signal-live" : "bg-brand"}`} />
                {n.type}
              </div>
              <div className="text-sm font-medium mt-0.5">{n.title}</div>
              <div className="text-xs text-zinc-400 mt-0.5">{n.message}</div>
            </div>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const initials = (user?.name || user?.email || "?").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-2 px-2 py-1.5 hover:bg-white/5 border border-white/10" data-testid="user-menu-trigger">
          <span className="h-7 w-7 rounded-full bg-elevated flex items-center justify-center text-xs font-mono">{initials}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <div className="text-sm font-medium">{user?.name}</div>
          <div className="text-xs text-zinc-500 font-mono">{user?.email}</div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => navigate("/app/settings")}>Settings</DropdownMenuItem>
        <DropdownMenuItem onClick={() => navigate("/app/billing")}>Billing</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={async () => { await logout(); navigate("/"); }} data-testid="logout-button" className="text-signal-failed">
          <LogOut className="h-4 w-4 mr-2" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function DashboardLayout() {
  const { user } = useAuth();
  const { active } = useWorkspace();
  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <aside className="w-64 hidden lg:flex flex-col border-r border-white/[0.06] sticky top-0 h-screen">
        <div className="p-5 border-b border-white/[0.06]">
          <Link to="/app"><Logo /></Link>
        </div>
        <div className="p-4 border-b border-white/[0.06]">
          <WorkspaceSwitcher />
        </div>
        <nav className="flex-1 py-4">
          {NAV.filter((n) => !n.agencyOnly || active?.type === "agency").map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              data-testid={`nav-${n.label.toLowerCase()}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm border-l-2 transition-colors ${
                  isActive
                    ? "border-brand text-white bg-white/[0.03]"
                    : "border-transparent text-zinc-400 hover:text-white hover:bg-white/[0.02]"
                }`
              }
            >
              <n.icon className="h-4 w-4" />
              {n.label}
            </NavLink>
          ))}
          {user?.role === "admin" && (
            <>
              <div className="mx-5 my-4 h-px bg-white/[0.06]" />
              <NavLink
                to={ADMIN_NAV.to}
                data-testid="nav-admin"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-5 py-2.5 text-sm border-l-2 transition-colors ${
                    isActive
                      ? "border-brand text-white bg-white/[0.03]"
                      : "border-transparent text-zinc-400 hover:text-white hover:bg-white/[0.02]"
                  }`
                }
              >
                <ADMIN_NAV.icon className="h-4 w-4 text-brand" />
                {ADMIN_NAV.label}
              </NavLink>
            </>
          )}
        </nav>
        <Link
          to="/app/apps/new"
          className="m-4 flex items-center justify-center gap-2 py-2.5 bg-brand text-brand-fg font-medium hover:bg-brand/90 active:scale-95 transition-transform shadow-[0_0_20px_rgba(0,229,255,0.25)]"
          data-testid="cta-new-app"
        >
          <Plus className="h-4 w-4" /> New App
        </Link>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="glass sticky top-0 z-30 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/app" className="lg:hidden"><Logo small /></Link>
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 border border-white/10 text-zinc-500 text-sm w-72">
              <Search className="h-3.5 w-3.5" />
              <input className="bg-transparent outline-none flex-1 text-xs font-mono placeholder:text-zinc-600" placeholder="search apps, deployments..." data-testid="topbar-search" />
              <span className="text-[10px] font-mono text-zinc-600">⌘K</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/app/apps/new"
              className="hidden lg:flex items-center gap-2 px-3 py-1.5 border border-white/15 text-xs font-mono uppercase tracking-wider hover:border-brand hover:text-brand transition-colors"
            >
              <Plus className="h-3 w-3" /> Deploy
            </Link>
            <NotificationsBell />
            <UserMenu />
          </div>
        </header>
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "@/App.css";
import "@/index.css";
import { AuthProvider } from "./contexts/AuthContext";
import { WorkspaceProvider } from "./contexts/WorkspaceContext";
import ProtectedRoute from "./components/ProtectedRoute";
import DashboardLayout from "./components/DashboardLayout";
import { Toaster } from "@/components/ui/sonner";

import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Pricing from "./pages/Pricing";
import Checkout from "./pages/Checkout";
import Overview from "./pages/dashboard/Overview";
import Projects from "./pages/dashboard/Projects";
import ProjectDetail from "./pages/dashboard/ProjectDetail";
import NewApp from "./pages/dashboard/NewApp";
import AppDetail from "./pages/dashboard/AppDetail";
import Domains from "./pages/dashboard/Domains";
import Monitoring from "./pages/dashboard/Monitoring";
import Alerts from "./pages/dashboard/Alerts";
import Billing from "./pages/dashboard/Billing";
import Settings from "./pages/dashboard/Settings";
import Account from "./pages/dashboard/Account";
import Admin from "./pages/dashboard/Admin";
import Fleet from "./pages/dashboard/Fleet";
import AuditLog from "./pages/dashboard/AuditLog";
import Databases from "./pages/dashboard/Databases";
import Roadmap from "./pages/dashboard/Roadmap";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";

function App() {
  return (
    <div className="App min-h-screen bg-background text-foreground">
      <BrowserRouter>
        <AuthProvider>
          <WorkspaceProvider>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/pricing" element={<Pricing />} />
              <Route
                path="/checkout"
                element={
                  <ProtectedRoute>
                    <Checkout />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/app"
                element={
                  <ProtectedRoute>
                    <DashboardLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Overview />} />
                <Route path="projects" element={<Projects />} />
                <Route path="projects/:id" element={<ProjectDetail />} />
                <Route path="apps/new" element={<NewApp />} />
                <Route path="apps/:id" element={<AppDetail />} />
                <Route path="domains" element={<Domains />} />
                <Route path="monitoring" element={<Monitoring />} />
                <Route path="alerts" element={<Alerts />} />
                <Route path="billing" element={<Billing />} />
                <Route path="settings" element={<Settings />} />
                <Route path="account" element={<Account />} />
                <Route path="admin" element={<Admin />} />
                <Route path="fleet" element={<Fleet />} />
                <Route path="audit" element={<AuditLog />} />
                <Route path="databases" element={<Databases />} />
                <Route path="roadmap" element={<Roadmap />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            <Toaster richColors position="top-right" />
          </WorkspaceProvider>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;

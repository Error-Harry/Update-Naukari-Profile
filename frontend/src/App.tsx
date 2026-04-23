import { Navigate, Route, Routes } from "react-router-dom";
import { useMe } from "@/lib/auth";
import { AuthPage } from "@/pages/Auth";
import { DashboardPage } from "@/pages/Dashboard";
import { BillingPage } from "@/pages/Billing";
import { AdminPage } from "@/pages/Admin";
import { AppShell } from "@/components/layout/AppShell";
import { Loader2 } from "lucide-react";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const me = useMe();
  if (me.isLoading) return <FullPageLoader />;
  if (!me.data) return <Navigate to="/login" replace />;
  return <AppShell>{children}</AppShell>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const me = useMe();
  if (me.isLoading) return <FullPageLoader />;
  if (!me.data) return <Navigate to="/login" replace />;
  if (me.data.user.role !== "admin") return <Navigate to="/" replace />;
  return <AppShell>{children}</AppShell>;
}

function FullPageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/billing"
        element={
          <ProtectedRoute>
            <BillingPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <AdminRoute>
            <AdminPage />
          </AdminRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

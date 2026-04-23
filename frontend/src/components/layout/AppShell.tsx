import { NavLink, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { LayoutDashboard, CreditCard, Shield, LogOut, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useMe, logout } from "@/lib/auth";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const me = useMe();
  const navigate = useNavigate();
  const user = me.data?.user;
  const isAdmin = user?.role === "admin";
  const isPaid = user?.subscription === "paid";

  const doLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="relative min-h-screen">
      <div className="pointer-events-none fixed inset-0 -z-10 animated-gradient" />

      <header className="sticky top-0 z-40 border-b bg-background/70 backdrop-blur-lg">
        <div className="container mx-auto flex h-16 items-center justify-between gap-4 px-4">
          <NavLink to="/" className="flex items-center gap-2 font-semibold">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-primary/15 text-primary">
              <Sparkles className="h-4 w-4" />
            </div>
            <span>Naukri Auto Update</span>
          </NavLink>

          <nav className="hidden items-center gap-1 md:flex">
            <NavItem to="/" icon={<LayoutDashboard className="h-4 w-4" />}>
              Dashboard
            </NavItem>
            <NavItem to="/billing" icon={<CreditCard className="h-4 w-4" />}>
              Billing
            </NavItem>
            {isAdmin && (
              <NavItem to="/admin" icon={<Shield className="h-4 w-4" />}>
                Admin
              </NavItem>
            )}
          </nav>

          <div className="flex items-center gap-3">
            <div className="hidden flex-col items-end text-right sm:flex">
              <span className="text-sm font-medium leading-none">
                {user?.name ?? "User"}
              </span>
              <span className="mt-1 flex items-center gap-2">
                {isPaid ? (
                  <Badge variant="success">Pro</Badge>
                ) : (
                  <Badge variant="secondary">Free</Badge>
                )}
                {isAdmin && <Badge variant="warning">Admin</Badge>}
              </span>
            </div>
            <Button variant="ghost" size="icon" onClick={doLogout} title="Log out">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <nav className="container mx-auto flex gap-1 overflow-x-auto border-t px-2 py-2 md:hidden">
          <NavItem to="/" icon={<LayoutDashboard className="h-4 w-4" />}>
            Dashboard
          </NavItem>
          <NavItem to="/billing" icon={<CreditCard className="h-4 w-4" />}>
            Billing
          </NavItem>
          {isAdmin && (
            <NavItem to="/admin" icon={<Shield className="h-4 w-4" />}>
              Admin
            </NavItem>
          )}
        </nav>
      </header>

      <motion.main
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="container mx-auto px-4 py-8"
      >
        {children}
      </motion.main>
    </div>
  );
}

function NavItem({
  to,
  icon,
  children,
}: {
  to: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-primary/10 text-primary"
            : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )
      }
    >
      {icon}
      {children}
    </NavLink>
  );
}

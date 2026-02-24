import { Link, useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Zap, LogOut, LayoutDashboard, Shield, User } from "lucide-react";
import { useEffect, useState } from "react";
import { getSession, logout, adminLogin, type SessionUser } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

/**
 * Main navigation bar for CircuitForge Lab
 * Shows auth state and role-based navigation
 */
export default function Navbar() {
  const navigate = useNavigate();
  const [user, setUser] = useState<SessionUser | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const { toast } = useToast();
  const location = useLocation();
  const hideAdminOnDashboard = location.pathname.startsWith("/dashboard");

  useEffect(() => {
    getSession()
      .then((data) => {
        setUser(data.user);
        setIsAdmin(data.roles.includes("admin"));
      })
      .catch(() => {
        setUser(null);
        setIsAdmin(false);
      });
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // ignore
    }
    navigate("/");
  };

  const handleAdminClick = async () => {
    if (isAdmin) {
      navigate("/admin");
      return;
    }

    const name = window.prompt("Enter admin name:");
    if (!name) return;
    const password = window.prompt("Enter admin password:");
    if (!password) return;

    try {
      await adminLogin(name, password);
      // Immediately navigate to the admin dashboard after admin credentials
      // are accepted. Server-side admin cookie will allow admin API access.
      navigate("/admin");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Invalid admin credentials";
      toast({ variant: "destructive", title: "Admin login failed", description: message });
    }
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="container flex h-14 items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 font-bold text-lg">
          <Zap className="h-5 w-5 text-primary" />
          <span className="text-foreground">Circuit</span>
          <span className="text-primary">Forge</span>
        </Link>

        {/* Navigation */}
        <div className="flex items-center gap-2">
          {user ? (
            <>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/dashboard">
                  <LayoutDashboard className="h-4 w-4 mr-1" />
                  Dashboard
                </Link>
              </Button>
              {isAdmin && !hideAdminOnDashboard && (
                <Button variant="ghost" size="sm" onClick={handleAdminClick}>
                  <Shield className="h-4 w-4 mr-1" />
                  Admin
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="h-4 w-4 mr-1" />
                Logout
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/auth">Sign In</Link>
              </Button>
              <Button size="sm" asChild>
                <Link to="/auth?tab=signup">Get Started</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

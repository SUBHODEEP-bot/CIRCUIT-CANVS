import { Link, useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Zap, LogOut, LayoutDashboard, Shield, User, Edit2 } from "lucide-react";
import { useEffect, useState } from "react";
import { getSession, logout, adminLogin, updateProfile, type SessionUser } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";

/**
 * Main navigation bar for CircuitForge Lab
 * Shows auth state and role-based navigation
 */
export default function Navbar() {
  const navigate = useNavigate();
  const [user, setUser] = useState<SessionUser | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [newName, setNewName] = useState("");
  const { toast } = useToast();
  const location = useLocation();
  const hideAdminOnDashboard = location.pathname.startsWith("/dashboard");

  useEffect(() => {
    getSession()
      .then((data) => {
        setUser(data.user);
        setIsAdmin(data.roles.includes("admin"));
        if (data.user?.display_name) {
          setNewName(data.user.display_name);
        }
      })
      .catch(() => {
        setUser(null);
        setIsAdmin(false);
      });
  }, []);

  const handleUpdateName = async () => {
    if (!newName.trim()) {
      toast({ variant: "destructive", title: "Error", description: "Name cannot be empty" });
      return;
    }

    try {
      const result = await updateProfile(newName.trim());
      if (result.user) {
        setUser(result.user);
        setEditingName(false);
        toast({ title: "Success", description: "Display name updated!" });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to update name";
      toast({ variant: "destructive", title: "Error", description: message });
    }
  };

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
              
              {/* User Profile Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm">
                    <User className="h-4 w-4 mr-1" />
                    {user.display_name || user.email || "User"}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  {editingName ? (
                    <div className="p-3 space-y-2">
                      <div className="text-xs font-medium text-muted-foreground">Update Display Name</div>
                      <Input
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        placeholder="Your name"
                        className="h-8"
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          className="flex-1"
                          onClick={handleUpdateName}
                        >
                          Save
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="flex-1"
                          onClick={() => {
                            setEditingName(false);
                            setNewName(user.display_name || "");
                          }}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <DropdownMenuItem disabled>
                        <span className="text-xs text-muted-foreground">{user.email}</span>
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => setEditingName(true)}>
                        <Edit2 className="h-4 w-4 mr-2" />
                        Edit Profile
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={handleLogout} className="text-destructive">
                        <LogOut className="h-4 w-4 mr-2" />
                        Logout
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
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

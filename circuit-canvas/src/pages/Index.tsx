import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import Navbar from "@/components/layout/Navbar";
import { Zap, Cpu, Cable, FolderOpen, ArrowRight, Shield } from "lucide-react";
import { getSession, adminLogin } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

/**
 * Landing page for CircuitForge Lab
 * Dark, circuit-board themed hero with feature highlights
 */
const Index = () => {
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleAdminClick = async () => {
    const name = window.prompt("Enter admin name:");
    if (!name) return;
    const password = window.prompt("Enter admin password:");
    if (!password) return;

    try {
      await adminLogin(name, password);
      // Admin credentials accepted — navigate directly to the admin dashboard.
      navigate("/admin");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Invalid admin credentials";
      toast({ variant: "destructive", title: "Admin login failed", description: message });
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-14">
        {/* Animated background grid */}
        <div className="absolute inset-0 circuit-grid opacity-30" />
        {/* Radial glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-primary/5 blur-3xl" />

        <div className="relative container flex flex-col items-center justify-center min-h-[90vh] text-center px-4">
          {/* Badge */}
          <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/5 px-4 py-1.5 text-sm text-primary">
            <Zap className="h-3.5 w-3.5" />
            Visual Circuit Design Platform
          </div>

          {/* Main heading */}
          <h1 className="text-5xl sm:text-6xl md:text-7xl font-black tracking-tight text-foreground mb-6 leading-tight">
            Design Circuits
            <br />
            <span className="text-primary text-glow-cyan">Visually</span>
          </h1>

          <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mb-10 leading-relaxed">
            Select modules, place them on an interactive canvas, connect pins with colored wires, 
            and bring your electronic projects to life — all in your browser.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4">
            <Button size="lg" className="glow-cyan text-lg px-8 h-12" asChild>
              <Link to="/auth?tab=signup">
                Start Building
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
            </Button>
            <Button variant="outline" size="lg" className="text-lg px-8 h-12" asChild>
              <Link to="/auth">Sign In</Link>
            </Button>
            <Button
              variant="outline"
              size="lg"
              className="text-lg px-8 h-12 border-primary/50 text-primary hover:bg-primary/10"
              onClick={handleAdminClick}
            >
              <Shield className="mr-2 h-5 w-5" />
              Admin
            </Button>
          </div>

          {/* Decorative circuit nodes */}
          <div className="mt-20 w-full max-w-4xl">
            <CircuitHeroGraphic />
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="relative py-24 border-t border-border">
        <div className="container px-4">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4 text-foreground">
            Everything You Need
          </h2>
          <p className="text-muted-foreground text-center mb-16 max-w-xl mx-auto">
            A complete circuit design toolkit built for speed and simplicity.
          </p>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
            <FeatureCard
              icon={<Cpu className="h-8 w-8" />}
              title="Module Library"
              description="Browse and select from a growing collection of electronic modules with pre-defined pin layouts."
            />
            <FeatureCard
              icon={<Cable className="h-8 w-8" />}
              title="Wire Connections"
              description="Click pins to connect them with color-coded wires. Wires auto-redraw when modules move."
            />
            <FeatureCard
              icon={<FolderOpen className="h-8 w-8" />}
              title="Project System"
              description="Save and load your circuit designs. All module positions and wire connections are preserved."
            />
            <FeatureCard
              icon={<Zap className="h-8 w-8" />}
              title="Future Ready"
              description="Architecture designed for connection validation, auto code generation, and simulation."
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8">
        <div className="container text-center text-sm text-muted-foreground">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Zap className="h-4 w-4 text-primary" />
            <span className="font-semibold text-foreground">CircuitForge Lab</span>
          </div>
          <p>Visual circuit design for everyone.</p>
        </div>
      </footer>
    </div>
  );
};

/** Feature card component */
function FeatureCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="group rounded-xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:glow-cyan">
      <div className="mb-4 text-primary">{icon}</div>
      <h3 className="text-lg font-semibold text-card-foreground mb-2">{title}</h3>
      <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
    </div>
  );
}

/** SVG circuit graphic for the hero section */
function CircuitHeroGraphic() {
  return (
    <svg viewBox="0 0 800 200" className="w-full h-auto opacity-60" xmlns="http://www.w3.org/2000/svg">
      {/* Traces */}
      <line x1="100" y1="100" x2="300" y2="100" stroke="hsl(187 100% 42%)" strokeWidth="2" strokeDasharray="8 4" className="animate-trace" />
      <line x1="300" y1="100" x2="300" y2="50" stroke="hsl(152 76% 36%)" strokeWidth="2" strokeDasharray="8 4" className="animate-trace" style={{ animationDelay: '0.5s' }} />
      <line x1="300" y1="50" x2="500" y2="50" stroke="hsl(187 100% 42%)" strokeWidth="2" strokeDasharray="8 4" className="animate-trace" style={{ animationDelay: '1s' }} />
      <line x1="500" y1="50" x2="500" y2="150" stroke="hsl(152 76% 36%)" strokeWidth="2" strokeDasharray="8 4" className="animate-trace" style={{ animationDelay: '1.5s' }} />
      <line x1="500" y1="150" x2="700" y2="150" stroke="hsl(187 100% 42%)" strokeWidth="2" strokeDasharray="8 4" className="animate-trace" style={{ animationDelay: '2s' }} />
      <line x1="300" y1="100" x2="500" y2="100" stroke="hsl(152 76% 36%)" strokeWidth="2" strokeDasharray="8 4" className="animate-trace" style={{ animationDelay: '0.7s' }} />
      <line x1="500" y1="100" x2="700" y2="100" stroke="hsl(187 100% 42%)" strokeWidth="2" strokeDasharray="8 4" className="animate-trace" style={{ animationDelay: '1.2s' }} />

      {/* Nodes */}
      {[
        { cx: 100, cy: 100 },
        { cx: 300, cy: 100 },
        { cx: 300, cy: 50 },
        { cx: 500, cy: 50 },
        { cx: 500, cy: 100 },
        { cx: 500, cy: 150 },
        { cx: 700, cy: 100 },
        { cx: 700, cy: 150 },
      ].map((pos, i) => (
        <g key={i}>
          <circle cx={pos.cx} cy={pos.cy} r="8" fill="hsl(222 47% 6%)" stroke="hsl(187 100% 42%)" strokeWidth="2" />
          <circle cx={pos.cx} cy={pos.cy} r="3" fill="hsl(187 100% 42%)" className="animate-glow-pulse" style={{ animationDelay: `${i * 0.3}s` }} />
        </g>
      ))}

      {/* Module boxes */}
      <rect x="60" y="70" width="80" height="60" rx="6" fill="none" stroke="hsl(152 76% 36% / 0.5)" strokeWidth="1.5" />
      <text x="100" y="105" textAnchor="middle" fill="hsl(152 76% 36%)" fontSize="10" fontFamily="JetBrains Mono">MCU</text>

      <rect x="460" y="70" width="80" height="60" rx="6" fill="none" stroke="hsl(187 100% 42% / 0.5)" strokeWidth="1.5" />
      <text x="500" y="105" textAnchor="middle" fill="hsl(187 100% 42%)" fontSize="10" fontFamily="JetBrains Mono">SENSOR</text>

      <rect x="660" y="120" width="80" height="60" rx="6" fill="none" stroke="hsl(152 76% 36% / 0.5)" strokeWidth="1.5" />
      <text x="700" y="155" textAnchor="middle" fill="hsl(152 76% 36%)" fontSize="10" fontFamily="JetBrains Mono">LED</text>
    </svg>
  );
}

export default Index;

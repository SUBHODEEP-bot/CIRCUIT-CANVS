import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import Navbar from "@/components/layout/Navbar";
import { Plus, FolderOpen, Trash2, Cpu, Clock, Search } from "lucide-react";
import type { Module, Project, CanvasData } from "@/lib/circuit-types";
import { getSession, getProjects, getModules, createProject as apiCreateProject, deleteProject as apiDeleteProject } from "@/lib/api";

/**
 * User dashboard showing projects and module gallery
 */
export default function Dashboard() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [projects, setProjects] = useState<Project[]>([]);
  const [modules, setModules] = useState<Module[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Auth guard
    const checkAuth = async () => {
      try {
        const session = await getSession();
        if (!session.user) {
          navigate("/auth");
          return;
        }
        loadData();
      } catch {
        navigate("/auth");
      }
    };
    checkAuth();
  }, [navigate]);

  const loadData = async () => {
    setLoading(true);
    // Load projects and modules in parallel
    try {
      const [projectsData, modulesData] = await Promise.all([getProjects(), getModules()]);
      if (projectsData) {
        setProjects(
          projectsData.map((p: any) => ({
            ...p,
            canvas_data: (p.canvas_data as unknown as CanvasData) || { modules: [], wires: [] },
          })) as Project[],
        );
      }
      if (modulesData) setModules(modulesData as Module[]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load data";
      toast({ variant: "destructive", title: "Error", description: message });
    }
    setLoading(false);
  };

  const createProject = async () => {
    try {
      const data = await apiCreateProject();
      if (data && data[0]) {
        navigate(`/canvas/${data[0].id}`);
      } else if (data && data.id) {
        navigate(`/canvas/${data.id}`);
      } else {
        toast({ variant: "destructive", title: "Error", description: "Could not create project" });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create project";
      toast({ variant: "destructive", title: "Error", description: message });
    }
  };

  const deleteProject = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiDeleteProject(id);
      setProjects(prev => prev.filter(p => p.id !== id));
      toast({ title: "Project deleted" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete project";
      toast({ variant: "destructive", title: "Error", description: message });
    }
  };

  const filteredModules = modules.filter(m =>
    m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (m.category && m.category.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container pt-20 pb-12 px-4">
        {/* Projects Section */}
        <div className="mb-12">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-foreground">My Projects</h2>
            <div className="flex items-center gap-2">
              <Button onClick={createProject}>
                <Plus className="h-4 w-4 mr-2" />
                New Project
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-32 rounded-xl bg-muted animate-pulse" />
              ))}
            </div>
          ) : projects.length === 0 ? (
            <Card className="border-dashed bg-card/50 cursor-pointer hover:border-primary/40 transition-colors" onClick={createProject}>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Plus className="h-10 w-10 text-muted-foreground mb-3" />
                <p className="text-muted-foreground">Create your first project</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map(project => (
                <Card
                  key={project.id}
                  className="cursor-pointer bg-card hover:border-primary/40 transition-all hover:glow-cyan group"
                  onClick={() => navigate(`/canvas/${project.id}`)}
                >
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base text-card-foreground truncate">{project.name}</CardTitle>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="opacity-0 group-hover:opacity-100 h-8 w-8 text-muted-foreground hover:text-destructive"
                        onClick={(e) => deleteProject(project.id, e)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Cpu className="h-3 w-3" />
                        {project.canvas_data?.modules?.length || 0} modules
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(project.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Module Gallery */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-foreground">Module Gallery</h2>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search modules..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {filteredModules.length === 0 ? (
            <Card className="bg-card/50">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Cpu className="h-10 w-10 text-muted-foreground mb-3" />
                <p className="text-muted-foreground">
                  {modules.length === 0 ? "No modules available yet. Ask an admin to add some!" : "No modules match your search."}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {filteredModules.map(mod => (
                <Card key={mod.id} className="bg-card hover:border-primary/30 transition-all group overflow-hidden">
                  <div className="aspect-square bg-muted/50 flex items-center justify-center overflow-hidden">
                    {mod.image_url ? (
                      <img src={mod.image_url} alt={mod.name} className="w-full h-full object-contain p-3" />
                    ) : (
                      <Cpu className="h-12 w-12 text-muted-foreground" />
                    )}
                  </div>
                  <CardContent className="p-3">
                    <p className="text-sm font-medium text-card-foreground truncate">{mod.name}</p>
                    {mod.category && (
                      <p className="text-xs text-muted-foreground font-mono mt-1">{mod.category}</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

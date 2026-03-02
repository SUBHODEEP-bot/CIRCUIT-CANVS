import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import Navbar from "@/components/layout/Navbar";
import { Plus, Trash2, Upload, Cpu, X, Save, Wand2 } from "lucide-react";
import type { Module, ModulePin, PinType } from "@/lib/circuit-types";
import { PIN_TYPES, PIN_TYPE_COLORS } from "@/lib/circuit-types";
import {
  getSession,
  getModules,
  getModulePins,
  adminCreateModule,
  adminUpdateModule,
  adminDeleteModule,
  adminCreatePins,
  adminDeletePin,
  uploadModuleImage,
  adminAnalyzeModuleImage,
} from "@/lib/api";

/**
 * Admin page for managing modules and placing pins on module images
 * Only accessible to users with admin role
 */
export default function AdminPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const imageRef = useRef<HTMLDivElement>(null);

  // Module list
  const [modules, setModules] = useState<Module[]>([]);
  const [loading, setLoading] = useState(true);

  // Module editor state
  const [editingModule, setEditingModule] = useState<Module | null>(null);
  const [moduleName, setModuleName] = useState("");
  const [moduleCategory, setModuleCategory] = useState("");
  const [moduleDescription, setModuleDescription] = useState("");
  const [moduleImageUrl, setModuleImageUrl] = useState("");
  const [pins, setPins] = useState<ModulePin[]>([]);
  const [uploading, setUploading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);

  // Pin placement state
  const [newPinName, setNewPinName] = useState("");
  const [newPinType, setNewPinType] = useState<PinType>("Digital");
  const [placingPin, setPlacingPin] = useState(false);
  const [draggingPinId, setDraggingPinId] = useState<string | null>(null);

  useEffect(() => {
    checkAdminAccess();
  }, []);

  const checkAdminAccess = async () => {
    try {
      const session = await getSession();
      // Allow access if the session reports the admin role (this can be
      // supplied by the admin cookie even when no authenticated user exists).
      if (!session.roles.includes("admin")) {
        // No admin role present. If there's no user signed in, redirect to auth;
        // otherwise inform the user they need admin privileges.
        if (!session.user) {
          navigate("/auth");
          return;
        }
        toast({ variant: "destructive", title: "Access denied", description: "You need admin privileges." });
        navigate("/dashboard");
        return;
      }
      loadModules();
    } catch {
      toast({ variant: "destructive", title: "Access denied", description: "You need admin privileges." });
      navigate("/dashboard");
    }
  };

  const loadModules = async () => {
    setLoading(true);
    try {
      const data = await getModules();
      if (data) setModules(data as Module[]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load modules";
      toast({ variant: "destructive", title: "Error", description: message });
    }
    setLoading(false);
  };

  const loadModulePins = async (moduleId: string) => {
    try {
      const data = await getModulePins(moduleId);
      if (data) setPins(data as ModulePin[]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load pins";
      toast({ variant: "destructive", title: "Error", description: message });
    }
  };

  const startNewModule = () => {
    setEditingModule(null);
    setModuleName("");
    setModuleCategory("");
    setModuleDescription("");
    setModuleImageUrl("");
    setPins([]);
    setIsCreating(true);
  };

  const startEditModule = async (mod: Module) => {
    setEditingModule(mod);
    setModuleName(mod.name);
    setModuleCategory(mod.category || "");
    setModuleDescription(mod.description || "");
    setModuleImageUrl(mod.image_url || "");
    setIsCreating(true);
    await loadModulePins(mod.id);
  };

  const cancelEdit = () => {
    setIsCreating(false);
    setEditingModule(null);
    setPins([]);
    setPlacingPin(false);
  };

  // Upload module image to storage
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const { public_url } = await uploadModuleImage(file);
      setModuleImageUrl(public_url);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      toast({ variant: "destructive", title: "Upload failed", description: message });
    } finally {
      setUploading(false);
    }
  };

  // AI-assisted pin detection using Gemini via backend
  const handleAIMapping = async () => {
    if (!moduleImageUrl) {
      toast({ variant: "destructive", title: "Upload an image first" });
      return;
    }
    setAiLoading(true);
    try {
      const meta = await adminAnalyzeModuleImage(moduleImageUrl, moduleName || undefined);
      const source = meta.source as string | undefined;

      if (meta.module_name && !moduleName) {
        setModuleName(meta.module_name);
      }
      if (meta.category && !moduleCategory) {
        setModuleCategory(meta.category);
      }
      if (meta.real_dimensions && !moduleDescription) {
        const w = meta.real_dimensions.width_mm;
        const h = meta.real_dimensions.height_mm;
        if (w && h) {
          setModuleDescription(`~${w.toFixed(1)}mm × ${h.toFixed(1)}mm module (${source === "supabase" ? "from library" : "AI estimated"})`);
        }
      }

      if (Array.isArray(meta.pins)) {
        const mappedPins: ModulePin[] = meta.pins.map((p: any, index: number) => {
          const coords = p.x_y_coordinates || {};
          const x = typeof coords.x_percent === "number" ? coords.x_percent : 50;
          const y = typeof coords.y_percent === "number" ? coords.y_percent : 50;
          const rawType = (p.type || "").toString().toLowerCase();
          let pinType: PinType = "Digital";
          if (rawType.includes("power") || rawType === "vcc" || rawType === "vdd") pinType = "Power";
          else if (rawType.includes("ground") || rawType === "gnd") pinType = "Ground";
          else if (rawType.includes("analog")) pinType = "Analog";
          else if (rawType.includes("i2c") || rawType.includes("sda") || rawType.includes("scl")) pinType = "I2C";
          else if (rawType.includes("spi")) pinType = "SPI";

          return {
            id: `temp-ai-${index}-${crypto.randomUUID()}`,
            module_id: editingModule?.id || "temp",
            name: p.name || `Pin ${index + 1}`,
            pin_type: pinType,
            x,
            y,
            created_at: new Date().toISOString(),
          };
        });
        setPins(mappedPins);
        toast({
          title: source === "supabase" ? "Loaded from library" : "AI pins detected",
          description: source === "supabase"
            ? "Existing module definition loaded from Supabase."
            : "Review and fine‑tune the detected pins before saving.",
        });
      } else {
        toast({ variant: "destructive", title: "No pins returned from AI" });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "AI mapping failed";
      toast({ variant: "destructive", title: "AI mapping failed", description: message });
    } finally {
      setAiLoading(false);
    }
  };

  // Handle click on image to place a pin
  const handleImageClick = (e: React.MouseEvent) => {
    if (!placingPin || !imageRef.current) return;

    const rect = imageRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;

    const tempPin: ModulePin = {
      id: `temp-${crypto.randomUUID()}`,
      module_id: editingModule?.id || "temp",
      name: newPinName || `Pin ${pins.length + 1}`,
      pin_type: newPinType,
      x,
      y,
      created_at: new Date().toISOString(),
    };

    setPins(prev => [...prev, tempPin]);
    setNewPinName("");
    setPlacingPin(false);
  };

  // Drag existing pins to fine‑tune their position
  const handleImageMouseMove = (e: React.MouseEvent) => {
    if (!draggingPinId || !imageRef.current) return;
    const rect = imageRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    setPins(prev =>
      prev.map(p => (p.id === draggingPinId ? { ...p, x: Math.min(Math.max(x, 0), 100), y: Math.min(Math.max(y, 0), 100) } : p)),
    );
  };

  const stopDragging = () => setDraggingPinId(null);

  // Remove a pin
  const removePin = async (pinId: string) => {
    try {
      if (!pinId.startsWith("temp-")) {
        await adminDeletePin(pinId);
      }
      setPins(prev => prev.filter(p => p.id !== pinId));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to remove pin";
      toast({ variant: "destructive", title: "Error", description: message });
    }
  };

  // Save module
  const saveModule = async () => {
    if (!moduleName.trim()) {
      toast({ variant: "destructive", title: "Name required" });
      return;
    }

    try {
      if (editingModule) {
        // Update existing module
        await adminUpdateModule(editingModule.id, {
          name: moduleName,
          category: moduleCategory || null,
          description: moduleDescription || null,
          image_url: moduleImageUrl || null,
        });

        // Save new pins (temp ones)
        const newPins = pins.filter(p => p.id.startsWith("temp-"));
        if (newPins.length > 0) {
          await adminCreatePins(
            editingModule.id,
            newPins.map(p => ({
              name: p.name,
              pin_type: p.pin_type,
              x: p.x,
              y: p.y,
            })),
          );
        }
      } else {
        // Create new module
        const data = await adminCreateModule({
          name: moduleName,
          category: moduleCategory || null,
          description: moduleDescription || null,
          image_url: moduleImageUrl || null,
        });

        const moduleId = Array.isArray(data) && data[0] ? data[0].id : data?.id;
        if (!moduleId) {
          toast({ variant: "destructive", title: "Error", description: "Could not create module" });
          return;
        }

        // Save pins
        if (pins.length > 0) {
          await adminCreatePins(
            moduleId,
            pins.map(p => ({
              name: p.name,
              pin_type: p.pin_type,
              x: p.x,
              y: p.y,
            })),
          );
        }
      }

      toast({ title: "Module saved!" });
      cancelEdit();
      loadModules();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error saving module";
      toast({ variant: "destructive", title: "Error", description: message });
    }
  };

  // Delete module
  const deleteModule = async (id: string) => {
    try {
      await adminDeleteModule(id);
      setModules(prev => prev.filter(m => m.id !== id));
      toast({ title: "Module deleted" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete module";
      toast({ variant: "destructive", title: "Error", description: message });
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main className="container pt-20 pb-12 px-4 max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold text-foreground">Admin: Module Manager</h1>
          {!isCreating && (
            <Button onClick={startNewModule}>
              <Plus className="h-4 w-4 mr-2" />
              New Module
            </Button>
          )}
        </div>

        {isCreating ? (
          /* Module Editor */
          <Card className="bg-card border-border">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-card-foreground">
                  {editingModule ? `Edit: ${editingModule.name}` : "New Module"}
                </CardTitle>
                <Button variant="ghost" size="icon" onClick={cancelEdit}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Module info */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Module Name *</Label>
                  <Input value={moduleName} onChange={(e) => setModuleName(e.target.value)} placeholder="e.g., Arduino Uno" />
                </div>
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Input value={moduleCategory} onChange={(e) => setModuleCategory(e.target.value)} placeholder="e.g., Microcontroller" />
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Input value={moduleDescription} onChange={(e) => setModuleDescription(e.target.value)} placeholder="Short description" />
                </div>
              </div>

              {/* Image upload */}
              <div className="space-y-2">
                <Label>Module Image</Label>
                <div className="flex items-center gap-3 flex-wrap">
                  <label className="flex items-center gap-2 px-4 py-2 rounded-md border border-border bg-secondary text-secondary-foreground hover:bg-secondary/80 cursor-pointer text-sm transition-colors">
                    <Upload className="h-4 w-4" />
                    {uploading ? "Uploading..." : "Upload Image"}
                    <input type="file" accept="image/*" className="hidden" onChange={handleImageUpload} disabled={uploading} />
                  </label>
                  {moduleImageUrl && <span className="text-xs text-accent font-mono">✓ Image uploaded</span>}
                  {moduleImageUrl && (
                    <Button size="sm" variant="outline" disabled={aiLoading} onClick={handleAIMapping}>
                      <Wand2 className="h-3 w-3 mr-1" />
                      {aiLoading ? "Analyzing..." : "AI Detect Pins"}
                    </Button>
                  )}
                </div>
              </div>

              {/* Image with pin placement */}
              {moduleImageUrl && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label>Pin Placement (click on image to place pins)</Label>
                    {!placingPin ? (
                      <div className="flex items-center gap-2">
                        <Input
                          value={newPinName}
                          onChange={(e) => setNewPinName(e.target.value)}
                          placeholder="Pin name"
                          className="h-8 w-32 text-xs"
                        />
                        <Select value={newPinType} onValueChange={(v) => setNewPinType(v as PinType)}>
                          <SelectTrigger className="h-8 w-28 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {PIN_TYPES.map(t => (
                              <SelectItem key={t} value={t}>{t}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Button size="sm" variant="outline" onClick={() => setPlacingPin(true)}>
                          <Plus className="h-3 w-3 mr-1" /> Place Pin
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-primary animate-pulse">Click on the image to place "{newPinName || `Pin ${pins.length + 1}`}"</span>
                    )}
                  </div>

                  <div
                    ref={imageRef}
                    className={`relative border border-border rounded-lg overflow-hidden bg-muted/30 inline-block ${placingPin ? "cursor-crosshair" : "cursor-default"}`}
                    onClick={handleImageClick}
                    onMouseMove={handleImageMouseMove}
                    onMouseUp={stopDragging}
                    onMouseLeave={stopDragging}
                  >
                    <img src={moduleImageUrl} alt="Module" className="block max-w-full max-h-[500px]" draggable={false} />
                    {/* Render placed pins */}
                    {pins.map(pin => (
                      <div
                        key={pin.id}
                        className="absolute w-4 h-4 rounded-full border-2 cursor-pointer"
                        style={{
                          left: `${pin.x}%`,
                          top: `${pin.y}%`,
                          marginLeft: -8,
                          marginTop: -8,
                          backgroundColor: PIN_TYPE_COLORS[pin.pin_type],
                          borderColor: "#ffffff",
                        }}
                        title={`${pin.name} (${pin.pin_type})`}
                        onMouseDown={(e) => {
                          e.stopPropagation();
                          setDraggingPinId(pin.id);
                        }}
                      />
                    ))}
                  </div>

                  {/* Pin list */}
                  {pins.length > 0 && (
                    <div className="space-y-1">
                      <Label className="text-xs">Placed Pins ({pins.length})</Label>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-1">
                        {pins.map(pin => (
                          <div key={pin.id} className="flex items-center gap-2 rounded bg-muted px-2 py-1 text-xs">
                            <div
                              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                              style={{ backgroundColor: PIN_TYPE_COLORS[pin.pin_type] }}
                            />
                            <span className="text-card-foreground truncate font-mono">{pin.name}</span>
                            <span className="text-muted-foreground text-[10px]">{pin.pin_type}</span>
                            <button onClick={() => removePin(pin.id)} className="ml-auto text-muted-foreground hover:text-destructive">
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Save */}
              <div className="flex gap-2 pt-2">
                <Button onClick={saveModule}>
                  <Save className="h-4 w-4 mr-2" />
                  Save Module
                </Button>
                <Button variant="outline" onClick={cancelEdit}>Cancel</Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          /* Module list */
          <div className="space-y-3">
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map(i => <div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />)}
              </div>
            ) : modules.length === 0 ? (
              <Card className="bg-card/50 border-dashed">
                <CardContent className="flex flex-col items-center justify-center py-12">
                  <Cpu className="h-10 w-10 text-muted-foreground mb-3" />
                  <p className="text-muted-foreground">No modules yet. Create your first one!</p>
                </CardContent>
              </Card>
            ) : (
              modules.map(mod => (
                <Card
                  key={mod.id}
                  className="bg-card hover:border-primary/30 transition-colors cursor-pointer"
                  onClick={() => startEditModule(mod)}
                >
                  <CardContent className="flex items-center gap-4 py-3">
                    <div className="w-12 h-12 rounded bg-muted flex items-center justify-center overflow-hidden flex-shrink-0">
                      {mod.image_url ? (
                        <img src={mod.image_url} alt={mod.name} className="w-full h-full object-contain" />
                      ) : (
                        <Cpu className="h-6 w-6 text-muted-foreground" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-card-foreground">{mod.name}</p>
                      <p className="text-xs text-muted-foreground font-mono">
                        {mod.category || "Uncategorized"} · {mod.description || "No description"}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-muted-foreground hover:text-destructive flex-shrink-0"
                      onClick={(e) => { e.stopPropagation(); deleteModule(mod.id); }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}
      </main>
    </div>
  );
}

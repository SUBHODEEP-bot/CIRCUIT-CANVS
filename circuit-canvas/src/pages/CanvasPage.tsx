import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import ModuleSidebar from "@/components/circuit/ModuleSidebar";
import ModuleNode from "@/components/circuit/ModuleNode";
import WireLayer from "@/components/circuit/WireLayer";
import {
  Save, ZoomIn, ZoomOut, RotateCcw, Trash2, ArrowLeft, Pencil, X, FileDown,
} from "lucide-react";
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";
import type {
  Module, ModulePin, CanvasModuleInstance, CanvasWire, CanvasData, SelectedPin,
  WireWaypoint,
} from "@/lib/circuit-types";
import { WIRE_COLORS, MODULE_DISPLAY_WIDTH } from "@/lib/circuit-types";
import { getSession, getModules, getModulePins, getProject, updateProject } from "@/lib/api";

/**
 * Main circuit canvas page
 * Manages all canvas state: placed modules, wires, zoom/pan, drag, and pin connections
 */
export default function CanvasPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const canvasRef = useRef<HTMLDivElement>(null);

  // Data from DB
  const [modules, setModules] = useState<Module[]>([]);
  const [allPins, setAllPins] = useState<Record<string, ModulePin[]>>({});
  const [projectName, setProjectName] = useState("Untitled Project");
  const [editingName, setEditingName] = useState(false);
  const [userName, setUserName] = useState<string>("");

  // Canvas state
  const [placedModules, setPlacedModules] = useState<CanvasModuleInstance[]>([]);
  const [wires, setWires] = useState<CanvasWire[]>([]);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  // Interaction state
  const [selectedPin, setSelectedPin] = useState<SelectedPin | null>(null);
  const [selectedWireId, setSelectedWireId] = useState<string | null>(null);
  const [wireColor, setWireColor] = useState(WIRE_COLORS[0].value);
  const [wireWaypoints, setWireWaypoints] = useState<WireWaypoint[]>([]);
  const [dragTarget, setDragTarget] = useState<string | null>(null);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [moduleHeights, setModuleHeights] = useState<Record<string, number>>({});

  const handleModuleHeightReady = useCallback((moduleId: string, height: number) => {
    setModuleHeights(prev => {
      if (prev[moduleId] === height) return prev;
      return { ...prev, [moduleId]: height };
    });
  }, []);

  // Load project data and available modules
  useEffect(() => {
    const load = async () => {
      const session = await getSession();
      if (!session.user) {
        navigate("/auth");
        return;
      }
      
      // Set user name for PDF
      setUserName(session.user.display_name || session.user.email || "");

      try {
        // Load modules, pins, and project in parallel
        const [modulesData, pinsData, projectData] = await Promise.all([
          getModules(),
          getModulePins(),
          projectId ? getProject(projectId) : Promise.resolve(null),
        ]);

        if (modulesData) setModules(modulesData as Module[]);

        if (pinsData) {
          const pinMap: Record<string, ModulePin[]> = {};
          (pinsData as ModulePin[]).forEach(pin => {
            if (!pinMap[pin.module_id]) pinMap[pin.module_id] = [];
            pinMap[pin.module_id].push(pin);
          });
          setAllPins(pinMap);
        }

        if (projectData && Array.isArray(projectData) && projectData[0]) {
          const project = projectData[0];
          setProjectName(project.name);
          const canvasData = project.canvas_data as unknown as CanvasData;
          if (canvasData) {
            setPlacedModules(canvasData.modules || []);
            setWires(canvasData.wires || []);
          }
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load project";
        toast({ variant: "destructive", title: "Error", description: message });
      }
    };
    load();
  }, [projectId, navigate, toast]);

  // Add module to canvas at center
  const handleAddModule = useCallback((moduleId: string) => {
    const instanceId = crypto.randomUUID();
    const newModule: CanvasModuleInstance = {
      instanceId,
      moduleId,
      x: (-offset.x + 300) / scale,
      y: (-offset.y + 200) / scale,
    };
    setPlacedModules(prev => [...prev, newModule]);
  }, [offset, scale]);

  // Module drag handlers
  const handleModuleMouseDown = useCallback((instanceId: string, e: React.MouseEvent) => {
    e.preventDefault();
    setDragTarget(instanceId);
    setDragStart({ x: e.clientX, y: e.clientY });
  }, []);

  // Pin click handler for wire creation
  const handlePinClick = useCallback((instanceId: string, pinId: string) => {
    if (!selectedPin) {
      // First pin selected - start drawing wire
      setSelectedPin({ instanceId, pinId });
      setWireWaypoints([]);
      setSelectedWireId(null);
    } else if (selectedPin.instanceId === instanceId && selectedPin.pinId === pinId) {
      // Deselect same pin
      setSelectedPin(null);
      setWireWaypoints([]);
    } else {
      // Second pin clicked → create wire with waypoints
      const newWire: CanvasWire = {
        id: crypto.randomUUID(),
        fromInstanceId: selectedPin.instanceId,
        fromPinId: selectedPin.pinId,
        toInstanceId: instanceId,
        toPinId: pinId,
        color: wireColor,
        waypoints: wireWaypoints.length > 0 ? wireWaypoints : undefined,
      };
      setWires(prev => [...prev, newWire]);
      setSelectedPin(null);
      setWireWaypoints([]);
    }
  }, [selectedPin, wireColor, wireWaypoints]);

  // Wire selection/deletion
  const handleWireClick = useCallback((wireId: string) => {
    setSelectedWireId(prev => prev === wireId ? null : wireId);
    setSelectedPin(null);
  }, []);

  const deleteSelectedWire = useCallback(() => {
    if (selectedWireId) {
      setWires(prev => prev.filter(w => w.id !== selectedWireId));
      setSelectedWireId(null);
    }
  }, [selectedWireId]);

  // Waypoint drag handler
  const handleWaypointDrag = useCallback((wireId: string, waypointIndex: number, x: number, y: number) => {
    setWires(prev => prev.map(w => {
      if (w.id !== wireId || !w.waypoints) return w;
      const newWaypoints = [...w.waypoints];
      newWaypoints[waypointIndex] = { x, y };
      return { ...w, waypoints: newWaypoints };
    }));
  }, []);

  // Canvas mouse events for drag and pan
  const handleCanvasMouseMove = useCallback((e: React.MouseEvent) => {
    setMousePos({ x: (e.clientX - offset.x) / scale, y: (e.clientY - offset.y - 56) / scale });

    if (dragTarget) {
      const dx = (e.clientX - dragStart.x) / scale;
      const dy = (e.clientY - dragStart.y) / scale;
      setPlacedModules(prev =>
        prev.map(m =>
          m.instanceId === dragTarget ? { ...m, x: m.x + dx, y: m.y + dy } : m
        )
      );
      setDragStart({ x: e.clientX, y: e.clientY });
    }

    if (isPanning) {
      const dx = e.clientX - panStart.x;
      const dy = e.clientY - panStart.y;
      setOffset(prev => ({ x: prev.x + dx, y: prev.y + dy }));
      setPanStart({ x: e.clientX, y: e.clientY });
    }
  }, [dragTarget, dragStart, isPanning, panStart, scale, offset]);

  const handleCanvasMouseUp = useCallback(() => {
    setDragTarget(null);
    setIsPanning(false);
  }, []);

  const handleCanvasMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 1) {
      e.preventDefault();
      setIsPanning(true);
      setPanStart({ x: e.clientX, y: e.clientY });
    }
    // Left-click on canvas while drawing a wire → add waypoint
    if (e.button === 0 && selectedPin && !(e.target as HTMLElement).closest('.module-node') && !(e.target as HTMLElement).closest('.pin-zone')) {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (rect) {
        const x = (e.clientX - rect.left - offset.x) / scale;
        const y = (e.clientY - rect.top - offset.y) / scale;
        setWireWaypoints(prev => [...prev, { x, y }]);
      }
    }
  }, [selectedPin, offset, scale]);

  // Zoom with scroll wheel
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale(prev => Math.min(Math.max(prev * delta, 0.2), 3));
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelectedPin(null);
        setWireWaypoints([]);
        setSelectedWireId(null);
      }
      if (e.key === "Delete" && selectedWireId) {
        deleteSelectedWire();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selectedWireId, deleteSelectedWire]);

  // Save project
  const saveProject = async () => {
    if (!projectId) return;
    const canvasData: CanvasData = { modules: placedModules, wires };
    try {
      await updateProject(projectId, {
        name: projectName,
        canvas_data: JSON.parse(JSON.stringify(canvasData)),
      });
      toast({ title: "Project saved!" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Save failed";
      toast({ variant: "destructive", title: "Save failed", description: message });
    }
  };

  // Export to PDF in HD quality with professional formatting
  const exportToPDF = async () => {
    if (!canvasRef.current) {
      toast({ variant: "destructive", title: "Error", description: "Canvas not found" });
      return;
    }

    try {
      toast({ title: "Generating PDF...", description: "Creating professional circuit diagram document." });

      // Capture canvas
      const canvas = await html2canvas(canvasRef.current, {
        backgroundColor: "#0a0f1f",
        scale: 3, // 3x scale for HD quality
        logging: false,
        useCORS: true,
        allowTaint: true,
      });

      const imgData = canvas.toDataURL("image/png");
      
      // Create PDF with A4 size
      const pdf = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: "a4",
      });

      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 12;
      const contentWidth = pageWidth - margin * 2;

      // Title Page
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(28);
      pdf.text("Circuit Design Document", pageWidth / 2, 50, { align: "center" });

      pdf.setFontSize(14);
      pdf.setFont("helvetica", "normal");
      pdf.text(`Project: ${projectName}`, pageWidth / 2, 75, { align: "center" });
      
      pdf.setFontSize(11);
      pdf.setFont("helvetica", "italic");
      pdf.text(`Designed by ${userName}`, pageWidth / 2, 87, { align: "center" });
      
      pdf.setFont("helvetica", "normal");
      const now = new Date();
      const dateStr = now.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
      pdf.setFontSize(10);
      pdf.text(`Generated: ${dateStr}`, pageWidth / 2, 99, { align: "center" });
      
      const timeStr = now.toLocaleTimeString();
      pdf.text(`Time: ${timeStr}`, pageWidth / 2, 107, { align: "center" });

      // Add horizontal line
      pdf.setDrawColor(66, 133, 244);
      pdf.setLineWidth(0.5);
      pdf.line(margin, 118, pageWidth - margin, 118);

      // Circuit Details Section (simplified for A4)
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(11);
      pdf.text("Circuit Details", margin, 130);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(9);
      const moduleCount = placedModules.length;
      const wireCount = wires.length;
      
      pdf.text(`Modules: ${moduleCount} | Connections: ${wireCount}`, margin + 5, 140);
      
      let yPos = 150;
      placedModules.slice(0, 5).forEach((mod, idx) => {
        const moduleName = modules.find(m => m.id === mod.moduleId)?.name || "Unknown";
        pdf.text(`${idx + 1}. ${moduleName}`, margin + 10, yPos);
        yPos += 6;
      });

      // Add new page for circuit diagram
      pdf.addPage();
      
      // Header on new page
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(14);
      pdf.text("Circuit Diagram", margin, 15);
      
      // Add the circuit image
      const diagramY = 25;
      const availableHeight = pageHeight - diagramY - margin;
      const imgWidth = contentWidth;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      pdf.addImage(imgData, "PNG", margin, diagramY, imgWidth, Math.min(imgHeight, availableHeight));

      // Function to add footer to all pages
      const addFooters = () => {
        const totalPages = pdf.internal.pages.length - 1;
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(9);
        pdf.setTextColor(128, 128, 128);

        for (let i = 2; i <= totalPages; i++) {
          pdf.setPage(i);
          pdf.text(`Page ${i} of ${totalPages}`, pageWidth / 2, pageHeight - 8, { align: "center" });
          pdf.line(margin, pageHeight - 12, pageWidth - margin, pageHeight - 12);
        }
      };

      // Handle multi-page if circuit is large
      if (imgHeight > availableHeight) {
        let remainingHeight = imgHeight - availableHeight;
        let yOffset = availableHeight;

        while (remainingHeight > 0) {
          pdf.addPage();
          const currentHeight = Math.min(remainingHeight, pageHeight - margin * 2);
          pdf.addImage(
            imgData,
            "PNG",
            margin,
            margin,
            imgWidth,
            currentHeight,
            undefined,
            "FAST",
            yOffset
          );
          remainingHeight -= currentHeight;
          yOffset += currentHeight;
        }
      }

      addFooters();

      // Save the PDF
      const fileName = `${projectName || "Circuit"}_${now.toISOString().split("T")[0]}.pdf`;
      pdf.save(fileName);

      toast({ title: "Professional PDF exported!", description: `Saved as ${fileName}` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "PDF export failed";
      toast({ variant: "destructive", title: "Export failed", description: message });
      console.error("PDF export error:", err);
    }
  };

  // Get pending wire position for wire being drawn
  const getPendingWire = () => {
    if (!selectedPin) return null;
    const instance = placedModules.find(m => m.instanceId === selectedPin.instanceId);
    if (!instance) return null;
    const pins = allPins[instance.moduleId];
    if (!pins) return null;
    const pin = pins.find(p => p.id === selectedPin.pinId);
    if (!pin) return null;

    const height = moduleHeights[instance.moduleId] ?? MODULE_DISPLAY_WIDTH;

    return {
      fromX: instance.x + (pin.x / 100) * MODULE_DISPLAY_WIDTH,
      fromY: instance.y + (pin.y / 100) * height,
      toX: mousePos.x,
      toY: mousePos.y,
      color: wireColor,
      waypoints: wireWaypoints,
    };
  };

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      {/* Top toolbar */}
      <div className="h-14 border-b border-border bg-card flex items-center px-4 gap-3 z-20 flex-shrink-0">
        <Button variant="ghost" size="icon" onClick={() => navigate("/dashboard")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>

        {/* Project name */}
        <div className="flex items-center gap-1">
          {editingName ? (
            <div className="flex items-center gap-1">
              <Input
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="h-8 w-48 text-sm"
                autoFocus
                onBlur={() => setEditingName(false)}
                onKeyDown={(e) => e.key === "Enter" && setEditingName(false)}
              />
            </div>
          ) : (
            <button
              className="text-sm font-medium text-card-foreground hover:text-primary flex items-center gap-1"
              onClick={() => setEditingName(true)}
            >
              {projectName}
              <Pencil className="h-3 w-3 text-muted-foreground" />
            </button>
          )}
        </div>

        <div className="flex-1" />

        {/* Wire color picker */}
        <div className="flex items-center gap-1 border border-border rounded-md px-2 py-1">
          <span className="text-xs text-muted-foreground mr-1">Wire:</span>
          {WIRE_COLORS.map(c => (
            <button
              key={c.value}
              className="w-5 h-5 rounded-full border-2 transition-transform hover:scale-110"
              style={{
                backgroundColor: c.value,
                borderColor: wireColor === c.value ? '#ffffff' : 'transparent',
                transform: wireColor === c.value ? 'scale(1.2)' : undefined,
              }}
              title={c.name}
              onClick={() => setWireColor(c.value)}
            />
          ))}
        </div>

        {/* Delete selected wire */}
        {selectedWireId && (
          <Button variant="destructive" size="sm" onClick={deleteSelectedWire}>
            <Trash2 className="h-3 w-3 mr-1" />
            Delete Wire
          </Button>
        )}

        {/* Zoom controls */}
        <div className="flex items-center gap-1 border border-border rounded-md">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setScale(s => Math.min(s * 1.2, 3))}>
            <ZoomIn className="h-3 w-3" />
          </Button>
          <span className="text-xs text-muted-foreground w-12 text-center font-mono">
            {Math.round(scale * 100)}%
          </span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setScale(s => Math.max(s * 0.8, 0.2))}>
            <ZoomOut className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }); }}>
            <RotateCcw className="h-3 w-3" />
          </Button>
        </div>

        {/* Save */}
        <Button size="sm" onClick={saveProject}>
          <Save className="h-3 w-3 mr-1" />
          Save
        </Button>

        {/* Export to PDF */}
        <Button size="sm" onClick={exportToPDF} variant="outline">
          <FileDown className="h-3 w-3 mr-1" />
          PDF
        </Button>
      </div>

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Module sidebar */}
        <ModuleSidebar modules={modules} onAddModule={handleAddModule} />

        {/* Canvas area */}
        <div
          ref={canvasRef}
          className="flex-1 relative overflow-hidden circuit-grid cursor-crosshair"
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
          onMouseDown={handleCanvasMouseDown}
          onWheel={handleWheel}
          onContextMenu={(e) => e.preventDefault()}
        >
          {/* Selected pin indicator */}
          {selectedPin && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 bg-primary/10 border border-primary/30 rounded-full px-3 py-1 text-xs text-primary flex items-center gap-2">
              Click canvas to add waypoints, click a pin to finish
              <button onClick={() => { setSelectedPin(null); setWireWaypoints([]); }}>
                <X className="h-3 w-3" />
              </button>
            </div>
          )}

          {/* Transformed canvas content */}
          <div
            style={{
              transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
              transformOrigin: "0 0",
              width: "5000px",
              height: "5000px",
              position: "relative",
            }}
          >
            {/* Wire layer */}
            <WireLayer
              wires={wires}
              placedModules={placedModules}
              modulePinsMap={allPins}
              moduleHeights={moduleHeights}
              pendingWire={getPendingWire()}
              selectedWireId={selectedWireId}
              onWireClick={handleWireClick}
              onWaypointDrag={handleWaypointDrag}
              scale={scale}
              offset={offset}
              canvasRef={canvasRef}
            />

            {/* Module nodes */}
            {placedModules.map(instance => {
              const mod = modules.find(m => m.id === instance.moduleId);
              if (!mod) return null;
              return (
                <ModuleNode
                  key={instance.instanceId}
                  instance={instance}
                  module={mod}
                  pins={allPins[instance.moduleId] || []}
                  selectedPin={selectedPin}
                  scale={scale}
                  onMouseDown={handleModuleMouseDown}
                  onPinClick={handlePinClick}
                  onHeightReady={handleModuleHeightReady}
                />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

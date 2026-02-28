import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import ModuleSidebar from "@/components/circuit/ModuleSidebar";
import ModuleNode from "@/components/circuit/ModuleNode";
import WireLayer from "@/components/circuit/WireLayer";
import {
  Save, ZoomIn, ZoomOut, RotateCcw, Trash2, ArrowLeft, Pencil, X, FileDown, Cpu,
} from "lucide-react";
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";
import type {
  Module, ModulePin, CanvasModuleInstance, CanvasWire, CanvasData, SelectedPin,
  WireWaypoint,
} from "@/lib/circuit-types";
import { WIRE_COLORS, MODULE_DISPLAY_WIDTH } from "@/lib/circuit-types";
import { getSession, getModules, getModulePins, getProject, updateProject, generatePCB } from "@/lib/api";

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
      
      // Set user name for PDF - always have a fallback
      const name = session.user.display_name || session.user.email || "Designer";
      setUserName(name);

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

      // Temporarily hide the grid background for clean PDF
      const originalClass = canvasRef.current.className;
      canvasRef.current.classList.remove("circuit-grid");
      
      // Create a container div with white background to capture clean
      const tempContainer = document.createElement("div");
      tempContainer.style.position = "absolute";
      tempContainer.style.left = "-9999px";
      tempContainer.style.width = canvasRef.current.offsetWidth + "px";
      tempContainer.style.height = canvasRef.current.offsetHeight + "px";
      tempContainer.style.backgroundColor = "#ffffff";
      tempContainer.appendChild(canvasRef.current.cloneNode(true));
      document.body.appendChild(tempContainer);

      // Capture canvas WITHOUT grid background and with white background
      const canvas = await html2canvas(tempContainer, {
        backgroundColor: "#ffffff",
        scale: 4, // 4x scale for extra HD quality
        logging: false,
        useCORS: true,
        allowTaint: true,
      });

      // Clean up
      document.body.removeChild(tempContainer);
      canvasRef.current.className = originalClass;

      const imgData = canvas.toDataURL("image/png");
      
      // Create PDF with A4 size (landscape for better diagram visibility)
      const pdf = new jsPDF({
        orientation: "landscape",
        unit: "mm",
        format: "a4",
      });

      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 10;
      const contentWidth = pageWidth - margin * 2;

      // ==== TITLE PAGE ====
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(32);
      pdf.text("Circuit Design Document", pageWidth / 2, 45, { align: "center" });

      // Decorative line
      pdf.setDrawColor(41, 128, 185);
      pdf.setLineWidth(1);
      pdf.line(margin + 20, 55, pageWidth - margin - 20, 55);

      pdf.setFontSize(16);
      pdf.setFont("helvetica", "normal");
      pdf.setTextColor(50, 50, 50);
      pdf.text(`Project: ${projectName}`, pageWidth / 2, 75, { align: "center" });
      
      pdf.setFontSize(13);
      pdf.setFont("helvetica", "italic");
      pdf.setTextColor(80, 80, 80);
      const designedByText = userName && userName.trim() ? `Designed by ${userName}` : "Designed by Designer";
      pdf.text(designedByText, pageWidth / 2, 90, { align: "center" });
      
      pdf.setFont("helvetica", "normal");
      pdf.setTextColor(100, 100, 100);
      const now = new Date();
      const dateStr = now.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
      pdf.setFontSize(11);
      pdf.text(`Generated: ${dateStr}`, pageWidth / 2, 105, { align: "center" });
      
      const timeStr = now.toLocaleTimeString();
      pdf.text(`Time: ${timeStr}`, pageWidth / 2, 113, { align: "center" });

      // Circuit Details Section - Enhanced styling
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(12);
      pdf.setTextColor(30, 30, 30);
      pdf.text("Circuit Summary", margin + 10, 135);

      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(10);
      pdf.setTextColor(60, 60, 60);
      const moduleCount = placedModules.length;
      const wireCount = wires.length;
      
      pdf.text(`Total Modules: ${moduleCount}`, margin + 15, 148);
      pdf.text(`Total Connections: ${wireCount}`, margin + 15, 158);

      // Component list
      if (placedModules.length > 0) {
        pdf.setFont("helvetica", "bold");
        pdf.setFontSize(10);
        pdf.text("Components Used:", margin + 15, 172);

        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(9);
        let yPos = 182;
        placedModules.slice(0, 8).forEach((mod, idx) => {
          const moduleName = modules.find(m => m.id === mod.moduleId)?.name || "Unknown";
          pdf.text(`${idx + 1}. ${moduleName}`, margin + 20, yPos);
          yPos += 7;
          if (yPos > pageHeight - 15) return;
        });
      }

      // ==== CIRCUIT DIAGRAM PAGE ====
      pdf.addPage();
      
      // Page header
      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(16);
      pdf.setTextColor(30, 30, 30);
      pdf.text("Circuit Diagram", margin, 15);
      
      // Decorative line
      pdf.setDrawColor(41, 128, 185);
      pdf.setLineWidth(0.5);
      pdf.line(margin, 20, pageWidth - margin, 20);

      // Add the circuit image with better sizing
      const diagramStartY = 28;
      const availableHeight = pageHeight - diagramStartY - margin;
      const imgWidth = contentWidth;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      // Add white background box for diagram
      pdf.setFillColor(255, 255, 255);
      pdf.rect(margin - 2, diagramStartY - 2, contentWidth + 4, Math.min(imgHeight, availableHeight) + 4, "F");
      
      // Add border around diagram
      pdf.setDrawColor(200, 200, 200);
      pdf.setLineWidth(0.3);
      pdf.rect(margin - 2, diagramStartY - 2, contentWidth + 4, Math.min(imgHeight, availableHeight) + 4);

      pdf.addImage(imgData, "PNG", margin, diagramStartY, imgWidth, Math.min(imgHeight, availableHeight));

      // Function to add footer to all pages
      const addFooters = () => {
        const totalPages = pdf.internal.pages.length - 1;
        pdf.setFont("helvetica", "normal");
        pdf.setFontSize(8);
        pdf.setTextColor(128, 128, 128);

        for (let i = 1; i <= totalPages; i++) {
          pdf.setPage(i);
          pdf.line(margin, pageHeight - 8, pageWidth - margin, pageHeight - 8);
          pdf.text(`Page ${i} of ${totalPages}`, pageWidth / 2, pageHeight - 4, { align: "center" });
          pdf.text("CircuitForge Lab", margin, pageHeight - 4);
        }
      };

      // Handle multi-page if circuit is large
      if (imgHeight > availableHeight) {
        let remainingHeight = imgHeight - availableHeight;
        let yOffset = availableHeight;

        while (remainingHeight > 0) {
          pdf.addPage();
          pdf.setFont("helvetica", "bold");
          pdf.setFontSize(12);
          pdf.setTextColor(30, 30, 30);
          pdf.text("Circuit Diagram (continued)", margin, 15);
          
          const currentHeight = Math.min(remainingHeight, pageHeight - margin * 3);
          
          // Add white background box
          pdf.setFillColor(255, 255, 255);
          pdf.rect(margin - 2, 22, contentWidth + 4, currentHeight + 4, "F");
          
          // Add border
          pdf.setDrawColor(200, 200, 200);
          pdf.setLineWidth(0.3);
          pdf.rect(margin - 2, 22, contentWidth + 4, currentHeight + 4);
          
          pdf.addImage(
            imgData,
            "PNG",
            margin,
            24,
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

      toast({ title: "✓ Professional PDF Exported!", description: `Successfully saved as ${fileName}` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "PDF export failed";
      toast({ variant: "destructive", title: "Export failed", description: message });
      console.error("PDF export error:", err);
    }
  };

  const handleGeneratePCB = async () => {
    if (placedModules.length === 0) {
      toast({ variant: "destructive", title: "No components", description: "Place some modules on the canvas first." });
      return;
    }

    toast({ title: "Generating PCB...", description: "Building netlist, placing components, routing traces." });

    const schematicModules = placedModules.map((inst) => {
      const mod = modules.find((m) => m.id === inst.moduleId);
      const pins = allPins[inst.moduleId] || [];
      return {
        instanceId: inst.instanceId,
        moduleId: inst.moduleId,
        moduleName: mod?.name || "Unknown",
        category: mod?.category || null,
        x: inst.x,
        y: inst.y,
        pins: pins.map((p) => ({
          id: p.id,
          name: p.name,
          pin_type: p.pin_type,
        })),
      };
    });

    const schematic = {
      modules: schematicModules,
      wires: wires.map((w) => ({
        fromInstanceId: w.fromInstanceId,
        fromPinId: w.fromPinId,
        toInstanceId: w.toInstanceId,
        toPinId: w.toPinId,
        color: w.color,
      })),
    };

    try {
      const pcbLayout = await generatePCB(schematic);
      navigate("/pcb", { state: { pcb: pcbLayout } });
    } catch (err) {
      const message = err instanceof Error ? err.message : "PCB generation failed";
      toast({ variant: "destructive", title: "PCB generation failed", description: message });
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

        {/* Generate PCB */}
        <Button size="sm" onClick={handleGeneratePCB} variant="outline" className="border-primary/50 text-primary hover:bg-primary/10">
          <Cpu className="h-3 w-3 mr-1" />
          Generate PCB
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

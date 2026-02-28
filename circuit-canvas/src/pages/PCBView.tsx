import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";

interface PadData {
  name: string;
  x: number;
  y: number;
  diameter: number;
}

interface PCBComponent {
  instanceId: string;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  pads: PadData[];
}

interface TracePoint {
  x: number;
  y: number;
}

interface PCBTrace {
  netName: string;
  width: number;
  points: TracePoint[];
}

interface PCBLayout {
  board: { width: number; height: number };
  components: PCBComponent[];
  traces: PCBTrace[];
  nets: { name: string; pinCount: number }[];
  layer: string;
}

const SCALE_FACTOR = 4;

const TRACE_COLORS = [
  "#ef4444", "#22c55e", "#3b82f6", "#eab308",
  "#f97316", "#a855f7", "#06b6d4", "#ec4899",
];

export default function PCBView() {
  const navigate = useNavigate();
  const location = useLocation();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [pcb, setPcb] = useState<PCBLayout | null>(null);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 40, y: 40 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const state = location.state as { pcb?: PCBLayout } | null;
    if (state?.pcb) {
      setPcb(state.pcb);
    }
  }, [location.state]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !pcb) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, rect.width, rect.height);

    ctx.save();
    ctx.translate(offset.x, offset.y);
    ctx.scale(scale, scale);

    const sf = SCALE_FACTOR;

    // Board outline
    ctx.fillStyle = "#1a5c2a";
    ctx.fillRect(0, 0, pcb.board.width * sf, pcb.board.height * sf);
    ctx.strokeStyle = "#fbbf24";
    ctx.lineWidth = 2 / scale;
    ctx.strokeRect(0, 0, pcb.board.width * sf, pcb.board.height * sf);

    // Copper traces
    pcb.traces.forEach((trace, idx) => {
      if (trace.points.length < 2) return;
      ctx.beginPath();
      ctx.strokeStyle = TRACE_COLORS[idx % TRACE_COLORS.length];
      ctx.lineWidth = Math.max(trace.width * sf, 1.5 / scale);
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.moveTo(trace.points[0].x * sf, trace.points[0].y * sf);
      for (let i = 1; i < trace.points.length; i++) {
        ctx.lineTo(trace.points[i].x * sf, trace.points[i].y * sf);
      }
      ctx.stroke();
    });

    // Components
    pcb.components.forEach((comp) => {
      // Component body
      ctx.fillStyle = "#0f172a";
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 1.5 / scale;
      ctx.fillRect(comp.x * sf, comp.y * sf, comp.width * sf, comp.height * sf);
      ctx.strokeRect(comp.x * sf, comp.y * sf, comp.width * sf, comp.height * sf);

      // Component label
      const fontSize = Math.max(8, Math.min(12, comp.width * sf * 0.15));
      ctx.fillStyle = "#e2e8f0";
      ctx.font = `bold ${fontSize / scale > 4 ? fontSize : 4 * scale}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(
        comp.name,
        (comp.x + comp.width / 2) * sf,
        (comp.y + comp.height / 2) * sf,
      );

      // Pads
      comp.pads.forEach((pad) => {
        const r = (pad.diameter * sf) / 2;
        ctx.beginPath();
        ctx.arc(pad.x * sf, pad.y * sf, Math.max(r, 2 / scale), 0, Math.PI * 2);
        ctx.fillStyle = "#fbbf24";
        ctx.fill();
        ctx.strokeStyle = "#78350f";
        ctx.lineWidth = 0.5 / scale;
        ctx.stroke();
      });
    });

    ctx.restore();
  }, [pcb, scale, offset]);

  useEffect(() => {
    draw();
  }, [draw]);

  useEffect(() => {
    const handleResize = () => draw();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [draw]);

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      setScale((s) => Math.min(Math.max(s * delta, 0.2), 8));
    },
    [],
  );

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0 || e.button === 1) {
      setIsPanning(true);
      setPanStart({ x: e.clientX, y: e.clientY });
    }
  }, []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isPanning) return;
      setOffset((prev) => ({
        x: prev.x + (e.clientX - panStart.x),
        y: prev.y + (e.clientY - panStart.y),
      }));
      setPanStart({ x: e.clientX, y: e.clientY });
    },
    [isPanning, panStart],
  );

  const handleMouseUp = useCallback(() => setIsPanning(false), []);

  if (!pcb) {
    return (
      <div className="h-screen flex items-center justify-center bg-background text-foreground">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">No PCB data. Generate a PCB from your circuit first.</p>
          <Button onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Go Back
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      {/* Toolbar */}
      <div className="h-14 border-b border-border bg-card flex items-center px-4 gap-3 z-20 flex-shrink-0">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <span className="text-sm font-semibold text-card-foreground">PCB Layout</span>
        <span className="text-xs text-muted-foreground">
          Board: {pcb.board.width.toFixed(1)} x {pcb.board.height.toFixed(1)} mm
          &nbsp;|&nbsp; Components: {pcb.components.length}
          &nbsp;|&nbsp; Nets: {pcb.nets.length}
          &nbsp;|&nbsp; Traces: {pcb.traces.length}
        </span>

        <div className="flex-1" />

        {/* Zoom controls */}
        <div className="flex items-center gap-1 border border-border rounded-md">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setScale((s) => Math.min(s * 1.2, 8))}>
            <ZoomIn className="h-3 w-3" />
          </Button>
          <span className="text-xs text-muted-foreground w-12 text-center font-mono">
            {Math.round(scale * 100)}%
          </span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setScale((s) => Math.max(s * 0.8, 0.2))}>
            <ZoomOut className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => { setScale(1); setOffset({ x: 40, y: 40 }); }}>
            <RotateCcw className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* PCB Canvas */}
      <div
        ref={containerRef}
        className="flex-1 bg-neutral-900 cursor-grab active:cursor-grabbing"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <canvas
          ref={canvasRef}
          className="w-full h-full"
        />
      </div>

      {/* Info panel */}
      <div className="h-10 border-t border-border bg-card flex items-center px-4 text-xs text-muted-foreground gap-4">
        <span>Layer: {pcb.layer} (copper)</span>
        {pcb.nets.map((net, i) => (
          <span key={net.name} className="flex items-center gap-1">
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ backgroundColor: TRACE_COLORS[i % TRACE_COLORS.length] }}
            />
            {net.name} ({net.pinCount} pins)
          </span>
        ))}
      </div>
    </div>
  );
}

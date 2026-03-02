import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, ZoomIn, ZoomOut, RotateCcw, Eye, EyeOff, AlertTriangle,
} from "lucide-react";

// ── Data types matching the backend JSON ────────────────────────

interface PadData {
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  shape: "circle" | "rect" | "oblong";
  drill: number;
  net: string;
}

interface SilkLine {
  x1: number; y1: number;
  x2: number; y2: number;
}

interface PCBComponent {
  instanceId: string;
  name: string;
  x: number; y: number;
  width: number; height: number;
  pads: PadData[];
  silkscreen: SilkLine[];
}

interface TracePoint { x: number; y: number; }

interface PCBTrace {
  netName: string;
  width: number;
  points: TracePoint[];
}

interface NetInfo {
  name: string;
  pinCount: number;
  isGround: boolean;
  isPower: boolean;
}

interface DRCItem {
  kind: string;
  net: string;
  x: number; y: number;
  detail: string;
}

interface PadExclusion { kind: string; cx: number; cy: number; radius: number; }
interface TraceExclusion { points: TracePoint[]; clearance: number; }
interface Thermal {
  cx: number; cy: number;
  outerRadius: number; innerRadius: number;
  spokeWidth: number; spokeCount: number;
}

interface CopperPour {
  net: string;
  clearance: number;
  padExclusions: PadExclusion[];
  traceExclusions: TraceExclusion[];
  thermals: Thermal[];
}

interface PCBUnits {
  coordinate: string;
  pxPerMm: number;
  traceWidthDefault: number;
  silkscreenWidth: number;
}

interface PCBLayout {
  board: { width: number; height: number };
  units: PCBUnits;
  components: PCBComponent[];
  traces: PCBTrace[];
  nets: NetInfo[];
  drc: DRCItem[];
  copperPour: CopperPour | null;
  layer: string;
}

// ── Colour palette ──────────────────────────────────────────────

const BOARD_COLOR = "#1a5c2a";
const BOARD_EDGE  = "#c8a92c";
const COPPER_FILL = "rgba(180,120,50,0.25)";
const SILK_COLOR  = "#e2e8f0";
const PAD_TH      = "#fbbf24";
const PAD_SMD     = "#e8b030";
const PAD_STROKE  = "#78350f";
const DRILL_COLOR = "#1e293b";
const DRC_COLOR   = "#ef4444";

const NET_COLORS: Record<string, string> = {
  GND: "#ef4444",
  VCC: "#22c55e",
};
const SIGNAL_COLORS = [
  "#3b82f6", "#eab308", "#f97316", "#a855f7",
  "#06b6d4", "#ec4899", "#14b8a6", "#f43f5e",
];

function netColor(name: string, idx: number): string {
  if (NET_COLORS[name]) return NET_COLORS[name];
  return SIGNAL_COLORS[idx % SIGNAL_COLORS.length];
}

// ── Component ───────────────────────────────────────────────────

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

  // Layer visibility
  const [showCopper, setShowCopper]     = useState(true);
  const [showSilk, setShowSilk]         = useState(true);
  const [showPour, setShowPour]         = useState(true);
  const [showDRC, setShowDRC]           = useState(true);
  const [showPadLabels, setShowPadLabels] = useState(true);

  useEffect(() => {
    const state = location.state as { pcb?: PCBLayout } | null;
    if (state?.pcb) setPcb(state.pcb);
  }, [location.state]);

  // ── Drawing ───────────────────────────────────────────────────

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !pcb) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width  = rect.width  * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, rect.width, rect.height);

    ctx.save();
    ctx.translate(offset.x, offset.y);
    ctx.scale(scale, scale);

    const sf = pcb.units.pxPerMm;

    // ── Board substrate ─────────────────────────────────────────
    ctx.fillStyle = BOARD_COLOR;
    ctx.fillRect(0, 0, pcb.board.width * sf, pcb.board.height * sf);
    ctx.strokeStyle = BOARD_EDGE;
    ctx.lineWidth = 2 / scale;
    ctx.strokeRect(0, 0, pcb.board.width * sf, pcb.board.height * sf);

    // ── Copper pour (GND plane) ─────────────────────────────────
    if (showPour && pcb.copperPour) {
      const pour = pcb.copperPour;

      // Draw the full fill
      ctx.fillStyle = COPPER_FILL;
      ctx.fillRect(0, 0, pcb.board.width * sf, pcb.board.height * sf);

      // Cut out pad exclusions
      ctx.save();
      ctx.globalCompositeOperation = "destination-out";

      for (const ex of pour.padExclusions) {
        ctx.beginPath();
        ctx.arc(ex.cx * sf, ex.cy * sf, ex.radius * sf, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0,0,0,1)";
        ctx.fill();
      }

      // Cut out trace exclusions
      for (const te of pour.traceExclusions) {
        if (te.points.length < 2) continue;
        ctx.beginPath();
        ctx.lineWidth = te.clearance * 2 * sf;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.strokeStyle = "rgba(0,0,0,1)";
        ctx.moveTo(te.points[0].x * sf, te.points[0].y * sf);
        for (let i = 1; i < te.points.length; i++) {
          ctx.lineTo(te.points[i].x * sf, te.points[i].y * sf);
        }
        ctx.stroke();
      }

      ctx.restore();

      // Thermal relief spokes
      ctx.strokeStyle = "rgba(180,120,50,0.5)";
      for (const th of pour.thermals) {
        const cx = th.cx * sf;
        const cy = th.cy * sf;
        const inner = th.innerRadius * sf;
        const outer = th.outerRadius * sf;
        ctx.lineWidth = th.spokeWidth * sf;
        for (let s = 0; s < th.spokeCount; s++) {
          const angle = (s * Math.PI * 2) / th.spokeCount;
          ctx.beginPath();
          ctx.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
          ctx.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer);
          ctx.stroke();
        }
      }
    }

    // ── Copper traces (45°) ─────────────────────────────────────
    if (showCopper) {
      let sigIdx = 0;
      for (const trace of pcb.traces) {
        if (trace.points.length < 2) continue;
        ctx.beginPath();
        ctx.strokeStyle = netColor(trace.netName, sigIdx);
        ctx.lineWidth = Math.max(trace.width * sf, 1 / scale);
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.moveTo(trace.points[0].x * sf, trace.points[0].y * sf);
        for (let i = 1; i < trace.points.length; i++) {
          ctx.lineTo(trace.points[i].x * sf, trace.points[i].y * sf);
        }
        ctx.stroke();
        if (!NET_COLORS[trace.netName]) sigIdx++;
      }
    }

    // ── Components ──────────────────────────────────────────────
    for (const comp of pcb.components) {
      // Silkscreen outline
      if (showSilk) {
        ctx.strokeStyle = SILK_COLOR;
        ctx.lineWidth = Math.max(pcb.units.silkscreenWidth * sf, 0.8 / scale);
        for (const sl of comp.silkscreen) {
          ctx.beginPath();
          ctx.moveTo(sl.x1 * sf, sl.y1 * sf);
          ctx.lineTo(sl.x2 * sf, sl.y2 * sf);
          ctx.stroke();
        }

        // Component reference label
        const fontSize = Math.max(6, Math.min(10, comp.width * sf * 0.12));
        ctx.fillStyle = SILK_COLOR;
        ctx.font = `bold ${fontSize}px 'JetBrains Mono', monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(
          comp.name,
          (comp.x + comp.width / 2) * sf,
          (comp.y + comp.height / 2) * sf,
        );
      }

      // Pads
      for (const pad of comp.pads) {
        const px = pad.x * sf;
        const py = pad.y * sf;

        if (pad.shape === "rect") {
          const pw = pad.width * sf;
          const ph = pad.height * sf;
          ctx.fillStyle = PAD_SMD;
          ctx.fillRect(px - pw / 2, py - ph / 2, pw, ph);
          ctx.strokeStyle = PAD_STROKE;
          ctx.lineWidth = 0.5 / scale;
          ctx.strokeRect(px - pw / 2, py - ph / 2, pw, ph);
        } else {
          const r = (pad.width * sf) / 2;
          ctx.beginPath();
          ctx.arc(px, py, Math.max(r, 1.5 / scale), 0, Math.PI * 2);
          ctx.fillStyle = PAD_TH;
          ctx.fill();
          ctx.strokeStyle = PAD_STROKE;
          ctx.lineWidth = 0.5 / scale;
          ctx.stroke();
        }

        // Drill hole
        if (pad.drill > 0) {
          const dr = (pad.drill * sf) / 2;
          ctx.beginPath();
          ctx.arc(px, py, Math.max(dr, 0.8 / scale), 0, Math.PI * 2);
          ctx.fillStyle = DRILL_COLOR;
          ctx.fill();
        }

        // Pad name label
        if (showPadLabels && scale > 1.5) {
          const lbl = pad.name;
          const lblSize = Math.max(4, Math.min(7, pad.width * sf * 0.5));
          ctx.fillStyle = "#1e293b";
          ctx.font = `${lblSize}px sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(lbl, px, py);
        }
      }
    }

    // ── DRC violation markers ───────────────────────────────────
    if (showDRC && pcb.drc.length > 0) {
      ctx.strokeStyle = DRC_COLOR;
      ctx.lineWidth = 1.5 / scale;
      const markerR = 3 / scale;
      for (const v of pcb.drc) {
        const vx = v.x * sf;
        const vy = v.y * sf;
        ctx.beginPath();
        ctx.arc(vx, vy, markerR, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(vx - markerR, vy - markerR);
        ctx.lineTo(vx + markerR, vy + markerR);
        ctx.moveTo(vx + markerR, vy - markerR);
        ctx.lineTo(vx - markerR, vy + markerR);
        ctx.stroke();
      }
    }

    // ── Scale ruler (bottom-left) ───────────────────────────────
    const rulerLen = 10 * sf;
    const rx = 10 / scale;
    const ry = (pcb.board.height * sf) + 15 / scale;
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 1.5 / scale;
    ctx.beginPath();
    ctx.moveTo(rx, ry);
    ctx.lineTo(rx + rulerLen, ry);
    ctx.moveTo(rx, ry - 3 / scale);
    ctx.lineTo(rx, ry + 3 / scale);
    ctx.moveTo(rx + rulerLen, ry - 3 / scale);
    ctx.lineTo(rx + rulerLen, ry + 3 / scale);
    ctx.stroke();
    ctx.fillStyle = "#94a3b8";
    ctx.font = `${9 / scale}px sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText("10 mm", rx + rulerLen / 2, ry + 12 / scale);

    ctx.restore();
  }, [pcb, scale, offset, showCopper, showSilk, showPour, showDRC, showPadLabels]);

  useEffect(() => { draw(); }, [draw]);

  useEffect(() => {
    const fn = () => draw();
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, [draw]);

  // ── Pan & zoom ────────────────────────────────────────────────

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setScale((s) => Math.min(Math.max(s * (e.deltaY > 0 ? 0.9 : 1.1), 0.2), 12));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0 || e.button === 1) {
      setIsPanning(true);
      setPanStart({ x: e.clientX, y: e.clientY });
    }
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return;
    setOffset((p) => ({
      x: p.x + e.clientX - panStart.x,
      y: p.y + e.clientY - panStart.y,
    }));
    setPanStart({ x: e.clientX, y: e.clientY });
  }, [isPanning, panStart]);

  const handleMouseUp = useCallback(() => setIsPanning(false), []);

  // ── Empty state ───────────────────────────────────────────────

  if (!pcb) {
    return (
      <div className="h-screen flex items-center justify-center bg-background text-foreground">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">No PCB data. Generate a PCB from your circuit first.</p>
          <Button onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4 mr-2" /> Go Back
          </Button>
        </div>
      </div>
    );
  }

  // ── Layer toggle button ───────────────────────────────────────

  const LayerBtn = ({ label, on, toggle }: { label: string; on: boolean; toggle: () => void }) => (
    <button
      onClick={toggle}
      className={`flex items-center gap-1 text-xs px-2 py-1 rounded border transition-colors ${
        on
          ? "border-primary/50 bg-primary/10 text-primary"
          : "border-border bg-card text-muted-foreground"
      }`}
    >
      {on ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
      {label}
    </button>
  );

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      {/* ── Toolbar ──────────────────────────────────────────── */}
      <div className="h-14 border-b border-border bg-card flex items-center px-4 gap-3 z-20 flex-shrink-0">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>

        <span className="text-sm font-semibold text-card-foreground">PCB Layout</span>
        <span className="text-xs text-muted-foreground hidden sm:inline">
          {pcb.board.width} x {pcb.board.height} mm
          &nbsp;|&nbsp; {pcb.components.length} components
          &nbsp;|&nbsp; {pcb.nets.length} nets
          &nbsp;|&nbsp; {pcb.traces.length} traces
        </span>

        {pcb.drc.length > 0 && (
          <span className="text-xs text-destructive flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            {pcb.drc.length} DRC
          </span>
        )}

        <div className="flex-1" />

        {/* Layer toggles */}
        <div className="flex items-center gap-1">
          <LayerBtn label="Copper"     on={showCopper}    toggle={() => setShowCopper(!showCopper)} />
          <LayerBtn label="Silk"       on={showSilk}      toggle={() => setShowSilk(!showSilk)} />
          <LayerBtn label="GND Pour"   on={showPour}      toggle={() => setShowPour(!showPour)} />
          <LayerBtn label="DRC"        on={showDRC}       toggle={() => setShowDRC(!showDRC)} />
          <LayerBtn label="Pad Names"  on={showPadLabels} toggle={() => setShowPadLabels(!showPadLabels)} />
        </div>

        {/* Zoom */}
        <div className="flex items-center gap-1 border border-border rounded-md">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setScale((s) => Math.min(s * 1.2, 12))}>
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

      {/* ── Canvas ───────────────────────────────────────────── */}
      <div
        ref={containerRef}
        className="flex-1 bg-neutral-900 cursor-grab active:cursor-grabbing"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <canvas ref={canvasRef} className="w-full h-full" />
      </div>

      {/* ── Info bar ─────────────────────────────────────────── */}
      <div className="h-10 border-t border-border bg-card flex items-center px-4 text-xs text-muted-foreground gap-4 overflow-x-auto">
        <span className="shrink-0">Layer: {pcb.layer}</span>
        <span className="shrink-0">Units: {pcb.units.coordinate}</span>
        {pcb.nets.map((net, i) => (
          <span key={net.name} className="flex items-center gap-1 shrink-0">
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ backgroundColor: netColor(net.name, i) }}
            />
            {net.name}
            {net.isGround && " (GND)"}
            {net.isPower && " (PWR)"}
            &nbsp;({net.pinCount})
          </span>
        ))}
      </div>
    </div>
  );
}

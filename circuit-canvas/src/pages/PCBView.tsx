import { useEffect, useState, useRef, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, ZoomIn, ZoomOut, RotateCcw, Eye, EyeOff, AlertTriangle,
} from "lucide-react";

// ── Types mirroring backend JSON ────────────────────────────────

interface PadData {
  name: string;
  x: number; y: number;
  width: number; height: number;
  shape: "circle" | "rect" | "oblong";
  drill: number;
  net: string;
}

interface SilkLine { x1: number; y1: number; x2: number; y2: number; }

interface PCBComponent {
  instanceId: string; name: string;
  x: number; y: number; width: number; height: number;
  pads: PadData[];
  silkscreen: SilkLine[];
}

interface TracePoint { x: number; y: number; }
interface PCBTrace { netName: string; width: number; points: TracePoint[]; }
interface NetInfo { name: string; pinCount: number; isGround: boolean; isPower: boolean; }
interface DRCItem { kind: string; net: string; x: number; y: number; detail: string; }

interface PadExclusion  { kind: string; cx: number; cy: number; radius: number; }
interface TraceExclusion { points: TracePoint[]; clearance: number; }
interface Thermal {
  cx: number; cy: number;
  outerRadius: number; innerRadius: number;
  spokeWidth: number; spokeCount: number;
}
interface CopperPour {
  net: string; clearance: number;
  padExclusions: PadExclusion[];
  traceExclusions: TraceExclusion[];
  thermals: Thermal[];
}
interface PCBUnits {
  coordinate: string; pxPerMm: number;
  traceWidthDefault: number; silkscreenWidth: number;
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

// ── Colours ─────────────────────────────────────────────────────

const BOARD_BG    = "#1a5c2a";
const BOARD_EDGE  = "#c8a92c";
const COPPER_FILL = "rgba(180,120,50,0.22)";
const SILK_COL    = "#e2e8f0";
const PAD_TH_COL  = "#fbbf24";
const PAD_SMD_COL = "#e8b030";
const PAD_STROKE  = "#78350f";
const DRILL_COL   = "#1e293b";
const DRC_COL     = "#ef4444";
const LABEL_BG    = "rgba(15,23,42,0.75)";

const NET_COLORS: Record<string, string> = { GND: "#ef4444", VCC: "#22c55e" };
const SIG_COLORS = [
  "#3b82f6", "#eab308", "#f97316", "#a855f7",
  "#06b6d4", "#ec4899", "#14b8a6", "#f43f5e",
];
function netColor(name: string, idx: number) {
  return NET_COLORS[name] ?? SIG_COLORS[idx % SIG_COLORS.length];
}

// ── Component ───────────────────────────────────────────────────

export default function PCBView() {
  const navigate  = useNavigate();
  const location  = useLocation();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const contRef   = useRef<HTMLDivElement>(null);

  const [pcb, setPcb]       = useState<PCBLayout | null>(null);
  const [scale, setScale]   = useState(1);
  const [offset, setOffset] = useState({ x: 40, y: 40 });
  const [isPan, setIsPan]   = useState(false);
  const [panSt, setPanSt]   = useState({ x: 0, y: 0 });

  const [showCopper, setShowCopper] = useState(true);
  const [showSilk, setShowSilk]     = useState(true);
  const [showPour, setShowPour]     = useState(true);
  const [showDRC, setShowDRC]       = useState(true);
  const [showLabels, setShowLabels] = useState(true);

  useEffect(() => {
    const s = location.state as { pcb?: PCBLayout } | null;
    if (s?.pcb) setPcb(s.pcb);
  }, [location.state]);

  // ── Rendering ─────────────────────────────────────────────────

  const draw = useCallback(() => {
    const cvs = canvasRef.current;
    if (!cvs || !pcb) return;
    const ctx = cvs.getContext("2d");
    if (!ctx) return;

    const dpr  = window.devicePixelRatio || 1;
    const rect = cvs.getBoundingClientRect();
    cvs.width  = rect.width  * dpr;
    cvs.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, rect.width, rect.height);

    ctx.save();
    ctx.translate(offset.x, offset.y);
    ctx.scale(scale, scale);

    const sf = pcb.units.pxPerMm;

    // Board substrate
    ctx.fillStyle   = BOARD_BG;
    ctx.fillRect(0, 0, pcb.board.width * sf, pcb.board.height * sf);
    ctx.strokeStyle = BOARD_EDGE;
    ctx.lineWidth   = 2 / scale;
    ctx.strokeRect(0, 0, pcb.board.width * sf, pcb.board.height * sf);

    // ── Copper pour ─────────────────────────────────────────────
    if (showPour && pcb.copperPour) {
      const pour = pcb.copperPour;

      ctx.fillStyle = COPPER_FILL;
      ctx.fillRect(0, 0, pcb.board.width * sf, pcb.board.height * sf);

      ctx.save();
      ctx.globalCompositeOperation = "destination-out";
      const solidCut = "rgba(0,0,0,1)";

      for (const ex of pour.padExclusions) {
        ctx.beginPath();
        ctx.arc(ex.cx * sf, ex.cy * sf, ex.radius * sf, 0, Math.PI * 2);
        ctx.fillStyle = solidCut;
        ctx.fill();
      }
      for (const te of pour.traceExclusions) {
        if (te.points.length < 2) continue;
        ctx.beginPath();
        ctx.lineWidth   = te.clearance * 2 * sf;
        ctx.lineCap     = "round";
        ctx.lineJoin    = "round";
        ctx.strokeStyle = solidCut;
        ctx.moveTo(te.points[0].x * sf, te.points[0].y * sf);
        for (let i = 1; i < te.points.length; i++)
          ctx.lineTo(te.points[i].x * sf, te.points[i].y * sf);
        ctx.stroke();
      }
      ctx.restore();

      // Thermal spokes
      ctx.strokeStyle = "rgba(180,120,50,0.5)";
      for (const th of pour.thermals) {
        const cx = th.cx * sf, cy = th.cy * sf;
        const ri = th.innerRadius * sf, ro = th.outerRadius * sf;
        ctx.lineWidth = th.spokeWidth * sf;
        for (let s = 0; s < th.spokeCount; s++) {
          const a = (s * Math.PI * 2) / th.spokeCount;
          ctx.beginPath();
          ctx.moveTo(cx + Math.cos(a) * ri, cy + Math.sin(a) * ri);
          ctx.lineTo(cx + Math.cos(a) * ro, cy + Math.sin(a) * ro);
          ctx.stroke();
        }
      }
    }

    // ── Traces ──────────────────────────────────────────────────
    if (showCopper) {
      let sigIdx = 0;
      for (const t of pcb.traces) {
        if (t.points.length < 2) continue;
        ctx.beginPath();
        ctx.strokeStyle = netColor(t.netName, sigIdx);
        ctx.lineWidth   = Math.max(t.width * sf, 1 / scale);
        ctx.lineCap     = "round";
        ctx.lineJoin    = "round";
        ctx.moveTo(t.points[0].x * sf, t.points[0].y * sf);
        for (let i = 1; i < t.points.length; i++)
          ctx.lineTo(t.points[i].x * sf, t.points[i].y * sf);
        ctx.stroke();
        if (!NET_COLORS[t.netName]) sigIdx++;
      }
    }

    // ── Components ──────────────────────────────────────────────
    for (const comp of pcb.components) {

      // Silkscreen outline
      if (showSilk) {
        ctx.strokeStyle = SILK_COL;
        ctx.lineWidth   = Math.max((pcb.units.silkscreenWidth ?? 0.15) * sf, 0.8 / scale);
        for (const sl of comp.silkscreen ?? []) {
          ctx.beginPath();
          ctx.moveTo(sl.x1 * sf, sl.y1 * sf);
          ctx.lineTo(sl.x2 * sf, sl.y2 * sf);
          ctx.stroke();
        }
        // Reference label centred on body
        const fs = Math.max(6, Math.min(10, comp.width * sf * 0.12));
        ctx.fillStyle  = SILK_COL;
        ctx.font       = `bold ${fs}px 'JetBrains Mono',monospace`;
        ctx.textAlign   = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(comp.name,
          (comp.x + comp.width / 2) * sf,
          (comp.y + comp.height / 2) * sf);
      }

      // Pads + labels
      const compCx = (comp.x + comp.width / 2);
      const compCy = (comp.y + comp.height / 2);

      for (const pad of comp.pads) {
        const px = pad.x * sf;
        const py = pad.y * sf;

        // Pad copper
        if (pad.shape === "rect") {
          const pw = pad.width * sf, ph = pad.height * sf;
          ctx.fillStyle   = PAD_SMD_COL;
          ctx.fillRect(px - pw / 2, py - ph / 2, pw, ph);
          ctx.strokeStyle = PAD_STROKE;
          ctx.lineWidth   = 0.5 / scale;
          ctx.strokeRect(px - pw / 2, py - ph / 2, pw, ph);
        } else {
          const r = (pad.width * sf) / 2;
          ctx.beginPath();
          ctx.arc(px, py, Math.max(r, 1.5 / scale), 0, Math.PI * 2);
          ctx.fillStyle   = PAD_TH_COL;
          ctx.fill();
          ctx.strokeStyle = PAD_STROKE;
          ctx.lineWidth   = 0.5 / scale;
          ctx.stroke();
        }

        // Drill hole (solder-mask clear area)
        if (pad.drill > 0) {
          const dr = (pad.drill * sf) / 2;
          ctx.beginPath();
          ctx.arc(px, py, Math.max(dr, 0.8 / scale), 0, Math.PI * 2);
          ctx.fillStyle = DRILL_COL;
          ctx.fill();
        }

        // Pad name — offset OUTSIDE the component body so labels
        // never overlap traces or other pads
        if (showLabels && scale > 0.8) {
          const dirX = pad.x - compCx;
          const dirY = pad.y - compCy;
          const dirLen = Math.hypot(dirX, dirY);
          let lblX = px, lblY = py;
          const offsetMm = 1.8;
          if (dirLen > 0.01) {
            lblX = (pad.x + (dirX / dirLen) * offsetMm) * sf;
            lblY = (pad.y + (dirY / dirLen) * offsetMm) * sf;
          }

          const lblSize = Math.max(4.5, Math.min(7, pad.width * sf * 0.55));
          ctx.font        = `bold ${lblSize}px sans-serif`;
          ctx.textAlign    = "center";
          ctx.textBaseline = "middle";

          // Dark halo behind text for readability
          ctx.strokeStyle = LABEL_BG;
          ctx.lineWidth   = 2.5 / scale;
          ctx.lineJoin    = "round";
          ctx.strokeText(pad.name, lblX, lblY);
          ctx.fillStyle = "#f1f5f9";
          ctx.fillText(pad.name, lblX, lblY);
        }
      }
    }

    // ── DRC markers ─────────────────────────────────────────────
    if (showDRC && pcb.drc.length > 0) {
      const mr = 4 / scale;
      ctx.strokeStyle = DRC_COL;
      ctx.lineWidth   = 1.5 / scale;
      for (const v of pcb.drc) {
        const vx = v.x * sf, vy = v.y * sf;
        ctx.beginPath(); ctx.arc(vx, vy, mr, 0, Math.PI * 2); ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(vx - mr, vy - mr); ctx.lineTo(vx + mr, vy + mr);
        ctx.moveTo(vx + mr, vy - mr); ctx.lineTo(vx - mr, vy + mr);
        ctx.stroke();
      }
    }

    // ── Scale ruler ─────────────────────────────────────────────
    const rulerMm = 10;
    const rulerPx = rulerMm * sf;
    const rx = 10 / scale;
    const ry = pcb.board.height * sf + 18 / scale;
    ctx.strokeStyle = "#94a3b8"; ctx.lineWidth = 1.5 / scale;
    ctx.beginPath();
    ctx.moveTo(rx, ry); ctx.lineTo(rx + rulerPx, ry);
    ctx.moveTo(rx, ry - 3 / scale); ctx.lineTo(rx, ry + 3 / scale);
    ctx.moveTo(rx + rulerPx, ry - 3 / scale); ctx.lineTo(rx + rulerPx, ry + 3 / scale);
    ctx.stroke();
    ctx.fillStyle = "#94a3b8";
    ctx.font = `${9 / scale}px sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText(`${rulerMm} mm`, rx + rulerPx / 2, ry + 12 / scale);

    ctx.restore();
  }, [pcb, scale, offset, showCopper, showSilk, showPour, showDRC, showLabels]);

  useEffect(() => { draw(); }, [draw]);
  useEffect(() => {
    const fn = () => draw();
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, [draw]);

  // ── Pan / Zoom ────────────────────────────────────────────────

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setScale(s => Math.min(Math.max(s * (e.deltaY > 0 ? 0.9 : 1.1), 0.2), 12));
  }, []);
  const onDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0 || e.button === 1) { setIsPan(true); setPanSt({ x: e.clientX, y: e.clientY }); }
  }, []);
  const onMove = useCallback((e: React.MouseEvent) => {
    if (!isPan) return;
    setOffset(p => ({ x: p.x + e.clientX - panSt.x, y: p.y + e.clientY - panSt.y }));
    setPanSt({ x: e.clientX, y: e.clientY });
  }, [isPan, panSt]);
  const onUp = useCallback(() => setIsPan(false), []);

  // ── Empty state ───────────────────────────────────────────────

  if (!pcb) return (
    <div className="h-screen flex items-center justify-center bg-background text-foreground">
      <div className="text-center">
        <p className="text-muted-foreground mb-4">No PCB data. Generate a PCB from your circuit first.</p>
        <Button onClick={() => navigate(-1)}><ArrowLeft className="h-4 w-4 mr-2" /> Go Back</Button>
      </div>
    </div>
  );

  // ── Layer toggle ──────────────────────────────────────────────

  const LB = ({ label, on, fn }: { label: string; on: boolean; fn: () => void }) => (
    <button onClick={fn} className={`flex items-center gap-1 text-xs px-2 py-1 rounded border transition-colors ${on ? "border-primary/50 bg-primary/10 text-primary" : "border-border bg-card text-muted-foreground"}`}>
      {on ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}{label}
    </button>
  );

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      {/* Toolbar */}
      <div className="h-14 border-b border-border bg-card flex items-center px-4 gap-3 z-20 flex-shrink-0">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}><ArrowLeft className="h-4 w-4" /></Button>
        <span className="text-sm font-semibold text-card-foreground">PCB Layout</span>
        <span className="text-xs text-muted-foreground hidden sm:inline">
          {pcb.board.width}×{pcb.board.height} mm | {pcb.components.length} comp | {pcb.nets.length} nets | {pcb.traces.length} traces
        </span>
        {pcb.drc.length > 0 && (
          <span className="text-xs text-destructive flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />{pcb.drc.length} DRC
          </span>
        )}
        <div className="flex-1" />
        <div className="flex items-center gap-1">
          <LB label="Copper"    on={showCopper} fn={() => setShowCopper(!showCopper)} />
          <LB label="Silk"      on={showSilk}   fn={() => setShowSilk(!showSilk)} />
          <LB label="GND Pour"  on={showPour}   fn={() => setShowPour(!showPour)} />
          <LB label="DRC"       on={showDRC}    fn={() => setShowDRC(!showDRC)} />
          <LB label="Labels"    on={showLabels} fn={() => setShowLabels(!showLabels)} />
        </div>
        <div className="flex items-center gap-1 border border-border rounded-md">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setScale(s => Math.min(s * 1.2, 12))}><ZoomIn className="h-3 w-3" /></Button>
          <span className="text-xs text-muted-foreground w-12 text-center font-mono">{Math.round(scale * 100)}%</span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setScale(s => Math.max(s * 0.8, 0.2))}><ZoomOut className="h-3 w-3" /></Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => { setScale(1); setOffset({ x: 40, y: 40 }); }}><RotateCcw className="h-3 w-3" /></Button>
        </div>
      </div>

      {/* Canvas */}
      <div ref={contRef} className="flex-1 bg-neutral-900 cursor-grab active:cursor-grabbing"
        onWheel={onWheel} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}>
        <canvas ref={canvasRef} className="w-full h-full" />
      </div>

      {/* Info bar */}
      <div className="h-10 border-t border-border bg-card flex items-center px-4 text-xs text-muted-foreground gap-4 overflow-x-auto">
        <span className="shrink-0">Layer: {pcb.layer}</span>
        <span className="shrink-0">Units: {pcb.units.coordinate}</span>
        {pcb.nets.map((net, i) => (
          <span key={net.name} className="flex items-center gap-1 shrink-0">
            <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: netColor(net.name, i) }} />
            {net.name}{net.isGround && " (GND)"}{net.isPower && " (PWR)"}&nbsp;({net.pinCount})
          </span>
        ))}
      </div>
    </div>
  );
}

import type { CanvasWire, CanvasModuleInstance, ModulePin, PinPosition, WireWaypoint } from "@/lib/circuit-types";
import { MODULE_DISPLAY_WIDTH } from "@/lib/circuit-types";

interface WireLayerProps {
  wires: CanvasWire[];
  placedModules: CanvasModuleInstance[];
  modulePinsMap: Record<string, ModulePin[]>;
  moduleHeights: Record<string, number>;
  pendingWire: {
    fromX: number;
    fromY: number;
    toX: number;
    toY: number;
    color: string;
    waypoints: WireWaypoint[];
  } | null;
  selectedWireId: string | null;
  onWireClick: (wireId: string) => void;
  onWaypointDrag: (wireId: string, waypointIndex: number, x: number, y: number) => void;
  scale: number;
  offset: { x: number; y: number };
  canvasRef: React.RefObject<HTMLDivElement | null>;
}

export default function WireLayer({
  wires,
  placedModules,
  modulePinsMap,
  moduleHeights,
  pendingWire,
  selectedWireId,
  onWireClick,
  onWaypointDrag,
  scale,
  offset,
  canvasRef,
}: WireLayerProps) {
  const getPinScreenPos = (instanceId: string, pinId: string): PinPosition | null => {
    const instance = placedModules.find(m => m.instanceId === instanceId);
    if (!instance) return null;
    const pins = modulePinsMap[instance.moduleId];
    if (!pins) return null;
    const pin = pins.find(p => p.id === pinId);
    if (!pin) return null;
    const height = moduleHeights[instance.moduleId] ?? MODULE_DISPLAY_WIDTH;
    return {
      x: instance.x + (pin.x / 100) * MODULE_DISPLAY_WIDTH,
      y: instance.y + (pin.y / 100) * height,
    };
  };

  const createWirePath = (from: PinPosition, to: PinPosition, waypoints?: WireWaypoint[]): string => {
    const points: PinPosition[] = [from, ...(waypoints || []), to];
    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      d += ` L ${points[i].x} ${points[i].y}`;
    }
    return d;
  };

  const handleWaypointMouseDown = (
    e: React.MouseEvent,
    wireId: string,
    waypointIndex: number
  ) => {
    e.stopPropagation();
    e.preventDefault();

    const onMouseMove = (ev: MouseEvent) => {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = (ev.clientX - rect.left - offset.x) / scale;
      const y = (ev.clientY - rect.top - offset.y) / scale;
      onWaypointDrag(wireId, waypointIndex, x, y);
    };

    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ zIndex: 20 }}
    >
      {wires.map(wire => {
        const from = getPinScreenPos(wire.fromInstanceId, wire.fromPinId);
        const to = getPinScreenPos(wire.toInstanceId, wire.toPinId);
        if (!from || !to) return null;

        const path = createWirePath(from, to, wire.waypoints);
        const isSelected = selectedWireId === wire.id;

        return (
          <g key={wire.id}>
            <path
              d={path}
              fill="none"
              stroke="transparent"
              strokeWidth="14"
              className="pointer-events-auto cursor-pointer"
              onClick={() => onWireClick(wire.id)}
            />
            <path
              d={path}
              fill="none"
              stroke={wire.color}
              strokeWidth={isSelected ? 5 : 3}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={0.5}
              filter="blur(2px)"
            />
            <path
              d={path}
              fill="none"
              stroke={wire.color}
              strokeWidth={isSelected ? 3 : 2}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={1}
            />
            {/* Endpoint dots */}
            {isSelected && (
              <>
                <circle cx={from.x} cy={from.y} r="5" fill={wire.color} stroke="white" strokeWidth="1.5" />
                <circle cx={to.x} cy={to.y} r="5" fill={wire.color} stroke="white" strokeWidth="1.5" />
              </>
            )}
            {/* Draggable waypoint dots */}
            {isSelected && wire.waypoints?.map((wp, i) => (
              <circle
                key={i}
                cx={wp.x}
                cy={wp.y}
                r="6"
                fill={wire.color}
                stroke="white"
                strokeWidth="2"
                className="pointer-events-auto cursor-grab"
                onMouseDown={(e) => handleWaypointMouseDown(e, wire.id, i)}
              />
            ))}
          </g>
        );
      })}

      {/* Pending wire being drawn */}
      {pendingWire && (() => {
        const points: PinPosition[] = [
          { x: pendingWire.fromX, y: pendingWire.fromY },
          ...pendingWire.waypoints,
          { x: pendingWire.toX, y: pendingWire.toY },
        ];
        let d = `M ${points[0].x} ${points[0].y}`;
        for (let i = 1; i < points.length; i++) {
          d += ` L ${points[i].x} ${points[i].y}`;
        }
        return (
          <g>
            <path
              d={d}
              fill="none"
              stroke={pendingWire.color}
              strokeWidth="2"
              strokeDasharray="6 3"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={1}
            />
            {pendingWire.waypoints.map((wp, i) => (
              <circle
                key={i}
                cx={wp.x}
                cy={wp.y}
                r="4"
                fill={pendingWire.color}
                stroke="white"
                strokeWidth="1.5"
                opacity={1}
              />
            ))}
          </g>
        );
      })()}
    </svg>
  );
}

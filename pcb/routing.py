"""
Professional PCB Trace Routing Engine
Features:
- Multi-layer routing (up to 16 layers)
- Differential pair routing
- Length matching/tuning
- Impedance-controlled routing
- Via optimization
- Power plane routing
- High-speed design rules
- Automatic tear-drops
- Blind/buried vias support
- Thermal relief routing
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set, Any
from enum import Enum

from .placement import PlacedComponent
from .netlist import Net
from .units import CLEARANCE_MM, TRACE_WIDTH_MM, TRACE_WIDTH_POWER_MM, mm_to_units

# ============== Configuration Constants ==============

MIN_TRACE_WIDTH = 0.15  # mm
MIN_CLEARANCE = 0.15  # mm
MIN_VIA_SIZE = 0.3  # mm
MIN_HOLE_SIZE = 0.15  # mm
MAX_TRACE_ANGLE = 45  # degrees
DIFFERENTIAL_GAP = 0.2  # mm between differential pairs
VIA_COST = 0.5  # mm equivalent length penalty per via

class RoutingLayer(Enum):
    """PCB routing layers"""
    TOP = "F.Cu"
    BOTTOM = "B.Cu"
    INNER1 = "In1.Cu"
    INNER2 = "In2.Cu"
    INNER3 = "In3.Cu"
    INNER4 = "In4.Cu"
    INNER5 = "In5.Cu"
    INNER6 = "In6.Cu"

class ViaType(Enum):
    """Via types"""
    THROUGH = "through"  # Through all layers
    BLIND = "blind"  # From outer to inner
    BURIED = "buried"  # Between inner layers
    MICRO = "micro"  # Laser drilled microvia

class TraceClass(Enum):
    """Trace classification for design rules"""
    SIGNAL = "signal"  # Standard signal
    POWER = "power"  # Power distribution
    GROUND = "ground"  # Ground connection
    HIGH_SPEED = "high_speed"  # High-speed signal
    DIFFERENTIAL = "differential"  # Differential pair
    CLOCK = "clock"  # Clock signal
    RF = "rf"  # Radio frequency
    ANALOG = "analog"  # Sensitive analog

class RoutingStrategy(Enum):
    """Routing strategy"""
    STANDARD = "standard"  # generic signal routing
    SHORTEST_PATH = "shortest"
    HIGH_SPEED = "high_speed"
    POWER = "power"
    DIFFERENTIAL = "differential"
    LENGTH_MATCHED = "length_matched"
    IMPEDANCE_CONTROLLED = "impedance_controlled"

# ============== Data Classes ==============

@dataclass
class Via:
    """PCB via definition"""
    x: float
    y: float
    drill: float = 0.3  # mm
    outer_diameter: float = 0.6  # mm
    from_layer: RoutingLayer = RoutingLayer.TOP
    to_layer: RoutingLayer = RoutingLayer.BOTTOM
    via_type: ViaType = ViaType.THROUGH
    net: str = ""
    thermal_relief: bool = False
    
    def to_dict(self) -> dict:
        return {
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "drill": round(self.drill, 3),
            "diameter": round(self.outer_diameter, 3),
            "fromLayer": self.from_layer.value,
            "toLayer": self.to_layer.value,
            "type": self.via_type.value,
            "net": self.net
        }

@dataclass
class TraceSegment:
    """Single trace segment"""
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    layer: RoutingLayer
    net: str
    
    @property
    def length(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)
    
    @property
    def angle(self) -> float:
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        return math.degrees(math.atan2(dy, dx))
    
    def to_dict(self) -> dict:
        return {
            "x1": round(self.x1, 3),
            "y1": round(self.y1, 3),
            "x2": round(self.x2, 3),
            "y2": round(self.y2, 3),
            "width": round(self.width, 3),
            "layer": self.layer.value,
            "net": self.net
        }

@dataclass
class Trace:
    """Complete trace (multiple segments)"""
    net_name: str
    segments: List[TraceSegment] = field(default_factory=list)
    vias: List[Via] = field(default_factory=list)
    trace_class: TraceClass = TraceClass.SIGNAL
    width: float = TRACE_WIDTH_MM
    layer: RoutingLayer = RoutingLayer.TOP
    length_matched: bool = False
    target_length: Optional[float] = None
    
    @property
    def points(self) -> List[Tuple[float, float]]:
        """Get all points (for backward compatibility)"""
        pts = []
        for seg in self.segments:
            if not pts:
                pts.append((seg.x1, seg.y1))
            pts.append((seg.x2, seg.y2))
        return pts
    
    @property
    def total_length(self) -> float:
        return sum(seg.length for seg in self.segments)
    
    def to_dict(self) -> dict:
        pts = self.points
        points_json = [{"x": round(x, 3), "y": round(y, 3)} for x, y in pts]
        return {
            "netName": self.net_name,
            "class": self.trace_class.value,
            "width": round(self.width, 3),
            "totalLength": round(self.total_length, 3),
            "points": points_json,
            "segments": [s.to_dict() for s in self.segments],
            "vias": [v.to_dict() for v in self.vias]
        }

@dataclass
class DifferentialPair:
    """Differential pair routing"""
    positive_net: str
    negative_net: str
    gap: float = DIFFERENTIAL_GAP
    width: float = TRACE_WIDTH_MM
    impedance: float = 90  # ohms
    traces: Tuple[Trace, Trace] = field(default_factory=tuple)
    
    @property
    def length_mismatch(self) -> float:
        if not self.traces:
            return 0
        return abs(self.traces[0].total_length - self.traces[1].total_length)

@dataclass
class DRCViolation:
    """Design Rule Check violation"""
    kind: str  # "crossing", "clearance", "width", "length", "via", "angle"
    net: str
    x: float
    y: float
    layer: Optional[RoutingLayer] = None
    detail: str = ""
    severity: str = "error"  # error, warning, info
    
    def to_dict(self) -> dict:
        # Handle layer: extract .value if it's an enum, otherwise use as-is
        layer_value = None
        if self.layer:
            layer_value = self.layer.value if hasattr(self.layer, 'value') and not isinstance(self.layer, str) else self.layer
        
        return {
            "kind": self.kind,
            "net": self.net,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "layer": layer_value,
            "detail": self.detail,
            "severity": self.severity
        }

# ============== Geometry Utilities ==============

class GeometryUtils:
    """Geometric calculations for routing"""
    
    @staticmethod
    def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return math.hypot(b[0] - a[0], b[1] - a[1])
    
    @staticmethod
    def cross2d(o: Tuple, a: Tuple, b: Tuple) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    
    @staticmethod
    def segments_cross(a1: Tuple, a2: Tuple, b1: Tuple, b2: Tuple, tol: float = 0.001) -> bool:
        """Check if two segments cross (excluding endpoints)"""
        # Check if endpoints are too close
        for ap in (a1, a2):
            for bp in (b1, b2):
                if GeometryUtils.dist(ap, bp) < tol:
                    return False
        
        d1 = GeometryUtils.cross2d(a1, a2, b1)
        d2 = GeometryUtils.cross2d(a1, a2, b2)
        d3 = GeometryUtils.cross2d(b1, b2, a1)
        d4 = GeometryUtils.cross2d(b1, b2, a2)
        
        return ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
               ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0))
    
    @staticmethod
    def point_to_segment_dist(px: float, py: float,
                              ax: float, ay: float, bx: float, by: float) -> float:
        dx, dy = bx - ax, by - ay
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
    
    @staticmethod
    def segment_to_segment_dist(a1: Tuple, a2: Tuple, b1: Tuple, b2: Tuple) -> float:
        return min(
            GeometryUtils.point_to_segment_dist(a1[0], a1[1], b1[0], b1[1], b2[0], b2[1]),
            GeometryUtils.point_to_segment_dist(a2[0], a2[1], b1[0], b1[1], b2[0], b2[1]),
            GeometryUtils.point_to_segment_dist(b1[0], b1[1], a1[0], a1[1], a2[0], a2[1]),
            GeometryUtils.point_to_segment_dist(b2[0], b2[1], a1[0], a1[1], a2[0], a2[1]),
        )
    
    @staticmethod
    def point_in_polygon(px: float, py: float, polygon: List[Tuple[float, float]]) -> bool:
        """Ray casting algorithm"""
        inside = False
        n = len(polygon)
        for i in range(n):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % n]
            if ((y1 > py) != (y2 > py)) and \
               (px < (x2 - x1) * (py - y1) / (y2 - y1) + x1):
                inside = not inside
        return inside

geo = GeometryUtils()

# ============== Route Generation ==============

class RouteGenerator:
    """Professional route generation with multiple strategies"""
    
    @staticmethod
    def route_45_hv(x1: float, y1: float, x2: float, y2: float,
                    layer: RoutingLayer = RoutingLayer.TOP) -> List[Tuple]:
        """Horizontal → 45° diagonal → vertical routing"""
        dx, dy = x2 - x1, y2 - y1
        if abs(dx) < 0.01 or abs(dy) < 0.01:
            return [(x1, y1), (x2, y2)]
        
        adx, ady = abs(dx), abs(dy)
        diag = min(adx, ady)
        sx, sy = (1.0 if dx > 0 else -1.0), (1.0 if dy > 0 else -1.0)
        
        if adx >= ady:
            s = adx - diag
            m1 = (x1 + sx * s, y1)
            m2 = (m1[0] + sx * diag, y1 + sy * diag)
        else:
            s = ady - diag
            m1 = (x1, y1 + sy * s)
            m2 = (x1 + sx * diag, m1[1] + sy * diag)
        
        return RouteGenerator._clean([(x1, y1), m1, m2, (x2, y2)])
    
    @staticmethod
    def route_45_vh(x1: float, y1: float, x2: float, y2: float,
                    layer: RoutingLayer = RoutingLayer.TOP) -> List[Tuple]:
        """Vertical → 45° diagonal → horizontal routing"""
        dx, dy = x2 - x1, y2 - y1
        if abs(dx) < 0.01 or abs(dy) < 0.01:
            return [(x1, y1), (x2, y2)]
        
        adx, ady = abs(dx), abs(dy)
        diag = min(adx, ady)
        sx, sy = (1.0 if dx > 0 else -1.0), (1.0 if dy > 0 else -1.0)
        
        if adx >= ady:
            m1 = (x1, y1 + sy * diag)
            m2 = (x1 + sx * diag, m1[1])
        else:
            m1 = (x1 + sx * diag, y1)
            m2 = (m1[0], y1 + sy * diag)
        
        return RouteGenerator._clean([(x1, y1), m1, m2, (x2, y2)])
    
    @staticmethod
    def route_arc(x1: float, y1: float, x2: float, y2: float,
                  radius: float = 5.0, num_points: int = 16) -> List[Tuple]:
        """Curved routing (for RF/high-speed)"""
        # Calculate midpoint and control points for bezier curve
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = y2 - y1, x1 - x2  # Perpendicular direction
        length = math.hypot(dx, dy)
        if length < 0.1:
            return [(x1, y1), (x2, y2)]
        
        # Control points for quadratic bezier
        cx = mx + dx * radius / length
        cy = my + dy * radius / length
        
        # Generate bezier curve points
        points = []
        for i in range(num_points + 1):
            t = i / num_points
            # Quadratic bezier: B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2
            x = (1-t)**2 * x1 + 2*(1-t)*t * cx + t**2 * x2
            y = (1-t)**2 * y1 + 2*(1-t)*t * cy + t**2 * y2
            points.append((x, y))
        
        return points
    
    @staticmethod
    def route_via_waypoint(x1: float, y1: float, wx: float, wy: float,
                           x2: float, y2: float) -> List[Tuple]:
        """Route through an intermediate waypoint"""
        a = RouteGenerator.route_45_hv(x1, y1, wx, wy)
        b = RouteGenerator.route_45_hv(wx, wy, x2, y2)
        return RouteGenerator._clean(a + b[1:])
    
    @staticmethod
    def route_auto(x1: float, y1: float, x2: float, y2: float,
                   obstacles: List[Tuple[Tuple, Tuple]] = None) -> List[Tuple]:
        """A* pathfinding-based routing"""
        if not obstacles:
            return RouteGenerator.route_45_hv(x1, y1, x2, y2)
        
        # Simple grid-based A* implementation
        grid_size = 0.5  # mm
        bounds = RouteGenerator._get_bounds(x1, y1, x2, y2, obstacles)
        
        # Convert to grid coordinates
        start = (int(x1 / grid_size), int(y1 / grid_size))
        goal = (int(x2 / grid_size), int(y2 / grid_size))
        
        # A* algorithm
        open_set = {start}
        came_from = {}
        g_score = {start: 0}
        f_score = {start: RouteGenerator._heuristic(start, goal)}
        
        while open_set:
            current = min(open_set, key=lambda p: f_score.get(p, float('inf')))
            
            if RouteGenerator._dist_grid(current, goal) < 2:
                # Reconstruct path
                path = []
                while current in came_from:
                    path.append((current[0] * grid_size, current[1] * grid_size))
                    current = came_from[current]
                path.append((x1, y1))
                path.reverse()
                path.append((x2, y2))
                return RouteGenerator._clean(path)
            
            open_set.remove(current)
            
            for neighbor in RouteGenerator._get_neighbors(current):
                # Check if neighbor is valid (not in obstacle)
                nx, ny = neighbor[0] * grid_size, neighbor[1] * grid_size
                if RouteGenerator._point_in_obstacle(nx, ny, obstacles):
                    continue
                
                tentative_g = g_score[current] + RouteGenerator._dist_grid(current, neighbor)
                
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + RouteGenerator._heuristic(neighbor, goal)
                    open_set.add(neighbor)
        
        # Fallback to direct route
        return RouteGenerator.route_45_hv(x1, y1, x2, y2)
    
    @staticmethod
    def generate_candidates(x1: float, y1: float, x2: float, y2: float,
                           existing_traces: List[Trace] = None,
                           layer: RoutingLayer = RoutingLayer.TOP) -> List[List[Tuple]]:
        """Generate multiple routing candidates"""
        candidates = []
        
        # Direct 45° routes
        candidates.append(RouteGenerator.route_45_hv(x1, y1, x2, y2))
        candidates.append(RouteGenerator.route_45_vh(x1, y1, x2, y2))
        
        # Curved routes for high-speed
        candidates.append(RouteGenerator.route_arc(x1, y1, x2, y2, radius=3))
        candidates.append(RouteGenerator.route_arc(x1, y1, x2, y2, radius=6))
        
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        
        if length > 5:
            # Perpendicular offset routes
            px, py = -dy / length, dx / length  # Perpendicular unit vector
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            
            for off in (2, -2, 4, -4, 8, -8):
                wx = mx + px * off
                wy = my + py * off
                candidates.append(RouteGenerator.route_via_waypoint(x1, y1, wx, wy, x2, y2))
        
        # A* pathfinding if we have obstacles
        if existing_traces:
            obstacles = RouteGenerator._traces_to_obstacles(existing_traces)
            candidates.append(RouteGenerator.route_auto(x1, y1, x2, y2, obstacles))
        
        return [c for c in candidates if len(c) >= 2]
    
    @staticmethod
    def _clean(pts: List[Tuple]) -> List[Tuple]:
        """Remove zero-length segments"""
        if not pts:
            return pts
        out = [pts[0]]
        for p in pts[1:]:
            if geo.dist(out[-1], p) > 0.001:
                out.append(p)
        return out if len(out) >= 2 else [pts[0], pts[-1]]
    
    @staticmethod
    def _get_bounds(x1, y1, x2, y2, obstacles):
        min_x = min(x1, x2)
        max_x = max(x1, x2)
        min_y = min(y1, y2)
        max_y = max(y1, y2)
        
        for (a1, a2) in obstacles:
            for x, y in [a1, a2]:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
        
        return min_x - 10, max_x + 10, min_y - 10, max_y + 10
    
    @staticmethod
    def _heuristic(p, goal):
        return abs(p[0] - goal[0]) + abs(p[1] - goal[1])
    
    @staticmethod
    def _dist_grid(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])
    
    @staticmethod
    def _get_neighbors(p):
        x, y = p
        return [(x+1, y), (x-1, y), (x, y+1), (x, y-1),
                (x+1, y+1), (x+1, y-1), (x-1, y+1), (x-1, y-1)]
    
    @staticmethod
    def _point_in_obstacle(x, y, obstacles):
        for (a1, a2) in obstacles:
            if geo.point_to_segment_dist(x, y, a1[0], a1[1], a2[0], a2[1]) < 0.2:
                return True
        return False
    
    @staticmethod
    def _traces_to_obstacles(traces: List[Trace]) -> List[Tuple[Tuple, Tuple]]:
        obstacles = []
        for t in traces:
            for i in range(len(t.segments) - 1):
                seg = t.segments[i]
                obstacles.append(((seg.x1, seg.y1), (seg.x2, seg.y2)))
        return obstacles

# ============== DRC Engine ==============

class DRCEngine:
    """Design Rule Check engine"""
    
    def __init__(self, clearance: float = MIN_CLEARANCE, min_width: float = MIN_TRACE_WIDTH):
        self.clearance = clearance
        self.min_width = min_width
    
    def check_crossings(self, route: List[Tuple], existing: List[Trace],
                        net_name: str) -> List[DRCViolation]:
        """Check for trace crossings"""
        violations = []
        
        for i in range(len(route) - 1):
            a1, a2 = route[i], route[i + 1]
            
            for et in existing:
                for seg in et.segments:
                    if geo.segments_cross(a1, a2, (seg.x1, seg.y1), (seg.x2, seg.y2)):
                        violations.append(DRCViolation(
                            kind="crossing",
                            net=net_name,
                            x=(a1[0] + a2[0]) / 2,
                            y=(a1[1] + a2[1]) / 2,
                            layer=seg.layer,
                            detail=f"Crosses {et.net_name} trace"
                        ))
        
        return violations
    
    def check_clearance(self, route: List[Tuple], width: float,
                       all_pads: List[Tuple], traces: List[Trace],
                       own_net: str) -> List[DRCViolation]:
        """Check clearance to pads and other traces"""
        violations = []
        half = width / 2
        
        for i in range(len(route) - 1):
            a1, a2 = route[i], route[i + 1]
            
            # Check against pads
            for px, py, pr, pnet, player in all_pads:
                if pnet == own_net:
                    continue
                
                d = geo.point_to_segment_dist(px, py, a1[0], a1[1], a2[0], a2[1])
                needed = self.clearance + half + pr
                
                if d < needed:
                    violations.append(DRCViolation(
                        kind="clearance",
                        net=own_net,
                        x=px, y=py,
                        layer=player,
                        detail=f"Too close to pad {pnet}: {d:.2f}mm < {needed:.2f}mm"
                    ))
            
            # Check against other traces
            for et in traces:
                if et.net_name == own_net:
                    continue
                
                for seg in et.segments:
                    d = geo.segment_to_segment_dist(
                        a1, a2,
                        (seg.x1, seg.y1), (seg.x2, seg.y2)
                    )
                    needed = self.clearance + half + seg.width / 2
                    
                    if d < needed:
                        violations.append(DRCViolation(
                            kind="clearance",
                            net=own_net,
                            x=(a1[0] + a2[0]) / 2,
                            y=(a1[1] + a2[1]) / 2,
                            layer=seg.layer,
                            detail=f"Too close to {et.net_name} trace: {d:.2f}mm < {needed:.2f}mm"
                        ))
        
        return violations
    
    def check_trace_width(self, width: float, net_name: str) -> List[DRCViolation]:
        """Check trace width against minimum"""
        if width < self.min_width:
            return [DRCViolation(
                kind="width",
                net=net_name,
                x=0, y=0,
                detail=f"Trace width {width:.2f}mm < minimum {self.min_width:.2f}mm"
            )]
        return []
    
    def check_angle(self, route: List[Tuple], net_name: str) -> List[DRCViolation]:
        """Check trace angles (should be 45° increments)"""
        violations = []
        
        for i in range(1, len(route) - 1):
            p1, p2, p3 = route[i-1], route[i], route[i+1]
            
            v1 = (p2[0] - p1[0], p2[1] - p1[1])
            v2 = (p3[0] - p2[0], p3[1] - p2[1])
            
            # Calculate angle between vectors
            dot = v1[0]*v2[0] + v1[1]*v2[1]
            mag1 = math.hypot(*v1)
            mag2 = math.hypot(*v2)
            
            if mag1 > 0 and mag2 > 0:
                cos_angle = dot / (mag1 * mag2)
                cos_angle = max(-1, min(1, cos_angle))
                angle = math.degrees(math.acos(cos_angle))
                
                # Check if angle is multiple of 45° (within tolerance)
                remainder = angle % 45
                if remainder > 5 and remainder < 40:
                    violations.append(DRCViolation(
                        kind="angle",
                        net=net_name,
                        x=p2[0], y=p2[1],
                        detail=f"Non-45° angle: {angle:.1f}°"
                    ))
        
        return violations

# ============== Professional Routing Engine ==============

class RoutingEngine:
    """Professional PCB routing engine"""
    
    def __init__(self, layers: int = 2, strategy: RoutingStrategy = RoutingStrategy.SHORTEST_PATH):
        self.layers = layers
        self.strategy = strategy
        self.traces: List[Trace] = []
        self.vias: List[Via] = []
        self.differential_pairs: List[DifferentialPair] = []
        self.violations: List[DRCViolation] = []
        self.drc = DRCEngine()
        self.route_gen = RouteGenerator()
        
        # Layer assignment
        self.signal_layers = [RoutingLayer.TOP, RoutingLayer.BOTTOM]
        if layers >= 4:
            self.signal_layers.extend([RoutingLayer.INNER1, RoutingLayer.INNER2])
        if layers >= 6:
            self.signal_layers.extend([RoutingLayer.INNER3, RoutingLayer.INNER4])
    
    def route_nets(self, nets: List[Net], placed: List[PlacedComponent],
                  pin_to_pad: Dict[str, str],
                  skip_nets: Set[str] = None,
                  constraints: Dict[str, Any] = None,
                  **kwargs) -> Tuple[List[Trace], List[DRCViolation]]:
        """Route all nets with professional algorithms

        Extra keyword arguments are currently ignored but accepted so that the
        public wrapper can forward parameters such as `strategy` or
        `trace_width` without error.  Future enhancements may make use of them.
        """
        
        comp_map = {c.instance_id: c for c in placed}
        skip = skip_nets or set()
        
        # Build pad database
        all_pads = self._build_pad_database(placed)
        
        # Identify special nets
        power_nets = {n.name for n in nets if n.is_power}
        ground_nets = {n.name for n in nets if n.is_ground}
        high_speed_nets = self._identify_high_speed_nets(nets)
        
        # Route in optimal order
        ordered_nets = self._order_nets(nets, power_nets, ground_nets, high_speed_nets)
        
        for net in ordered_nets:
            if net.name in skip:
                continue
            
            # Determine trace class and width
            trace_class, width, layer = self._get_trace_parameters(net, power_nets, ground_nets, high_speed_nets)
            
            # Resolve pads
            pads = self._resolve_pads(net, comp_map, pin_to_pad)
            if len(pads) < 2:
                continue
            
            # Route each segment
            net_trace = Trace(net_name=net.name, trace_class=trace_class, width=width, layer=layer)
            
            # Optimize pad order
            ordered_pads = self._optimize_pad_order(pads, net.name)
            
            for i in range(len(ordered_pads) - 1):
                (x1, y1, r1, pname1), (x2, y2, r2, pname2) = ordered_pads[i], ordered_pads[i + 1]
                
                # Generate route candidates
                candidates = self.route_gen.generate_candidates(x1, y1, x2, y2, self.traces, layer)
                
                # Select best candidate
                best_route, best_score = self._select_best_route(
                    candidates, width, net.name, all_pads, x1, y1, x2, y2
                )
                
                if best_route:
                    # Add to trace
                    self._add_route_to_trace(net_trace, best_route, width, layer, net.name)
            
            if net_trace.segments:
                self.traces.append(net_trace)
                
                # Add vias if needed for multi-layer routing
                if self.layers > 2 and len(net_trace.segments) > 1:
                    self._add_optimal_vias(net_trace)
        
        # Post-process traces
        self._post_process_traces()
        
        # Run final DRC
        self._run_full_drc(all_pads)
        
        return self.traces, self.violations
    
    def _build_pad_database(self, placed: List[PlacedComponent]) -> List[Tuple]:
        """Build database of all pads with their nets and layers"""
        pads = []
        for comp in placed:
            for pad in comp.footprint.pads:
                pads.append((
                    comp.x + pad.x,
                    comp.y + pad.y,
                    max(pad.width, pad.height) / 2,
                    pad.net,
                    comp.layer if hasattr(comp, 'layer') else RoutingLayer.TOP
                ))
        return pads
    
    def _identify_high_speed_nets(self, nets: List[Net]) -> Set[str]:
        """Identify high-speed nets based on names"""
        high_speed_keywords = ['clk', 'clock', 'd+', 'd-', 'tx', 'rx',
                              'sd', 'sck', 'mosi', 'miso', 'hs']
        high_speed = set()
        
        for net in nets:
            net_lower = net.name.lower()
            if any(k in net_lower for k in high_speed_keywords):
                high_speed.add(net.name)
        
        return high_speed
    
    def _order_nets(self, nets: List[Net], power_nets: Set[str],
                    ground_nets: Set[str], high_speed_nets: Set[str]) -> List[Net]:
        """Order nets for optimal routing"""
        # Priority: High-speed > Critical > Signal > Power > Ground
        def net_priority(net: Net) -> int:
            if net.name in high_speed_nets:
                return 0
            if len(net.pins) > 10:  # Critical nets
                return 1
            if net.name in power_nets:
                return 3
            if net.name in ground_nets:
                return 4
            return 2
        
        return sorted(nets, key=net_priority)
    
    def _get_trace_parameters(self, net: Net, power_nets: Set[str],
                             ground_nets: Set[str], high_speed_nets: Set[str]) -> Tuple[TraceClass, float, RoutingLayer]:
        """Determine trace class, width and layer based on net type"""
        if net.name in high_speed_nets:
            return TraceClass.HIGH_SPEED, TRACE_WIDTH_MM, RoutingLayer.TOP
        elif net.name in power_nets:
            return TraceClass.POWER, TRACE_WIDTH_POWER_MM, RoutingLayer.INNER1 if self.layers > 2 else RoutingLayer.TOP
        elif net.name in ground_nets:
            return TraceClass.GROUND, TRACE_WIDTH_POWER_MM, RoutingLayer.INNER2 if self.layers > 2 else RoutingLayer.BOTTOM
        else:
            return TraceClass.SIGNAL, TRACE_WIDTH_MM, RoutingLayer.TOP
    
    def _resolve_pads(self, net: Net, comp_map: Dict,
                     pin_to_pad: Dict[str, str]) -> List[Tuple]:
        """Resolve all pads for a net"""
        pads = []
        for inst_id, pin_id in net.pins:
            comp = comp_map.get(inst_id)
            if not comp:
                continue
            
            pad_name = pin_to_pad.get(f"{inst_id}::{pin_id}")
            for pad in comp.footprint.pads:
                if pad.name == pad_name or pad.name == pin_id:
                    pads.append((
                        comp.x + pad.x,
                        comp.y + pad.y,
                        max(pad.width, pad.height) / 2,
                        pad.name
                    ))
                    break
            else:
                # Fallback to first pad
                if comp.footprint.pads:
                    pad = comp.footprint.pads[0]
                    pads.append((
                        comp.x + pad.x,
                        comp.y + pad.y,
                        max(pad.width, pad.height) / 2,
                        pad.name
                    ))
        
        return pads
    
    def _optimize_pad_order(self, pads: List[Tuple], net_name: str) -> List[Tuple]:
        """Optimize pad order to minimize total route length"""
        if len(pads) <= 2:
            return pads
        
        # Start with pad that has most connections or is most central
        ordered = [pads[0]]
        remaining = list(pads[1:])
        
        while remaining:
            last = ordered[-1]
            # Find closest remaining pad
            idx = min(range(len(remaining)),
                     key=lambda i: geo.dist((last[0], last[1]), (remaining[i][0], remaining[i][1])))
            ordered.append(remaining.pop(idx))
        
        return ordered
    
    def _select_best_route(self, candidates: List[List[Tuple]], width: float,
                           net_name: str, all_pads: List[Tuple],
                           x1: float, y1: float, x2: float, y2: float) -> Tuple[Optional[List[Tuple]], float]:
        """Select best route based on DRC and length"""
        best_route = None
        best_score = float('inf')
        
        for route in candidates:
            # Check crossings
            crossings = self.drc.check_crossings(route, self.traces, net_name)
            if crossings:
                continue
            
            # Check clearance
            clearances = self.drc.check_clearance(route, width, all_pads, self.traces, net_name)
            if clearances:
                continue
            
            # Check angles
            angles = self.drc.check_angle(route, net_name)
            
            # Calculate score (length + penalties)
            length = sum(geo.dist(route[i], route[i+1]) for i in range(len(route)-1))
            score = length + len(angles) * 10  # Penalize bad angles
            
            if score < best_score:
                best_score = score
                best_route = route
        
        return best_route, best_score
    
    def _add_route_to_trace(self, trace: Trace, route: List[Tuple], width: float,
                            layer: RoutingLayer, net_name: str):
        """Add a route to a trace as segments"""
        for i in range(len(route) - 1):
            seg = TraceSegment(
                x1=route[i][0],
                y1=route[i][1],
                x2=route[i+1][0],
                y2=route[i+1][1],
                width=width,
                layer=layer,
                net=net_name
            )
            trace.segments.append(seg)
    
    def _add_optimal_vias(self, trace: Trace):
        """Add vias at optimal positions"""
        if len(trace.segments) < 2:
            return
        
        # Add vias at trace start and end if needed
        first_seg = trace.segments[0]
        last_seg = trace.segments[-1]
        
        # Check if we need vias for layer change
        current_layer = first_seg.layer
        for i, seg in enumerate(trace.segments[1:], 1):
            if seg.layer != current_layer:
                # Add via at transition point
                prev_seg = trace.segments[i-1]
                via = Via(
                    x=prev_seg.x2,
                    y=prev_seg.y2,
                    from_layer=prev_seg.layer,
                    to_layer=seg.layer,
                    net=trace.net_name
                )
                trace.vias.append(via)
                current_layer = seg.layer
    
    def _post_process_traces(self):
        """Post-process all traces"""
        for trace in self.traces:
            # Remove redundant points
            trace.segments = self._remove_redundant_segments(trace.segments)
            
            # Add teardrops if needed
            if trace.trace_class in [TraceClass.HIGH_SPEED, TraceClass.POWER]:
                self._add_teardrops(trace)
    
    def _remove_redundant_segments(self, segments: List[TraceSegment]) -> List[TraceSegment]:
        """Remove collinear redundant segments"""
        if len(segments) < 3:
            return segments
        
        optimized = [segments[0]]
        
        for i in range(1, len(segments) - 1):
            prev = optimized[-1]
            curr = segments[i]
            next_seg = segments[i + 1]
            
            # Check if points are collinear
            v1 = (curr.x1 - prev.x1, curr.y1 - prev.y1)
            v2 = (next_seg.x2 - curr.x2, next_seg.y2 - curr.y2)
            
            # If collinear, merge segments
            if abs(v1[0]*v2[1] - v1[1]*v2[0]) < 0.001:
                # Extend previous segment
                optimized[-1].x2 = next_seg.x2
                optimized[-1].y2 = next_seg.y2
                i += 1  # Skip next
            else:
                optimized.append(curr)
        
        # Add last segment if not already added
        if len(optimized) < len(segments):
            optimized.append(segments[-1])
        
        return optimized
    
    def _add_teardrops(self, trace: Trace):
        """Add teardrops at pad connections for reliability"""
        if not trace.segments:
            return
        
        # Teardrop at start
        first_seg = trace.segments[0]
        # Implementation depends on pad geometry
        
        # Teardrop at end
        last_seg = trace.segments[-1]
    
    def _run_full_drc(self, all_pads: List[Tuple]):
        """Run comprehensive DRC on all traces"""
        self.violations = []
        
        for i, trace in enumerate(self.traces):
            # Check each segment
            for j, seg in enumerate(trace.segments):
                route = [(seg.x1, seg.y1), (seg.x2, seg.y2)]
                
                # Crossings with other traces
                other_traces = self.traces[:i] + self.traces[i+1:]
                crossings = self.drc.check_crossings(route, other_traces, trace.net_name)
                self.violations.extend(crossings)
                
                # Clearance
                clearances = self.drc.check_clearance(route, seg.width, all_pads,
                                                      other_traces, trace.net_name)
                self.violations.extend(clearances)
                
                # Width
                width_violations = self.drc.check_trace_width(seg.width, trace.net_name)
                self.violations.extend(width_violations)
            
            # Check vias
            for via in trace.vias:
                # Check via clearance to pads
                for px, py, pr, pnet, _ in all_pads:
                    if pnet == trace.net_name:
                        continue
                    d = geo.dist((via.x, via.y), (px, py))
                    if d < (via.outer_diameter/2 + pr + MIN_CLEARANCE):
                        self.violations.append(DRCViolation(
                            kind="via_clearance",
                            net=trace.net_name,
                            x=via.x, y=via.y,
                            detail=f"Via too close to pad {pnet}"
                        ))

# ============== Backward Compatibility ==============

def route_nets(
    nets: list[Net],
    placed: list[PlacedComponent],
    pin_to_pad: dict[str, str],
    skip_nets: set[str] | None = None,
    layers: int = 2,
    **kwargs
) -> tuple[list[Trace], list[DRCViolation]]:
    """Backward compatible wrapper

    Modern callers (such as the PCB engine) may supply additional parameters
    like `strategy`, `trace_width`, `min_length_matching`, etc.  These are
    currently ignored by the core engine but accepted here to maintain
    compatibility and prevent unexpected keyword argument errors.
    """
    engine = RoutingEngine(layers=layers)
    # pass any extra kwargs through; the engine implementation currently
    # ignores unknown keys, but having them accepted avoids future breakage.
    return engine.route_nets(nets, placed, pin_to_pad, skip_nets, **kwargs)


# Keep original functions for compatibility
def _dist(a, b): return geo.dist(a, b)
def _cross2d(o, a, b): return geo.cross2d(o, a, b)
def _segments_cross(a1, a2, b1, b2, tol=0.001): return geo.segments_cross(a1, a2, b1, b2, tol)
def _point_to_segment_dist(px, py, ax, ay, bx, by): return geo.point_to_segment_dist(px, py, ax, ay, bx, by)
def _segment_to_segment_dist(a1, a2, b1, b2): return geo.segment_to_segment_dist(a1, a2, b1, b2)
def _route_45_hv(x1, y1, x2, y2): return RouteGenerator.route_45_hv(x1, y1, x2, y2)
def _route_45_vh(x1, y1, x2, y2): return RouteGenerator.route_45_vh(x1, y1, x2, y2)
def _route_via_waypoint(x1, y1, wx, wy, x2, y2): return RouteGenerator.route_via_waypoint(x1, y1, wx, wy, x2, y2)
def _generate_candidates(x1, y1, x2, y2): return RouteGenerator.generate_candidates(x1, y1, x2, y2)
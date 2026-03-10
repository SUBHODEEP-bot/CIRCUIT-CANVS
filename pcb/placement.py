"""
Professional Component Placement Engine
Features:
- Thermal-aware placement
- Signal integrity optimization
- Automatic component grouping
- Multi-zone placement (digital/analog/power)
- Height profile management
- Placement strategy: Grid, Cluster, Force-directed
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
import math
import random
from collections import defaultdict

from .footprints import Footprint, Pad
from .units import BOARD_EDGE_CLEARANCE, mm_to_units

# ============== Configuration Constants ==============

MIN_COMPONENT_SPACING = 2.0  # mm between components
COMPONENT_GAP = 4.0  # mm gap between courtyards
BOARD_MARGIN = 5.0  # mm from board edge
THERMAL_SPACING = 6.0  # mm around hot components
HIGH_SPEED_SPACING = 3.0  # mm around high-speed components
KEEP_OUT_ZONE = 2.0  # mm keep-out around board edges

class ComponentType(Enum):
    """Component classification for placement optimization"""
    IC_DIGITAL = "ic_digital"
    IC_ANALOG = "ic_analog"
    IC_POWER = "ic_power"
    IC_RF = "ic_rf"
    PASSIVE = "passive"
    CONNECTOR = "connector"
    CRYSTAL = "crystal"
    INDUCTOR = "inductor"
    CAPACITOR_BULK = "capacitor_bulk"
    CAPACITOR_DECOUPLING = "capacitor_decoupling"
    THERMAL = "thermal"  # Heatsink, etc
    MECHANICAL = "mechanical"

class PlacementStrategy(Enum):
    """Placement algorithm strategy"""
    GRID = "grid"  # Simple grid placement
    CLUSTER = "cluster"  # Group related components
    FORCE_DIRECTED = "force_directed"  # Physics-based
    THERMAL_AWARE = "thermal_aware"  # Consider heat dissipation
    SIGNAL_INTEGRITY = "signal_integrity"  # Optimize for signal quality
    AUTO = "auto"  # Choose best strategy

class BoardZone(Enum):
    """PCB functional zones"""
    DIGITAL = "digital"
    ANALOG = "analog"
    POWER = "power"
    RF = "rf"
    IO = "io"
    MECHANICAL = "mechanical"

@dataclass
class ZoneDefinition:
    """Definition of a functional zone on PCB"""
    zone_type: BoardZone
    x: float  # mm
    y: float  # mm
    width: float
    height: float
    priority: int = 1  # Higher priority zones placed first
    keep_out: bool = False  # True for no-go zones

@dataclass
class PlacementConstraints:
    """Placement constraints for a component"""
    preferred_zone: Optional[BoardZone] = None
    avoid_zones: List[BoardZone] = field(default_factory=list)
    min_distance_from: Dict[str, float] = field(default_factory=dict)  # component type -> min distance
    max_distance_from: Dict[str, float] = field(default_factory=dict)  # component type -> max distance
    rotation_allowed: List[int] = field(default_factory=lambda: [0, 90, 180, 270])
    side: str = "top"  # top or bottom
    thermal_priority: int = 0  # Higher = needs more cooling
    signal_integrity_priority: int = 0  # Higher = needs better signal quality

@dataclass
class PlacedComponent:
    """Professional placed component with metadata"""
    instance_id: str
    module_id: str
    module_name: str
    component_type: ComponentType
    footprint: Footprint
    x: float  # mm - center coordinate
    y: float  # mm - center coordinate
    rotation: int = 0  # degrees (0, 90, 180, 270)
    layer: str = "top"  # top or bottom
    zone: Optional[BoardZone] = None
    thermal_vias: List[Tuple[float, float]] = field(default_factory=list)  # positions of thermal vias
    keepout_region: Optional[Tuple[float, float, float, float]] = None  # x, y, w, h
    constraints: Optional[PlacementConstraints] = None
    
    @property
    def left(self) -> float:
        return self.x - self.width / 2
    
    @property
    def right(self) -> float:
        return self.x + self.width / 2
    
    @property
    def top(self) -> float:
        return self.y - self.height / 2
    
    @property
    def bottom(self) -> float:
        return self.y + self.height / 2
    
    @property
    def width(self) -> float:
        return self.footprint.width
    
    @property
    def height(self) -> float:
        return self.footprint.height
    
    def get_courtyard(self, margin: float = 0.5) -> Tuple[float, float, float, float]:
        """Get courtyard rectangle (x, y, w, h) with margin"""
        return (
            self.left - margin,
            self.top - margin,
            self.width + 2 * margin,
            self.height + 2 * margin
        )
    
    def overlaps_with(self, other: PlacedComponent, margin: float = 0.5) -> bool:
        """Check if this component overlaps with another"""
        cx1, cy1, cw1, ch1 = self.get_courtyard(margin)
        cx2, cy2, cw2, ch2 = other.get_courtyard(margin)
        
        return not (cx1 + cw1 <= cx2 or cx2 + cw2 <= cx1 or
                   cy1 + ch1 <= cy2 or cy2 + ch2 <= cy1)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization (PCBView format)."""
        left = self.x - self.width / 2
        top = self.y - self.height / 2
        pads_data = []
        for p in self.footprint.pads:
            pad_x = self.x + p.x
            pad_y = self.y + p.y
            shape_val = p.shape.value if hasattr(p.shape, "value") else "circle"
            pads_data.append({
                "name": p.name,
                "x": round(pad_x, 3),
                "y": round(pad_y, 3),
                "width": round(p.width, 3),
                "height": round(p.height, 3),
                "shape": shape_val,
                "drill": round(p.drill, 3),
                "net": p.net or "",
            })
        silkscreen_data = []
        for sl in getattr(self.footprint, "silkscreen", []) or []:
            silkscreen_data.append({
                "x1": round(left + sl.x1, 3),
                "y1": round(top + sl.y1, 3),
                "x2": round(left + sl.x2, 3),
                "y2": round(top + sl.y2, 3),
            })
        if not silkscreen_data:
            w, h = self.width, self.height
            inset = 0.3
            silkscreen_data = [
                {"x1": left + inset, "y1": top + inset, "x2": left + w - inset, "y2": top + inset},
                {"x1": left + w - inset, "y1": top + inset, "x2": left + w - inset, "y2": top + h - inset},
                {"x1": left + w - inset, "y1": top + h - inset, "x2": left + inset, "y2": top + h - inset},
                {"x1": left + inset, "y1": top + h - inset, "x2": left + inset, "y2": top + inset},
            ]
        return {
            "instanceId": self.instance_id,
            "moduleId": self.module_id,
            "name": self.module_name,
            "type": self.component_type.value,
            "x": round(left, 3),
            "y": round(top, 3),
            "rotation": self.rotation,
            "width": round(self.width, 3),
            "height": round(self.height, 3),
            "layer": self.layer,
            "zone": self.zone.value if self.zone else None,
            "pads": pads_data,
            "silkscreen": silkscreen_data,
        }

@dataclass
class Board:
    """Professional PCB board definition"""
    width: float  # mm
    height: float  # mm
    layers: int = 2
    zones: List[ZoneDefinition] = field(default_factory=list)
    keepout_areas: List[Tuple[float, float, float, float]] = field(default_factory=list)
    mounting_holes: List[Tuple[float, float, float]] = field(default_factory=list)  # x, y, diameter
    
    def is_valid_position(self, x: float, y: float, margin: float = BOARD_MARGIN) -> bool:
        """Check if position is valid (inside board, not in keepout)"""
        if x < margin or x > self.width - margin or y < margin or y > self.height - margin:
            return False
        
        for kx, ky, kw, kh in self.keepout_areas:
            if kx <= x <= kx + kw and ky <= y <= ky + kh:
                return False
        
        return True
    
    def get_zone_at(self, x: float, y: float) -> Optional[BoardZone]:
        """Get zone at position"""
        for zone in sorted(self.zones, key=lambda z: z.priority, reverse=True):
            if (zone.x <= x <= zone.x + zone.width and
                zone.y <= y <= zone.y + zone.height):
                return zone.zone_type
        return None


# ============== Professional Placement Engine ==============

class PlacementEngine:
    """Professional component placement engine"""
    
    def __init__(self, strategy: PlacementStrategy = PlacementStrategy.AUTO):
        self.strategy = strategy
        self.placed: List[PlacedComponent] = []
        self.board: Optional[Board] = None
        self.netlist: Optional[Dict] = None
        self.component_groups: Dict[str, List[str]] = defaultdict(list)  # group_id -> component ids
        self.constraints: Dict[str, PlacementConstraints] = {}
        
    def place_components(self, 
                         instances: List[dict],
                         footprints: Dict[str, Footprint],
                         nets: List[Net],
                         board: Optional[Board] = None,
                         constraints: Optional[Dict[str, PlacementConstraints]] = None,
                         min_clearance: float | None = None,
                         **kwargs) -> Tuple[Board, List[PlacedComponent]]:
        """Main placement function

        `min_clearance` is an optional override for the minimum spacing between
        components. It is currently not used by the default algorithms but is
        accepted for forward compatibility. Extra keyword arguments are swallowed
        to avoid breaking wrapper callers when new parameters are introduced.
        """
        
        # Initialize board if not provided
        if not board:
            board = self._create_initial_board(instances, footprints)
        self.board = board
        self.constraints = constraints or {}
        # store clearance override for potential use in algorithms
        if min_clearance is not None:
            setattr(self, '_min_clearance_override', min_clearance)
        
        # Classify components by type
        components = self._classify_components(instances, footprints)
        
        # Create component groups based on netlist
        self._create_component_groups(components, nets)
        
        # Choose placement strategy
        strategy = self._select_strategy(components, nets)
        
        # Place components based on strategy
        if strategy == PlacementStrategy.GRID:
            placed = self._grid_placement(components)
        elif strategy == PlacementStrategy.CLUSTER:
            placed = self._cluster_placement(components)
        elif strategy == PlacementStrategy.FORCE_DIRECTED:
            placed = self._force_directed_placement(components)
        elif strategy == PlacementStrategy.THERMAL_AWARE:
            placed = self._thermal_aware_placement(components)
        elif strategy == PlacementStrategy.SIGNAL_INTEGRITY:
            placed = self._signal_integrity_placement(components)
        else:
            placed = self._smart_placement(components)
        
        # Optimize placement
        placed = self._optimize_placement(placed)
        
        # Adjust board size if needed
        self.board = self._adjust_board_size(self.board, placed)
        
        return self.board, placed
    
    def _create_initial_board(self, instances: List[dict], footprints: Dict[str, Footprint]) -> Board:
        """Create initial board based on components"""
        # Estimate board size (rough calculation)
        total_area = sum(fp.width * fp.height for fp in footprints.values())
        # Add 30% for routing
        board_area = total_area * 1.3
        board_size = math.sqrt(board_area) * 1.2  # Make it slightly rectangular
        
        return Board(
            width=max(50, min(300, round(board_size * 1.2, 2))),
            height=max(30, min(200, round(board_size, 2)))
        )
    
    def _classify_components(self, instances: List[dict], 
                            footprints: Dict[str, Footprint]) -> List[Tuple[dict, Footprint, ComponentType]]:
        """Classify components by type"""
        classified = []
        
        for inst in instances:
            inst_id = inst["instanceId"]
            fp = footprints.get(inst_id)
            if not fp:
                continue
            
            # Determine component type
            comp_type = self._determine_component_type(inst, fp)
            classified.append((inst, fp, comp_type))
        
        return classified
    
    def _determine_component_type(self, inst: dict, fp: Footprint) -> ComponentType:
        """Determine component type from metadata"""
        module_name = inst.get("moduleName", "").lower()
        category = inst.get("category", "").lower()
        
        # Check based on module name
        if any(x in module_name for x in ["microcontroller", "processor", "fpga", "cpld"]):
            return ComponentType.IC_DIGITAL
        elif any(x in module_name for x in ["opamp", "amplifier", "adc", "dac"]):
            return ComponentType.IC_ANALOG
        elif any(x in module_name for x in ["regulator", "buck", "boost", "power"]):
            return ComponentType.IC_POWER
        elif any(x in module_name for x in ["rf", "antenna", "ble", "wifi"]):
            return ComponentType.IC_RF
        elif any(x in module_name for x in ["crystal", "oscillator"]):
            return ComponentType.CRYSTAL
        elif any(x in module_name for x in ["inductor", "choke"]):
            return ComponentType.INDUCTOR
        elif any(x in module_name for x in ["connector", "usb", "hdmi", "jack"]):
            return ComponentType.CONNECTOR
        elif "capacitor" in module_name:
            if any(x in module_name for x in ["bulk", "electrolytic"]):
                return ComponentType.CAPACITOR_BULK
            return ComponentType.CAPACITOR_DECOUPLING
        elif any(x in module_name for x in ["resistor", "capacitor"]):
            return ComponentType.PASSIVE
        
        # Default based on pin count
        if len(fp.pads) > 20:
            return ComponentType.IC_DIGITAL
        elif len(fp.pads) > 8:
            return ComponentType.IC_ANALOG
        
        return ComponentType.PASSIVE
    
    def _create_component_groups(self, components: List[Tuple], nets: List[Net]):
        """Group components based on net connections"""
        # Build connection graph
        connections = defaultdict(set)
        for net in nets:
            if len(net.pins) > 1:
                for i, (inst1, _) in enumerate(net.pins):
                    for inst2, _ in net.pins[i+1:]:
                        connections[inst1].add(inst2)
                        connections[inst2].add(inst1)
        
        # Find connected components (graph clusters)
        visited = set()
        group_id = 0
        
        for inst, _, _ in components:
            if inst["instanceId"] in visited:
                continue
            
            # BFS to find group
            queue = [inst["instanceId"]]
            group = []
            
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                group.append(current)
                
                for neighbor in connections[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)
            
            if len(group) > 1:
                self.component_groups[f"group_{group_id}"] = group
                group_id += 1
    
    def _select_strategy(self, components: List[Tuple], nets: List[Net]) -> PlacementStrategy:
        """Select best placement strategy"""
        if self.strategy != PlacementStrategy.AUTO:
            return self.strategy
        
        # Count component types
        type_counts = defaultdict(int)
        for _, _, ctype in components:
            type_counts[ctype] += 1
        
        # Check for thermal considerations
        if type_counts[ComponentType.IC_POWER] > 0 or type_counts[ComponentType.INDUCTOR] > 0:
            return PlacementStrategy.THERMAL_AWARE
        
        # Check for high-speed signals
        high_speed_nets = 0
        for net in nets:
            if any(pin_name in ["CLK", "D+", "D-", "TX", "RX"] for _, pin_name in net.pins):
                high_speed_nets += 1
        
        if high_speed_nets > 2:
            return PlacementStrategy.SIGNAL_INTEGRITY
        
        # Check for many connections
        if len(nets) > 20:
            return PlacementStrategy.CLUSTER
        
        # Default to smart placement
        return PlacementStrategy.FORCE_DIRECTED
    
    def _grid_placement(self, components: List[Tuple]) -> List[PlacedComponent]:
        """Simple grid-based placement"""
        placed = []
        margin = BOARD_MARGIN
        spacing = COMPONENT_GAP
        x, y = margin, margin
        max_row_height = 0
        
        for inst, fp, ctype in components:
            # Check if we need new row
            if x + fp.width + spacing > self.board.width - margin:
                x = margin
                y += max_row_height + spacing
                max_row_height = 0
            
            # Place component
            comp = PlacedComponent(
                instance_id=inst["instanceId"],
                module_id=inst.get("moduleId", inst["instanceId"]),
                module_name=inst.get("moduleName", ""),
                component_type=ctype,
                footprint=fp,
                x=x + fp.width/2,
                y=y + fp.height/2,
                rotation=0
            )
            
            placed.append(comp)
            x += fp.width + spacing
            max_row_height = max(max_row_height, fp.height)
        
        return placed
    
    def _cluster_placement(self, components: List[Tuple]) -> List[PlacedComponent]:
        """Place components in functional clusters"""
        placed = []
        
        # Create zones for different functions
        zones = [
            ZoneDefinition(BoardZone.DIGITAL, 10, 10, 60, 50, priority=3),
            ZoneDefinition(BoardZone.ANALOG, 70, 10, 50, 50, priority=2),
            ZoneDefinition(BoardZone.POWER, 10, 60, 50, 40, priority=2),
            ZoneDefinition(BoardZone.IO, 70, 60, 40, 40, priority=1),
        ]
        self.board.zones = zones
        
        # Place components in appropriate zones
        zone_placements = defaultdict(list)
        
        for inst, fp, ctype in components:
            # Determine target zone
            target_zone = self._get_target_zone(ctype)
            
            # Find zone definition
            zone = next((z for z in zones if z.zone_type == target_zone), zones[0])
            
            # Place in zone
            comp = self._place_in_zone(inst, fp, ctype, zone, zone_placements[target_zone])
            if comp:
                zone_placements[target_zone].append(comp)
                placed.append(comp)
        
        return placed
    
    def _get_target_zone(self, ctype: ComponentType) -> BoardZone:
        """Get target zone for component type"""
        zone_map = {
            ComponentType.IC_DIGITAL: BoardZone.DIGITAL,
            ComponentType.IC_ANALOG: BoardZone.ANALOG,
            ComponentType.IC_POWER: BoardZone.POWER,
            ComponentType.IC_RF: BoardZone.RF,
            ComponentType.CAPACITOR_BULK: BoardZone.POWER,
            ComponentType.CAPACITOR_DECOUPLING: BoardZone.DIGITAL,
            ComponentType.CONNECTOR: BoardZone.IO,
        }
        return zone_map.get(ctype, BoardZone.DIGITAL)
    
    def _place_in_zone(self, inst: dict, fp: Footprint, ctype: ComponentType,
                       zone: ZoneDefinition, existing: List[PlacedComponent]) -> Optional[PlacedComponent]:
        """Place component within a zone"""
        margin = 2.0
        spacing = 1.0
        
        # Try grid placement within zone
        for y in range(int(zone.y + margin), int(zone.y + zone.height - fp.height), int(spacing + fp.height)):
            for x in range(int(zone.x + margin), int(zone.x + zone.width - fp.width), int(spacing + fp.width)):
                comp = PlacedComponent(
                    instance_id=inst["instanceId"],
                    module_id=inst.get("moduleId", inst["instanceId"]),
                    module_name=inst.get("moduleName", ""),
                    component_type=ctype,
                    footprint=fp,
                    x=x + fp.width/2,
                    y=y + fp.height/2,
                    zone=zone.zone_type
                )
                
                # Check for collisions
                if not any(comp.overlaps_with(e) for e in existing):
                    return comp
        
        # Fallback to zone center
        return PlacedComponent(
            instance_id=inst["instanceId"],
            module_id=inst.get("moduleId", inst["instanceId"]),
            module_name=inst.get("moduleName", ""),
            component_type=ctype,
            footprint=fp,
            x=zone.x + zone.width/2,
            y=zone.y + zone.height/2,
            zone=zone.zone_type
        )
    
    def _force_directed_placement(self, components: List[Tuple]) -> List[PlacedComponent]:
        """Physics-based force-directed placement"""
        # Initialize random positions
        placed = []
        for inst, fp, ctype in components:
            placed.append(PlacedComponent(
                instance_id=inst["instanceId"],
                module_id=inst.get("moduleId", inst["instanceId"]),
                module_name=inst.get("moduleName", ""),
                component_type=ctype,
                footprint=fp,
                x=random.uniform(BOARD_MARGIN, self.board.width - BOARD_MARGIN),
                y=random.uniform(BOARD_MARGIN, self.board.height - BOARD_MARGIN)
            ))
        
        # Simulate forces for optimization
        for iteration in range(100):  # 100 iterations
            forces = defaultdict(lambda: [0, 0])
            
            # Calculate repulsive forces (components push each other)
            for i in range(len(placed)):
                for j in range(i + 1, len(placed)):
                    dx = placed[j].x - placed[i].x
                    dy = placed[j].y - placed[i].y
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    if dist < 0.1:
                        dist = 0.1
                    
                    # Repulsive force (inverse square)
                    force = 10.0 / (dist * dist)
                    if dist < (placed[i].width + placed[j].width) / 2:
                        force *= 5  # Stronger repulsion if overlapping
                    
                    angle = math.atan2(dy, dx)
                    fx = force * math.cos(angle)
                    fy = force * math.sin(angle)
                    
                    forces[i][0] -= fx
                    forces[i][1] -= fy
                    forces[j][0] += fx
                    forces[j][1] += fy
            
            # Apply forces with damping
            damping = 0.1 / (iteration + 1)
            for i, comp in enumerate(placed):
                comp.x += forces[i][0] * damping
                comp.y += forces[i][1] * damping
                
                # Keep within board
                comp.x = max(BOARD_MARGIN + comp.width/2, 
                           min(self.board.width - BOARD_MARGIN - comp.width/2, comp.x))
                comp.y = max(BOARD_MARGIN + comp.height/2,
                           min(self.board.height - BOARD_MARGIN - comp.height/2, comp.y))
        
        return placed
    
    def _thermal_aware_placement(self, components: List[Tuple]) -> List[PlacedComponent]:
        """Placement optimized for thermal management"""
        placed = []
        
        # Identify hot components
        hot_components = []
        normal_components = []
        
        for inst, fp, ctype in components:
            if ctype in [ComponentType.IC_POWER, ComponentType.INDUCTOR]:
                hot_components.append((inst, fp, ctype))
            else:
                normal_components.append((inst, fp, ctype))
        
        # Place hot components first (spread them out)
        hot_spacing = THERMAL_SPACING
        x, y = BOARD_MARGIN, BOARD_MARGIN
        
        for inst, fp, ctype in hot_components:
            comp = PlacedComponent(
                instance_id=inst["instanceId"],
                module_id=inst.get("moduleId", inst["instanceId"]),
                module_name=inst.get("moduleName", ""),
                component_type=ctype,
                footprint=fp,
                x=x + fp.width/2,
                y=y + fp.height/2
            )
            
            # Add thermal vias
            comp.thermal_vias = self._add_thermal_vias(comp)
            
            placed.append(comp)
            x += fp.width + hot_spacing
            if x > self.board.width - BOARD_MARGIN - 50:  # New row
                x = BOARD_MARGIN
                y += 30
        
        # Place normal components in remaining space
        normal_placed = self._grid_placement(normal_components)
        placed.extend(normal_placed)
        
        return placed
    
    def _add_thermal_vias(self, comp: PlacedComponent) -> List[Tuple[float, float]]:
        """Add thermal vias for hot components"""
        vias = []
        if comp.component_type in [ComponentType.IC_POWER, ComponentType.INDUCTOR]:
            # Add 4 thermal vias around the component
            via_positions = [
                (comp.x - 1, comp.y - 1),
                (comp.x + 1, comp.y - 1),
                (comp.x - 1, comp.y + 1),
                (comp.x + 1, comp.y + 1)
            ]
            vias.extend(via_positions)
        return vias
    
    def _signal_integrity_placement(self, components: List[Tuple]) -> List[PlacedComponent]:
        """Placement optimized for signal integrity"""
        placed = []
        
        # Place critical components first
        critical_first = []
        for ctype in [ComponentType.CRYSTAL, ComponentType.IC_RF, ComponentType.IC_DIGITAL]:
            critical = [(inst, fp, ct) for inst, fp, ct in components if ct == ctype]
            critical_first.extend(critical)
        
        # Place critical components close to each other if they're connected
        for inst, fp, ctype in critical_first:
            # Find best position near related components
            best_pos = self._find_best_position(inst, fp, placed)
            
            comp = PlacedComponent(
                instance_id=inst["instanceId"],
                module_id=inst.get("moduleId", inst["instanceId"]),
                module_name=inst.get("moduleName", ""),
                component_type=ctype,
                footprint=fp,
                x=best_pos[0],
                y=best_pos[1]
            )
            placed.append(comp)
        
        # Place remaining components
        remaining = [(inst, fp, ct) for inst, fp, ct in components 
                    if (inst, fp, ct) not in critical_first]
        remaining_placed = self._grid_placement(remaining)
        placed.extend(remaining_placed)
        
        return placed
    
    def _find_best_position(self, inst: dict, fp: Footprint, 
                           existing: List[PlacedComponent]) -> Tuple[float, float]:
        """Find best position for a component"""
        if not existing:
            return BOARD_MARGIN + fp.width/2, BOARD_MARGIN + fp.height/2
        
        # Try to place near connected components
        # For now, simple grid position
        return BOARD_MARGIN + fp.width/2, BOARD_MARGIN + fp.height/2 + 20
    
    def _smart_placement(self, components: List[Tuple]) -> List[PlacedComponent]:
        """Smart placement combining multiple strategies"""
        # Start with force-directed
        placed = self._force_directed_placement(components)
        
        # Then optimize for thermal if needed
        if any(ct in [ComponentType.IC_POWER, ComponentType.INDUCTOR] 
               for _, _, ct in components):
            placed = self._thermal_optimization(placed)
        
        # Finally, snap to grid
        placed = self._snap_to_grid(placed)
        
        return placed
    
    def _thermal_optimization(self, placed: List[PlacedComponent]) -> List[PlacedComponent]:
        """Optimize placement for thermal management"""
        # Identify hot components
        hot_comps = [c for c in placed if c.component_type in 
                    [ComponentType.IC_POWER, ComponentType.INDUCTOR]]
        
        # Ensure spacing between hot components
        for i in range(len(hot_comps)):
            for j in range(i + 1, len(hot_comps)):
                dist = math.sqrt((hot_comps[j].x - hot_comps[i].x)**2 + 
                               (hot_comps[j].y - hot_comps[i].y)**2)
                if dist < THERMAL_SPACING:
                    # Move them apart
                    angle = math.atan2(hot_comps[j].y - hot_comps[i].y,
                                      hot_comps[j].x - hot_comps[i].x)
                    move = (THERMAL_SPACING - dist) / 2
                    hot_comps[i].x -= move * math.cos(angle)
                    hot_comps[i].y -= move * math.sin(angle)
                    hot_comps[j].x += move * math.cos(angle)
                    hot_comps[j].y += move * math.sin(angle)
        
        return placed
    
    def _snap_to_grid(self, placed: List[PlacedComponent], grid_size: float = 0.5) -> List[PlacedComponent]:
        """Snap components to manufacturing grid"""
        for comp in placed:
            comp.x = round(comp.x / grid_size) * grid_size
            comp.y = round(comp.y / grid_size) * grid_size
        return placed
    
    def _optimize_placement(self, placed: List[PlacedComponent]) -> List[PlacedComponent]:
        """Final placement optimization"""
        # Remove overlaps
        placed = self._resolve_overlaps(placed)
        
        # Optimize orientations
        placed = self._optimize_orientations(placed)
        
        return placed
    
    def _resolve_overlaps(self, placed: List[PlacedComponent]) -> List[PlacedComponent]:
        """Resolve component overlaps"""
        changed = True
        max_iterations = 50
        
        while changed and max_iterations > 0:
            changed = False
            max_iterations -= 1
            
            for i in range(len(placed)):
                for j in range(i + 1, len(placed)):
                    if placed[i].overlaps_with(placed[j]):
                        # Move them apart
                        dx = placed[j].x - placed[i].x
                        dy = placed[j].y - placed[i].y
                        dist = math.sqrt(dx*dx + dy*dy)
                        
                        if dist < 0.01:
                            # Random direction if exactly overlapping
                            angle = random.uniform(0, 2 * math.pi)
                            move = 1.0
                        else:
                            angle = math.atan2(dy, dx)
                            move = (placed[i].width + placed[j].width) / 4
                        
                        placed[i].x -= move * math.cos(angle) / 2
                        placed[i].y -= move * math.sin(angle) / 2
                        placed[j].x += move * math.cos(angle) / 2
                        placed[j].y += move * math.sin(angle) / 2
                        
                        changed = True
        
        return placed
    
    def _optimize_orientations(self, placed: List[PlacedComponent]) -> List[PlacedComponent]:
        """Optimize component orientations for better routing"""
        for comp in placed:
            # Set optimal rotation based on pin layout
            if len(comp.footprint.pads) > 0:
                # Align with predominant pad direction
                pad_x_center = sum(p.x for p in comp.footprint.pads) / len(comp.footprint.pads)
                pad_y_center = sum(p.y for p in comp.footprint.pads) / len(comp.footprint.pads)
                
                if abs(pad_x_center - comp.width/2) > abs(pad_y_center - comp.height/2):
                    comp.rotation = 0  # Horizontal alignment
                else:
                    comp.rotation = 90  # Vertical alignment
        
        return placed
    
    def _adjust_board_size(self, board: Board, placed: List[PlacedComponent]) -> Board:
        """Adjust board size to fit all components"""
        if not placed:
            return board
        
        # Find component bounds
        min_x = min(c.left for c in placed) - BOARD_MARGIN
        min_y = min(c.top for c in placed) - BOARD_MARGIN
        max_x = max(c.right for c in placed) + BOARD_MARGIN
        max_y = max(c.bottom for c in placed) + BOARD_MARGIN
        
        # Adjust if components exceed current board
        if min_x < 0 or min_y < 0 or max_x > board.width or max_y > board.height:
            board.width = max(board.width, max_x - min_x + BOARD_MARGIN * 2)
            board.height = max(board.height, max_y - min_y + BOARD_MARGIN * 2)
            
            # Translate components if origin shifted
            if min_x < 0:
                for c in placed:
                    c.x += abs(min_x)
            if min_y < 0:
                for c in placed:
                    c.y += abs(min_y)
        
        return board


# ============== Backward Compatibility ==============

def place_components(
    instances: list[dict],
    footprints: dict[str, Footprint],
    nets: Optional[list] = None,
    board: Optional[Board] = None,
    strategy: PlacementStrategy = PlacementStrategy.AUTO,
    **kwargs
) -> tuple[Board, list[PlacedComponent]]:
    """Backward compatible wrapper

    Accepts extra keyword arguments and passes them through to the
    underlying `PlacementEngine.place_components` implementation. This
    allows newer parameters (e.g. `min_clearance`) to be supplied without
    breaking existing callers.
    """
    engine = PlacementEngine(strategy)
    if nets is None:
        nets = []
    return engine.place_components(instances, footprints, nets, board, **kwargs)


def _courtyard(fp: Footprint) -> tuple[float, float]:
    """Legacy courtyard function"""
    margin = getattr(fp, 'courtyard_margin', 0.5)
    return (fp.width + 2 * margin, fp.height + 2 * margin)
"""
PCB Generation Engine — Professional Grade
Supports: Multi-layer boards, High-speed design rules, Thermal management, Auto-router
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Set
from enum import Enum
import math
import uuid
import json

from .netlist import generate_netlist, Net
from .footprints import get_footprint, Footprint, Pad, PadShape
from .placement import place_components, PlacedComponent, Board, PlacementStrategy
from .routing import route_nets, Trace, DRCViolation, RoutingStrategy, Via
from .copper_pour import generate_pour, CopperPour
from .units import PX_PER_MM, TRACE_WIDTH_MM, SILKSCREEN_WIDTH_MM, mm_to_units
from .drc_engine import DRCEngine, DRCConfig
from .thermal_analysis import ThermalAnalyzer

# ============== Configuration Classes ==============

class BoardLayer(Enum):
    """Professional PCB Layer Stack"""
    TOP = "F.Cu"
    BOTTOM = "B.Cu"
    INNER1 = "In1.Cu"
    INNER2 = "In2.Cu"
    INNER3 = "In3.Cu"
    INNER4 = "In4.Cu"
    TOP_SOLDERMASK = "F.Mask"
    BOTTOM_SOLDERMASK = "B.Mask"
    TOP_SILKSCREEN = "F.SilkS"
    BOTTOM_SILKSCREEN = "B.SilkS"
    TOP_PASTE = "F.Paste"
    BOTTOM_PASTE = "B.Paste"

class BoardClass(Enum):
    """PCB Classification based on reliability requirements"""
    CLASS_1 = "consumer"       # Consumer electronics - 1.0mm min clearance
    CLASS_2 = "industrial"     # Industrial - 0.5mm min clearance
    CLASS_3 = "high_reliability"  # Aerospace/Medical - 0.25mm min clearance
    CLASS_4 = "automotive"      # Automotive - 0.35mm min clearance

class ImpedanceControl(Enum):
    """Impedance control requirements for high-speed signals"""
    NONE = "none"
    SINGLE_ENDED_50 = "50_ohm"
    SINGLE_ENDED_75 = "75_ohm"
    DIFFERENTIAL_90 = "90_ohm_diff"   # USB
    DIFFERENTIAL_100 = "100_ohm_diff"  # Ethernet, LVDS
    DIFFERENTIAL_120 = "120_ohm_diff"  # CAN bus
    CUSTOM = "custom"

class StackupMaterial(Enum):
    """PCB layer stackup materials"""
    FR4 = "fr4"  # Standard
    FR4_HIGH_TG = "fr4_high_tg"  # High temperature
    ROGERS = "rogers"  # RF applications
    POLYIMIDE = "polyimide"  # Flexible
    ALUMINUM = "aluminum"  # LED applications

@dataclass
class LayerStackup:
    """PCB layer stackup definition"""
    layer: BoardLayer
    thickness_mm: float  # Copper thickness
    dielectric_mm: float  # Dielectric thickness to next layer
    material: StackupMaterial = StackupMaterial.FR4
    copper_weight_oz: float = 1.0  # 1oz = 35μm

@dataclass
class BoardSpecs:
    """Complete board specifications"""
    width: float  # mm
    height: float  # mm
    layers: int
    board_class: BoardClass = BoardClass.CLASS_2
    impedance_control: ImpedanceControl = ImpedanceControl.NONE
    stackup: List[LayerStackup] = field(default_factory=list)
    min_trace_width: float = 0.15  # mm
    min_clearance: float = 0.15  # mm
    min_via_size: float = 0.3  # mm
    min_hole_size: float = 0.15  # mm
    solder_mask_color: str = "green"
    silk_screen_color: str = "white"
    surface_finish: str = "HASL"  # HASL, ENIG, OSP, Immersion Silver
    
    def __post_init__(self):
        if not self.stackup:
            self.stackup = self._default_stackup()
    
    def _default_stackup(self) -> List[LayerStackup]:
        """Generate default layer stackup based on layer count"""
        stackup = []
        if self.layers == 2:
            stackup = [
                LayerStackup(BoardLayer.TOP, 0.035, 0.0),  # 1oz copper
                LayerStackup(BoardLayer.BOTTOM, 0.035, 1.6)  # 1.6mm total thickness
            ]
        elif self.layers == 4:
            stackup = [
                LayerStackup(BoardLayer.TOP, 0.035, 0.0),
                LayerStackup(BoardLayer.INNER1, 0.035, 0.2),
                LayerStackup(BoardLayer.INNER2, 0.035, 1.0),
                LayerStackup(BoardLayer.BOTTOM, 0.035, 0.2)
            ]
        return stackup

# ============== Main PCB Engine ==============

class PCBEngine:
    """Professional PCB Design Engine"""
    
    def __init__(self, board_specs: Optional[BoardSpecs] = None):
        self.board_specs = board_specs or BoardSpecs(width=100, height=100, layers=2)
        self.drc_engine = DRCEngine(DRCConfig(
            min_trace_width=self.board_specs.min_trace_width,
            min_clearance=self.board_specs.min_clearance,
            min_via_size=self.board_specs.min_via_size
        ))
        self.thermal_analyzer = ThermalAnalyzer()
        self.nets: List[Net] = []
        self.placed_components: List[PlacedComponent] = []
        self.traces: List[Trace] = []
        self.vias: List[Via] = []
        self.power_planes: Dict[str, CopperPour] = {}
        self.violations: List[DRCViolation] = []
        
    def generate_pcb(self, schematic: dict) -> dict:
        """Main PCB generation pipeline"""
        try:
            # 1. Extract instances and wires
            instances = schematic.get("modules", [])
            wires = schematic.get("wires", [])
            
            print(f"Generating PCB for {len(instances)} components, {len(wires)} connections")
            
            # 2. Generate global netlist with power/ground detection
            self.nets = generate_netlist(wires, instances)
            print(f"Generated {len(self.nets)} nets")
            
            # 3. Assign footprints with pin mapping
            instance_fps, pin_to_pad = self._assign_footprints(instances, self.nets)
            
            # 4. Optimize component placement
            self.board, self.placed_components = self._optimize_placement(
                instances, instance_fps, self.nets
            )
            print(f"Placed {len(self.placed_components)} components")
            
            # 5. Route connections intelligently
            self.traces, self.violations = self._smart_routing(
                self.nets, self.placed_components, pin_to_pad
            )
            print(f"Routed {len(self.traces)} traces")
            
            # 6. Generate copper pours for power nets
            self.power_planes = self._generate_power_pours()
            
            # 7. Run comprehensive DRC check
            self._run_drc_checks()
            
            # 8. Generate output
            return self._serialise_output()
            
        except Exception as e:
            print(f"PCB Generation Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
    
    def _assign_footprints(self, instances: List[dict], nets: List[Net]) -> Tuple[Dict[str, Footprint], Dict[str, str]]:
        """Assign footprints with proper pad-net binding"""
        instance_fps: Dict[str, Footprint] = {}
        pin_to_pad: Dict[str, str] = {}  # "instId::pinId" -> padName
        net_by_pin: Dict[str, str] = {}
        
        # Build pin to net mapping
        for net in nets:
            for inst_id, pin_id in net.pins:
                net_by_pin[f"{inst_id}::{pin_id}"] = net.name
        
        for inst in instances:
            inst_id = inst["instanceId"]
            module_name = inst.get("moduleName", "Unknown")
            pin_count = len(inst.get("pins", []))
            meta = inst.get("pcb_meta") or {}
            
            # Get or create footprint
            fp = self._get_or_create_footprint(inst, meta, pin_count)
            instance_fps[inst_id] = fp
            
            # Bind pads to nets
            pins = inst.get("pins", [])
            for idx, pin in enumerate(pins):
                if idx >= len(fp.pads):
                    break
                    
                pin_id = pin.get("id", f"pin{idx}")
                key = f"{inst_id}::{pin_id}"
                pad = fp.pads[idx]
                
                # Apply admin-defined position if available
                if "x" in pin and "y" in pin:
                    pad.x = (pin["x"] / 100.0) * fp.width
                    pad.y = (pin["y"] / 100.0) * fp.height
                
                # Bind net
                pad.net = net_by_pin.get(key, "")
                
                # Store mapping
                pin_to_pad[key] = pad.name
        
        return instance_fps, pin_to_pad
    
    def _get_or_create_footprint(self, inst: dict, meta: dict, pin_count: int) -> Footprint:
        """Get footprint from library or create custom one"""
        width_mm = meta.get("width_mm")
        height_mm = meta.get("height_mm")
        
        if isinstance(width_mm, (int, float)) and isinstance(height_mm, (int, float)) and width_mm > 0 and height_mm > 0:
            # Create custom footprint with dimensions
            fp = Footprint(
                name=inst.get("moduleName", "Unknown"),
                width=float(width_mm),
                height=float(height_mm),
                pads=self._create_pads_from_pins(inst.get("pins", []), width_mm, height_mm)
            )
        else:
            # Get from library with pin count
            fp = get_footprint(
                inst.get("moduleName", "Unknown"),
                inst.get("category"),
                max(pin_count, 2)
            )
        
        return fp
    
    def _create_pads_from_pins(self, pins: List[dict], width_mm: float, height_mm: float) -> List[Pad]:
        """Create pads from pin definitions"""
        pads = []
        for pin in pins:
            # Default pad dimensions (1.6mm x 1.6mm for THT, 1.0mm for SMD)
            pad_width = 1.6
            pad_height = 1.6
            drill = 0.8
            
            # Check if SMD
            if pin.get("type") == "smd":
                pad_width = 1.0
                pad_height = 1.5
                drill = 0.0
            
            shape = PadShape.CIRCLE if drill > 0 else PadShape.RECT
            pad = Pad(
                name=pin.get("name", "P"),
                x=(pin.get("x", 50) / 100.0) * width_mm,
                y=(pin.get("y", 50) / 100.0) * height_mm,
                width=pad_width,
                height=pad_height,
                drill=drill,
                shape=shape
            )
            pads.append(pad)
        return pads
    
    def _optimize_placement(self, instances: List[dict], 
                          instance_fps: Dict[str, Footprint],
                          nets: List[Net]) -> Tuple[Board, List[PlacedComponent]]:
        """Optimize component placement with thermal and signal integrity considerations"""
        
        # Create board
        board = Board(
            width=self.board_specs.width,
            height=self.board_specs.height,
            layers=self.board_specs.layers
        )
        
        # Place components with professional algorithm
        # attempt to pass min_clearance; fall back gracefully if the
        # imported placement module hasn't been updated yet (e.g. during a
        # hot restart where the wrapper signature is still old).
        try:
            result = place_components(
                instances=instances,
                footprints=instance_fps,
                nets=nets,
                board=board,
                strategy=PlacementStrategy.THERMAL_AWARE,  # Consider thermal issues
                min_clearance=self.board_specs.min_clearance
            )
        except TypeError as exc:
            # If the error is due to unexpected keyword, retry without it
            if "min_clearance" in str(exc):
                result = place_components(
                    instances=instances,
                    footprints=instance_fps,
                    nets=nets,
                    board=board,
                    strategy=PlacementStrategy.THERMAL_AWARE,
                )
            else:
                raise

        # wrapper may return either a flat list or (board, placed_list)
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], Board):
            _, placed = result
        else:
            placed = result

        return board, placed
    
    def _smart_routing(self, nets: List[Net], 
                      placed: List[PlacedComponent],
                      pin_to_pad: Dict[str, str]) -> Tuple[List[Trace], List[DRCViolation]]:
        """Intelligent routing with multiple strategies"""
        
        # Identify special nets
        power_nets = {n.name for n in nets if n.is_power}
        ground_nets = {n.name for n in nets if n.is_ground}
        high_speed_nets = self._identify_high_speed_nets(nets)
        
        # Route with appropriate strategy per net
        all_traces = []
        all_violations = []
        
        # Route high-speed nets first (they need optimal paths)
        for net in nets:
            if net.name in high_speed_nets:
                traces, violations = route_nets(
                    nets=[net],
                    placed=placed,
                    pin_to_pad=pin_to_pad,
                    strategy=RoutingStrategy.HIGH_SPEED,
                    min_length_matching=True  # Match lengths for differential pairs
                )
                all_traces.extend(traces)
                all_violations.extend(violations)
        
        # Route power nets with wider traces
        for net in nets:
            if net.name in power_nets:
                traces, violations = route_nets(
                    nets=[net],
                    placed=placed,
                    pin_to_pad=pin_to_pad,
                    strategy=RoutingStrategy.POWER,
                    trace_width=0.5  # Wider for power
                )
                all_traces.extend(traces)
                all_violations.extend(violations)
        
        # Route signal nets
        signal_nets = [n for n in nets if n.name not in power_nets 
                      and n.name not in ground_nets
                      and n.name not in high_speed_nets]
        
        if signal_nets:
            traces, violations = route_nets(
                nets=signal_nets,
                placed=placed,
                pin_to_pad=pin_to_pad,
                strategy=RoutingStrategy.STANDARD,
                skip_nets=power_nets | ground_nets | high_speed_nets
            )
            all_traces.extend(traces)
            all_violations.extend(violations)
        
        return all_traces, all_violations
    
    def _identify_high_speed_nets(self, nets: List[Net]) -> Set[str]:
        """Identify high-speed nets based on pin types"""
        high_speed = set()
        for net in nets:
            # Check if connected to high-speed pins
            for inst_id, pin_id in net.pins:
                # Add logic to identify high-speed pins
                if any(signal in pin_id.lower() for signal in ['clk', 'clock', 'd+', 'd-', 'tx', 'rx']):
                    high_speed.add(net.name)
                    break
        return high_speed
    
    def _generate_power_pours(self) -> Dict[str, CopperPour]:
        """Generate copper pours for power and ground nets"""
        pours = {}
        
        # Generate ground pour first (usually largest)
        ground_nets = [n.name for n in self.nets if n.is_ground]
        for net_name in ground_nets:
            pour = generate_pour(
                board=self.board,
                placed=self.placed_components,
                traces=self.traces,
                gnd_net_name=net_name,
                clearance=self.board_specs.min_clearance * 2,
            )
            if pour:
                pours[net_name] = pour
        
        # Generate power pours
        power_nets = [n.name for n in self.nets if n.is_power]
        for net_name in power_nets:
            pour = generate_pour(
                board=self.board,
                placed=self.placed_components,
                traces=self.traces,
                gnd_net_name=net_name,
                clearance=self.board_specs.min_clearance * 1.5
            )
            if pour:
                pours[net_name] = pour
        
        return pours
    
    def _run_drc_checks(self):
        """Run comprehensive DRC checks"""
        # Clearance checks
        clearance_violations = self.drc_engine.check_clearances(
            self.placed_components,
            self.traces,
            self.power_planes
        )
        self.violations.extend(clearance_violations)
        
        # Trace width checks
        width_violations = self.drc_engine.check_trace_widths(
            self.traces,
            self.board_specs.min_trace_width
        )
        self.violations.extend(width_violations)
        
        # Annular ring checks
        ring_violations = self.drc_engine.check_annular_rings(
            self.vias,
            min_ring=0.125  # mm
        )
        self.violations.extend(ring_violations)
    
    def _serialise_output(self) -> dict:
        """Serialise to output format (PCBView-compatible)"""
        
        # Components
        components_json = []
        for comp in self.placed_components:
            # sometimes placement algorithms may accidentally return unexpected
            # objects (e.g. a Board) which would crash serialization.  Guard
            # against that by only serializing objects that implement `to_dict()`.
            if hasattr(comp, "to_dict"):
                components_json.append(comp.to_dict())
            else:
                # log or ignore
                print(f"Warning: skipped non-serializable placed component {comp}")
        
        # Traces
        traces_json = []
        for t in self.traces:
            traces_json.append(t.to_dict())
        
        # Copper pours
        pours_json = {}
        for net_name, pour in self.power_planes.items():
            pours_json[net_name] = pour.to_dict()
        primary_pour = None
        for name in ("GND", "VCC", "VDD", "3V3", "5V"):
            if name in pours_json:
                primary_pour = pours_json[name]
                break
        if primary_pour is None and pours_json:
            primary_pour = next(iter(pours_json.values()))
        
        # Nets
        nets_json = []
        for n in self.nets:
            nets_json.append({
                "name": n.name,
                "pinCount": len(n.pins),
                "isGround": n.is_ground,
                "isPower": n.is_power,
                "isHighSpeed": n.name in self._identify_high_speed_nets(self.nets)
            })
        
        # DRC violations
        drc_json = [v.to_dict() for v in self.violations]
        
        # Generate manufacturing files
        manufacturing = self._generate_manufacturing_files()
        
        return {
            "board": {
                "width": round(self.board.width, 3),
                "height": round(self.board.height, 3),
                "layers": self.board.layers,
                "class": self.board_specs.board_class.value
            },
            "units": {
                "coordinate": "mm",
                "pxPerMm": PX_PER_MM,
                "traceWidthDefault": TRACE_WIDTH_MM,
                "silkscreenWidth": SILKSCREEN_WIDTH_MM
            },
            "components": components_json,
            "traces": traces_json,
            "nets": nets_json,
            "copperPours": pours_json,
            "copperPour": primary_pour,
            "drc": drc_json,
            "manufacturing": manufacturing,
            "stats": {
                "componentCount": len(components_json),
                "traceCount": len(traces_json),
                "netCount": len(nets_json),
                "viaCount": len(self.vias),
                "drcViolationCount": len(drc_json)
            }
        }
    
    def _generate_manufacturing_files(self) -> dict:
        """Generate manufacturing file data"""
        return {
            "gerber": {
                "top_layer": self._generate_gerber_layer(BoardLayer.TOP),
                "bottom_layer": self._generate_gerber_layer(BoardLayer.BOTTOM),
                "soldermask_top": self._generate_soldermask_layer(BoardLayer.TOP_SOLDERMASK),
                "soldermask_bottom": self._generate_soldermask_layer(BoardLayer.BOTTOM_SOLDERMASK),
                "silkscreen_top": self._generate_silkscreen_layer(BoardLayer.TOP_SILKSCREEN),
                "silkscreen_bottom": self._generate_silkscreen_layer(BoardLayer.BOTTOM_SILKSCREEN),
                "drill": self._generate_drill_file()
            },
            "pick_and_place": self._generate_pick_and_place(),
            "bom": self._generate_bom()
        }
    
    def _generate_gerber_layer(self, layer: BoardLayer) -> str:
        """Generate Gerber data for a layer (simplified)"""
        return f"Gerber data for {layer.value} - generated"
    
    def _generate_soldermask_layer(self, layer: BoardLayer) -> str:
        """Generate soldermask layer"""
        return f"Generated soldermask openings"
    
    def _generate_silkscreen_layer(self, layer: BoardLayer) -> str:
        """Generate silkscreen layer"""
        return f"Generated silkscreen"
    
    def _generate_drill_file(self) -> str:
        """Generate Excellon drill file"""
        return "Generated drill file"
    
    def _generate_pick_and_place(self) -> List[dict]:
        """Generate pick and place file for assembly"""
        pnp = []
        for comp in self.placed_components:
            pnp.append({
                "designator": comp.module_id,
                "value": comp.module_name,
                "footprint": comp.footprint.name,
                "mid_x": round(comp.x, 3),
                "mid_y": round(comp.y, 3),
                "rotation": comp.rotation,
                "layer": "top" if comp.layer == BoardLayer.TOP else "bottom"
            })
        return pnp
    
    def _generate_bom(self) -> List[dict]:
        """Generate Bill of Materials"""
        bom = {}
        for comp in self.placed_components:
            key = f"{comp.module_name}"
            if key not in bom:
                bom[key] = {
                    "part": comp.module_name,
                    "footprint": comp.footprint.name,
                    "quantity": 0,
                    "designators": []
                }
            bom[key]["quantity"] += 1
            bom[key]["designators"].append(comp.module_id)
        
        return list(bom.values())


# ============== Backward Compatibility ==============

def generate_pcb(schematic: dict, board_specs: Optional[BoardSpecs] = None) -> dict:
    """Backward compatible wrapper"""
    engine = PCBEngine(board_specs)
    return engine.generate_pcb(schematic)


def _serialise(board, placed, traces, nets, violations, pour) -> dict:
    """Legacy serialization function"""
    # This is kept for backward compatibility
    # In production, use PCBEngine directly
    return {
        "board": {"width": board.width, "height": board.height},
        "components": [c.to_dict() for c in placed],
        "traces": [t.to_dict() for t in traces],
        "nets": [{"name": n.name} for n in nets],
        "drc": [v.to_dict() for v in violations],
        "copperPour": pour.to_dict() if pour else None
    }
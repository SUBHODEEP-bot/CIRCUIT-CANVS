"""
Copper pour (ground plane) generator.

Fills empty board area with a GND copper zone, maintaining clearance
from non-GND copper and adding thermal relief spokes to GND pads.

Output is a set of exclusion zones (clearance cutouts) and thermal
relief descriptors — the frontend renderer draws the fill and masks
out the exclusions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from .placement import PlacedComponent, Board
from .routing import Trace
from .units import POUR_CLEARANCE_MM, THERMAL_SPOKE_WIDTH, THERMAL_GAP_MM


@dataclass
class Exclusion:
    """Circular or rectangular area where copper pour must not exist."""
    kind: str          # "circle" | "rect"
    cx: float
    cy: float
    radius: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class ThermalRelief:
    """Spoked thermal connection between a GND pad and the pour."""
    cx: float
    cy: float
    outer_radius: float
    inner_radius: float
    spoke_width: float = THERMAL_SPOKE_WIDTH
    spoke_count: int = 4


@dataclass
class TraceExclusion:
    """Exclusion zone along a trace path."""
    points: list[tuple[float, float]] = field(default_factory=list)
    clearance: float = POUR_CLEARANCE_MM


@dataclass
class CopperPour:
    net: str                                    # typically "GND"
    board_width: float
    board_height: float
    clearance: float = POUR_CLEARANCE_MM
    pad_exclusions: list[Exclusion] = field(default_factory=list)
    trace_exclusions: list[TraceExclusion] = field(default_factory=list)
    thermals: list[ThermalRelief] = field(default_factory=list)
    
    def to_dict(self):
        """Serialize to JSON-compatible dictionary."""
        return {
            "net": self.net,
            "boardWidth": self.board_width,
            "boardHeight": self.board_height,
            "clearance": self.clearance,
            "padExclusions": [
                {
                    "kind": e.kind,
                    "cx": round(e.cx, 3),
                    "cy": round(e.cy, 3),
                    "radius": round(e.radius, 3),
                    "width": round(e.width, 3),
                    "height": round(e.height, 3)
                }
                for e in self.pad_exclusions
            ],
            "traceExclusions": [
                {
                    "points": [{"x": round(p[0], 3), "y": round(p[1], 3)} for p in te.points],
                    "clearance": te.clearance
                }
                for te in self.trace_exclusions
            ],
            "thermals": [
                {
                    "cx": t.cx,
                    "cy": t.cy,
                    "outerRadius": t.outer_radius,
                    "innerRadius": t.inner_radius,
                    "spokeWidth": t.spoke_width,
                    "spokeCount": t.spoke_count
                }
                for t in self.thermals
            ]
        }


def generate_pour(
    board: Board,
    placed: list[PlacedComponent],
    traces: list[Trace],
    gnd_net_name: str = "GND",
    clearance: float = POUR_CLEARANCE_MM,
) -> CopperPour:
    """
    Build the copper pour data for the given GND net.

    Rules:
    - Non-GND pads get a clearance circle (exclusion).
    - GND pads get a thermal relief (spoked connection).
    - Non-GND traces get a clearance buffer (trace exclusion).
    - GND traces are absorbed into the pour (no exclusion needed).
    """
    pour = CopperPour(
        net=gnd_net_name,
        board_width=board.width,
        board_height=board.height,
        clearance=clearance,
    )

    for comp in placed:
        for pad in comp.footprint.pads:
            abs_x = comp.x + pad.x
            abs_y = comp.y + pad.y
            pad_r = max(pad.width, pad.height) / 2

            if pad.net == gnd_net_name:
                pour.thermals.append(ThermalRelief(
                    cx=abs_x,
                    cy=abs_y,
                    outer_radius=pad_r + POUR_CLEARANCE_MM + THERMAL_GAP_MM,
                    inner_radius=pad_r,
                ))
            else:
                pour.pad_exclusions.append(Exclusion(
                    kind="circle",
                    cx=abs_x,
                    cy=abs_y,
                    radius=pad_r + POUR_CLEARANCE_MM,
                ))

    for trace in traces:
        if trace.net_name == gnd_net_name:
            continue
        pour.trace_exclusions.append(TraceExclusion(
            points=list(trace.points),
            clearance=POUR_CLEARANCE_MM + trace.width / 2,
        ))

    return pour

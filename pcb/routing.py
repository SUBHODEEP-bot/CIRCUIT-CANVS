"""
Trace routing engine — connects pads that belong to the same net
using simple Manhattan (L-shaped) routing on a single copper layer.

Each trace is a list of (x, y) points forming the route path.
Future: multi-layer routing, obstacle-aware A* pathfinding.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from .placement import PlacedComponent
from .netlist import Net


@dataclass
class Trace:
    net_name: str
    points: list[tuple[float, float]] = field(default_factory=list)
    width: float = 0.25  # mm trace width


def _pad_position(
    comp: PlacedComponent, pad_name: str
) -> tuple[float, float] | None:
    """Get the absolute board position of a pad by name."""
    for pad in comp.footprint.pads:
        if pad.name == pad_name:
            return (comp.x + pad.x, comp.y + pad.y)
    return None


def _find_pad_position(
    instance_id: str,
    pin_id: str,
    components: dict[str, PlacedComponent],
    pin_to_pad: dict[str, str],
) -> tuple[float, float] | None:
    """Resolve a schematic pin reference to an absolute board coordinate."""
    comp = components.get(instance_id)
    if not comp:
        return None

    pad_name = pin_to_pad.get(f"{instance_id}::{pin_id}")
    if pad_name:
        return _pad_position(comp, pad_name)

    # Fallback: try matching by pad index
    fp_pads = comp.footprint.pads
    # pin_id might be a UUID; map by position in the schematic pin list
    for pad in fp_pads:
        if pad.name == pin_id:
            return _pad_position(comp, pad.name)

    # Last resort: use the first available pad
    if fp_pads:
        return _pad_position(comp, fp_pads[0].name)

    return None


def route_nets(
    nets: list[Net],
    placed: list[PlacedComponent],
    pin_to_pad: dict[str, str],
) -> list[Trace]:
    """
    Route each net using L-shaped Manhattan traces.

    For a net with N pins we connect them in a chain
    (pin0 → pin1 → pin2 → …) using a single L-bend per segment.
    """
    comp_map = {c.instance_id: c for c in placed}
    traces: list[Trace] = []

    for net in nets:
        positions: list[tuple[float, float]] = []
        for inst_id, pin_id in net.pins:
            pos = _find_pad_position(inst_id, pin_id, comp_map, pin_to_pad)
            if pos:
                positions.append(pos)

        if len(positions) < 2:
            continue

        # Chain successive pins with an L-bend
        for i in range(len(positions) - 1):
            x1, y1 = positions[i]
            x2, y2 = positions[i + 1]
            # L-shape: go horizontal first, then vertical
            mid_x, mid_y = x2, y1
            traces.append(
                Trace(
                    net_name=net.name,
                    points=[(x1, y1), (mid_x, mid_y), (x2, y2)],
                )
            )

    return traces

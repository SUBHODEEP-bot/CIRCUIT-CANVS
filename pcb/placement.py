"""
Component placement engine — positions footprints on the PCB board
using grid-based placement with courtyard-aware collision avoidance.

All dimensions are in millimetres.
"""

from __future__ import annotations
from dataclasses import dataclass
from .footprints import Footprint
from .units import BOARD_EDGE_CLEARANCE

COMPONENT_GAP = 8.0   # mm gap between courtyards — room for routing channels


@dataclass
class PlacedComponent:
    instance_id: str
    module_id: str
    module_name: str
    footprint: Footprint
    x: float          # mm — top-left origin on the board
    y: float          # mm
    width: float       # mm
    height: float      # mm


@dataclass
class Board:
    width: float       # mm
    height: float      # mm


def _courtyard(fp: Footprint) -> tuple[float, float]:
    """Effective width/height including courtyard margin."""
    return (
        fp.width  + 2 * fp.courtyard_margin,
        fp.height + 2 * fp.courtyard_margin,
    )


def place_components(
    instances: list[dict],
    footprints: dict[str, Footprint],
) -> tuple[Board, list[PlacedComponent]]:
    """
    Grid-based placement: arrange components left-to-right,
    top-to-bottom, respecting courtyard clearance zones.
    """
    placed: list[PlacedComponent] = []
    margin = max(BOARD_EDGE_CLEARANCE, 3.0)
    cursor_x = margin
    cursor_y = margin
    row_max_h = 0.0
    max_row_w = 0.0

    MAX_BOARD_W = 200.0

    sorted_instances = sorted(
        instances,
        key=lambda inst: (
            footprints.get(inst["instanceId"], Footprint("?", 10, 10)).width
            * footprints.get(inst["instanceId"], Footprint("?", 10, 10)).height
        ),
        reverse=True,
    )

    for inst in sorted_instances:
        fp = footprints.get(inst["instanceId"])
        if not fp:
            continue

        cw, ch = _courtyard(fp)

        if cursor_x + cw + COMPONENT_GAP > MAX_BOARD_W:
            cursor_x = margin
            cursor_y += row_max_h + COMPONENT_GAP
            row_max_h = 0.0

        comp_x = cursor_x + fp.courtyard_margin
        comp_y = cursor_y + fp.courtyard_margin

        placed.append(PlacedComponent(
            instance_id=inst["instanceId"],
            module_id=inst["moduleId"],
            module_name=inst.get("moduleName", ""),
            footprint=fp,
            x=comp_x,
            y=comp_y,
            width=fp.width,
            height=fp.height,
        ))

        cursor_x += cw + COMPONENT_GAP
        row_max_h = max(row_max_h, ch)
        max_row_w = max(max_row_w, cursor_x)

    board_w = max(max_row_w + margin, 50.0)
    board_h = max(cursor_y + row_max_h + margin, 30.0)

    return Board(width=round(board_w, 2), height=round(board_h, 2)), placed

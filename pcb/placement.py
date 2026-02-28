"""
Component placement engine — positions footprints on the PCB board
using a simple grid-based algorithm with basic collision avoidance.

Future: force-directed or simulated-annealing placement.
"""

from __future__ import annotations
from dataclasses import dataclass
from .footprints import Footprint

BOARD_MARGIN = 5.0   # mm from board edge
GAP = 4.0            # mm gap between components


@dataclass
class PlacedComponent:
    instance_id: str
    module_id: str
    module_name: str
    footprint: Footprint
    x: float        # mm — top-left corner on the board
    y: float        # mm
    width: float     # mm
    height: float    # mm


@dataclass
class Board:
    width: float     # mm
    height: float    # mm


def place_components(
    instances: list[dict],
    footprints: dict[str, Footprint],
) -> tuple[Board, list[PlacedComponent]]:
    """
    Grid-based placement: lay out components left-to-right, top-to-bottom.
    Returns the board dimensions and placed component list.
    """
    placed: list[PlacedComponent] = []
    cursor_x = BOARD_MARGIN
    cursor_y = BOARD_MARGIN
    row_max_height = 0.0
    max_row_width = 0.0

    # Sort by footprint area (largest first) for more compact layouts
    sorted_instances = sorted(
        instances,
        key=lambda inst: footprints.get(inst["instanceId"], Footprint("?", 10, 10)).width
        * footprints.get(inst["instanceId"], Footprint("?", 10, 10)).height,
        reverse=True,
    )

    for inst in sorted_instances:
        fp = footprints.get(inst["instanceId"])
        if not fp:
            continue

        w, h = fp.width, fp.height

        # Wrap to next row if this component exceeds a reasonable board width
        max_board_w = 200.0  # mm soft limit
        if cursor_x + w + GAP > max_board_w:
            cursor_x = BOARD_MARGIN
            cursor_y += row_max_height + GAP
            row_max_height = 0.0

        placed.append(
            PlacedComponent(
                instance_id=inst["instanceId"],
                module_id=inst["moduleId"],
                module_name=inst.get("moduleName", ""),
                footprint=fp,
                x=cursor_x,
                y=cursor_y,
                width=w,
                height=h,
            )
        )

        cursor_x += w + GAP
        row_max_height = max(row_max_height, h)
        max_row_width = max(max_row_width, cursor_x)

    board_w = max(max_row_width + BOARD_MARGIN, 60.0)
    board_h = max(cursor_y + row_max_height + BOARD_MARGIN, 40.0)

    return Board(width=board_w, height=board_h), placed

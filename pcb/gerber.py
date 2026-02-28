"""
Gerber export stub — placeholder for future Gerber RS-274X file generation.

Currently returns a simple text representation of the PCB layout.
Future: full Gerber / Excellon drill output.
"""

from __future__ import annotations
from .placement import Board, PlacedComponent
from .routing import Trace


def export_gerber_stub(
    board: Board,
    components: list[PlacedComponent],
    traces: list[Trace],
) -> str:
    """
    Returns a human-readable text summary of the PCB.
    A real implementation would emit Gerber RS-274X files.
    """
    lines = [
        f"Board: {board.width:.1f} x {board.height:.1f} mm",
        f"Components: {len(components)}",
        f"Traces: {len(traces)}",
        "",
    ]

    for comp in components:
        lines.append(
            f"  [{comp.module_name}] at ({comp.x:.1f}, {comp.y:.1f}) "
            f"size {comp.width:.1f}x{comp.height:.1f}mm  "
            f"pads={len(comp.footprint.pads)}"
        )

    lines.append("")
    for trace in traces:
        pts = " → ".join(f"({x:.1f},{y:.1f})" for x, y in trace.points)
        lines.append(f"  {trace.net_name}: {pts}")

    return "\n".join(lines)

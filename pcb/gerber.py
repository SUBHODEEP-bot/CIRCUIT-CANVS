"""
Gerber export — generates a simplified Gerber RS-274X text output
for the copper layer.  Suitable as a reference; a full implementation
would produce separate files for each layer + Excellon drill data.
"""

from __future__ import annotations
from .placement import Board, PlacedComponent
from .routing import Trace
from .units import mm_to_mil


def export_gerber_stub(
    board: Board,
    components: list[PlacedComponent],
    traces: list[Trace],
) -> str:
    """
    Human-readable Gerber-style summary with mm and mil dimensions.
    """
    lines = [
        "G04 CircuitForge PCB Export*",
        f"G04 Board: {board.width:.2f} x {board.height:.2f} mm "
        f"({mm_to_mil(board.width):.0f} x {mm_to_mil(board.height):.0f} mil)*",
        f"G04 Components: {len(components)}*",
        f"G04 Traces: {len(traces)}*",
        "%MOIN*%",
        "%FSLAX36Y36*%",
        "",
    ]

    for comp in components:
        lines.append(
            f"G04 [{comp.module_name}] origin=({comp.x:.2f},{comp.y:.2f})mm "
            f"size={comp.width:.2f}x{comp.height:.2f}mm  pads={len(comp.footprint.pads)}*"
        )

    lines.append("")
    for trace in traces:
        pts = " ".join(f"({x:.2f},{y:.2f})" for x, y in trace.points)
        lines.append(f"G04 {trace.net_name} w={trace.width:.3f}mm: {pts}*")

    lines.append("M02*")
    return "\n".join(lines)

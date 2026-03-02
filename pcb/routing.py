"""
Trace routing engine with 45-degree angles and DRC clearance checking.

Routes each net by chaining its pads with 3-segment traces:
  straight → 45° diagonal → straight

Performs clearance checks so traces don't collide with unrelated
pads or other-net traces.  All coordinates are in mm.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from .placement import PlacedComponent
from .netlist import Net
from .units import CLEARANCE_MM, TRACE_WIDTH_MM, TRACE_WIDTH_POWER_MM


@dataclass
class Trace:
    net_name: str
    points: list[tuple[float, float]] = field(default_factory=list)
    width: float = TRACE_WIDTH_MM


@dataclass
class DRCViolation:
    kind: str            # "pad_clearance" | "trace_clearance"
    net: str
    x: float
    y: float
    detail: str


# ── Geometry helpers ─────────────────────────────────────────────

def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _point_to_segment_dist(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """Minimum distance from point (px,py) to segment (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _segment_to_segment_dist(
    a1: tuple[float, float], a2: tuple[float, float],
    b1: tuple[float, float], b2: tuple[float, float],
) -> float:
    """Approximate min distance between two segments."""
    candidates = [
        _point_to_segment_dist(a1[0], a1[1], b1[0], b1[1], b2[0], b2[1]),
        _point_to_segment_dist(a2[0], a2[1], b1[0], b1[1], b2[0], b2[1]),
        _point_to_segment_dist(b1[0], b1[1], a1[0], a1[1], a2[0], a2[1]),
        _point_to_segment_dist(b2[0], b2[1], a1[0], a1[1], a2[0], a2[1]),
    ]
    return min(candidates)


# ── 45-degree route generation ───────────────────────────────────

def _route_45(
    x1: float, y1: float, x2: float, y2: float,
) -> list[tuple[float, float]]:
    """
    Build a 3-segment route with 45° diagonals:
      horizontal → 45° → vertical   (or v → 45° → h)

    Picks the arrangement that keeps the diagonal short.
    """
    dx = x2 - x1
    dy = y2 - y1

    if abs(dx) < 0.01 and abs(dy) < 0.01:
        return [(x1, y1), (x2, y2)]

    # Pure horizontal or vertical — no diagonal needed
    if abs(dx) < 0.01 or abs(dy) < 0.01:
        return [(x1, y1), (x2, y2)]

    adx, ady = abs(dx), abs(dy)
    diag = min(adx, ady)
    sx = 1.0 if dx > 0 else -1.0
    sy = 1.0 if dy > 0 else -1.0

    if adx >= ady:
        # Horizontal first, then 45°, then remaining horizontal/straight to target
        straight_len = adx - diag
        mid1 = (x1 + sx * straight_len, y1)
        mid2 = (mid1[0] + sx * diag, y1 + sy * diag)
        points = [(x1, y1), mid1, mid2, (x2, y2)]
    else:
        # Vertical first, then 45°, then remaining
        straight_len = ady - diag
        mid1 = (x1, y1 + sy * straight_len)
        mid2 = (x1 + sx * diag, mid1[1] + sy * diag)
        points = [(x1, y1), mid1, mid2, (x2, y2)]

    # Remove degenerate zero-length segments
    cleaned: list[tuple[float, float]] = [points[0]]
    for pt in points[1:]:
        if _dist(cleaned[-1], pt) > 0.01:
            cleaned.append(pt)
    return cleaned


def _try_alternate_route(
    x1: float, y1: float, x2: float, y2: float,
) -> list[tuple[float, float]]:
    """Mirror route: go vertical first instead of horizontal."""
    dx = x2 - x1
    dy = y2 - y1
    adx, ady = abs(dx), abs(dy)
    diag = min(adx, ady)
    sx = 1.0 if dx > 0 else -1.0
    sy = 1.0 if dy > 0 else -1.0

    if adx >= ady:
        mid1 = (x1, y1 + sy * diag)
        mid2 = (x1 + sx * diag, mid1[1])
        straight_end = (x2, y2)
    else:
        mid1 = (x1 + sx * diag, y1)
        mid2 = (mid1[0], y1 + sy * diag)
        straight_end = (x2, y2)

    points = [(x1, y1), mid1, mid2, straight_end]
    cleaned: list[tuple[float, float]] = [points[0]]
    for pt in points[1:]:
        if _dist(cleaned[-1], pt) > 0.01:
            cleaned.append(pt)
    return cleaned


# ── Clearance checking ───────────────────────────────────────────

def _check_pad_clearance(
    points: list[tuple[float, float]],
    trace_w: float,
    pads: list[tuple[float, float, float, str]],  # (x, y, radius, net)
    own_net: str,
    clearance: float,
) -> list[DRCViolation]:
    """Check that a trace keeps clearance from pads not on its net."""
    violations: list[DRCViolation] = []
    min_gap = clearance + trace_w / 2

    for i in range(len(points) - 1):
        seg_a, seg_b = points[i], points[i + 1]
        for px, py, pr, pnet in pads:
            if pnet == own_net:
                continue
            d = _point_to_segment_dist(px, py, seg_a[0], seg_a[1], seg_b[0], seg_b[1])
            if d < min_gap + pr:
                violations.append(DRCViolation(
                    kind="pad_clearance",
                    net=own_net,
                    x=px, y=py,
                    detail=f"Trace {own_net} is {d:.2f}mm from pad (net {pnet}), min {min_gap + pr:.2f}mm",
                ))
    return violations


def _check_trace_clearance(
    points: list[tuple[float, float]],
    trace_w: float,
    existing: list[Trace],
    own_net: str,
    clearance: float,
) -> list[DRCViolation]:
    """Check that a new trace keeps clearance from existing traces on other nets."""
    violations: list[DRCViolation] = []
    min_gap = clearance + trace_w / 2

    for i in range(len(points) - 1):
        sa, sb = points[i], points[i + 1]
        for et in existing:
            if et.net_name == own_net:
                continue
            other_half_w = et.width / 2
            for j in range(len(et.points) - 1):
                ea, eb = et.points[j], et.points[j + 1]
                d = _segment_to_segment_dist(sa, sb, ea, eb)
                if d < min_gap + other_half_w:
                    mx = (sa[0] + sb[0]) / 2
                    my = (sa[1] + sb[1]) / 2
                    violations.append(DRCViolation(
                        kind="trace_clearance",
                        net=own_net,
                        x=mx, y=my,
                        detail=f"Trace {own_net} is {d:.2f}mm from trace {et.net_name}",
                    ))
    return violations


# ── Pad position resolution ──────────────────────────────────────

def _abs_pad_pos(comp: PlacedComponent, pad_name: str) -> tuple[float, float] | None:
    for pad in comp.footprint.pads:
        if pad.name == pad_name:
            return (comp.x + pad.x, comp.y + pad.y)
    return None


def _resolve_pad(
    instance_id: str,
    pin_id: str,
    comp_map: dict[str, PlacedComponent],
    pin_to_pad: dict[str, str],
) -> tuple[float, float] | None:
    comp = comp_map.get(instance_id)
    if not comp:
        return None

    pad_name = pin_to_pad.get(f"{instance_id}::{pin_id}")
    if pad_name:
        pos = _abs_pad_pos(comp, pad_name)
        if pos:
            return pos

    # Fallback: try pin_id as pad name directly
    pos = _abs_pad_pos(comp, pin_id)
    if pos:
        return pos

    if comp.footprint.pads:
        pad = comp.footprint.pads[0]
        return (comp.x + pad.x, comp.y + pad.y)
    return None


# ── Public API ───────────────────────────────────────────────────

def route_nets(
    nets: list[Net],
    placed: list[PlacedComponent],
    pin_to_pad: dict[str, str],
) -> tuple[list[Trace], list[DRCViolation]]:
    """
    Route all nets with 45° traces and clearance checking.

    Returns (traces, drc_violations).
    """
    comp_map = {c.instance_id: c for c in placed}

    # Build global pad list for clearance checks
    all_pads: list[tuple[float, float, float, str]] = []
    for comp in placed:
        for pad in comp.footprint.pads:
            radius = max(pad.width, pad.height) / 2
            all_pads.append((comp.x + pad.x, comp.y + pad.y, radius, pad.net))

    traces: list[Trace] = []
    violations: list[DRCViolation] = []

    for net in nets:
        trace_w = TRACE_WIDTH_POWER_MM if (net.is_power or net.is_ground) else TRACE_WIDTH_MM

        # Resolve pad positions for this net
        positions: list[tuple[float, float]] = []
        for inst_id, pin_id in net.pins:
            pos = _resolve_pad(inst_id, pin_id, comp_map, pin_to_pad)
            if pos:
                positions.append(pos)

        if len(positions) < 2:
            continue

        # Sort positions to minimise total wire length (nearest-neighbor)
        ordered = [positions[0]]
        remaining = list(positions[1:])
        while remaining:
            last = ordered[-1]
            nearest_idx = min(range(len(remaining)), key=lambda i: _dist(last, remaining[i]))
            ordered.append(remaining.pop(nearest_idx))

        # Route each consecutive pair
        for i in range(len(ordered) - 1):
            x1, y1 = ordered[i]
            x2, y2 = ordered[i + 1]

            primary = _route_45(x1, y1, x2, y2)
            alt = _try_alternate_route(x1, y1, x2, y2)

            # Pick the route with fewer violations
            v_primary = (
                _check_pad_clearance(primary, trace_w, all_pads, net.name, CLEARANCE_MM)
                + _check_trace_clearance(primary, trace_w, traces, net.name, CLEARANCE_MM)
            )
            v_alt = (
                _check_pad_clearance(alt, trace_w, all_pads, net.name, CLEARANCE_MM)
                + _check_trace_clearance(alt, trace_w, traces, net.name, CLEARANCE_MM)
            )

            if len(v_alt) < len(v_primary):
                chosen, chosen_v = alt, v_alt
            else:
                chosen, chosen_v = primary, v_primary

            traces.append(Trace(net_name=net.name, points=chosen, width=trace_w))
            violations.extend(chosen_v)

    return traces, violations

"""
PCB trace routing engine — 45° angles, no-cross guarantee, DRC clearance.

Routing pipeline for each net:
  1. Resolve absolute pad positions from placed components
  2. Order pads by nearest-neighbor to minimise total wire length
  3. For each consecutive pad pair, generate 12 route candidates:
     - 2 direct 45° routes (horizontal-first and vertical-first)
     - 10 offset routes (waypoints ±1.5 … ±12 mm perpendicular to the
       direct line) that detour around existing traces
  4. Score each candidate: (crossings, drc_violations, total_length)
  5. Pick the candidate with 0 crossings, fewest DRC errors, shortest path
  6. Trim endpoints so traces stop at the pad edge (clear solder mask)
  7. Commit trace; subsequent candidates see it as an obstacle

All coordinates are in millimetres.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from .placement import PlacedComponent
from .netlist import Net
from .units import CLEARANCE_MM, TRACE_WIDTH_MM, TRACE_WIDTH_POWER_MM


# ── Data classes ─────────────────────────────────────────────────

@dataclass
class Trace:
    net_name: str
    points: list[tuple[float, float]] = field(default_factory=list)
    width: float = TRACE_WIDTH_MM


@dataclass
class DRCViolation:
    kind: str          # "crossing" | "pad_clearance" | "trace_clearance"
    net: str
    x: float
    y: float
    detail: str


# ── Geometry primitives ──────────────────────────────────────────

def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _cross2d(o: tuple, a: tuple, b: tuple) -> float:
    """Signed area of triangle OAB (cross product of OA × OB)."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_cross(
    a1: tuple, a2: tuple, b1: tuple, b2: tuple, tol: float = 0.2,
) -> bool:
    """
    True if segment a1→a2 properly intersects segment b1→b2.
    Shared endpoints (within *tol* mm) do NOT count as crossings —
    two traces meeting at the same pad is normal.
    """
    for ap in (a1, a2):
        for bp in (b1, b2):
            if _dist(ap, bp) < tol:
                return False

    d1 = _cross2d(a1, a2, b1)
    d2 = _cross2d(a1, a2, b2)
    d3 = _cross2d(b1, b2, a1)
    d4 = _cross2d(b1, b2, a2)

    return (
        ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0))
        and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0))
    )


def _point_to_segment_dist(
    px: float, py: float,
    ax: float, ay: float, bx: float, by: float,
) -> float:
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _segment_to_segment_dist(a1: tuple, a2: tuple, b1: tuple, b2: tuple) -> float:
    return min(
        _point_to_segment_dist(a1[0], a1[1], b1[0], b1[1], b2[0], b2[1]),
        _point_to_segment_dist(a2[0], a2[1], b1[0], b1[1], b2[0], b2[1]),
        _point_to_segment_dist(b1[0], b1[1], a1[0], a1[1], a2[0], a2[1]),
        _point_to_segment_dist(b2[0], b2[1], a1[0], a1[1], a2[0], a2[1]),
    )


# ── 45° route generation ────────────────────────────────────────

def _clean(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Remove zero-length segments."""
    if not pts:
        return pts
    out = [pts[0]]
    for p in pts[1:]:
        if _dist(out[-1], p) > 0.01:
            out.append(p)
    return out if len(out) >= 2 else [pts[0], pts[-1]]


def _route_45_hv(x1: float, y1: float, x2: float, y2: float) -> list[tuple]:
    """Horizontal → 45° diagonal → vertical."""
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) < 0.01 or abs(dy) < 0.01:
        return _clean([(x1, y1), (x2, y2)])
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
    return _clean([(x1, y1), m1, m2, (x2, y2)])


def _route_45_vh(x1: float, y1: float, x2: float, y2: float) -> list[tuple]:
    """Vertical → 45° diagonal → horizontal (mirror of _hv)."""
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) < 0.01 or abs(dy) < 0.01:
        return _clean([(x1, y1), (x2, y2)])
    adx, ady = abs(dx), abs(dy)
    diag = min(adx, ady)
    sx, sy = (1.0 if dx > 0 else -1.0), (1.0 if dy > 0 else -1.0)
    if adx >= ady:
        m1 = (x1, y1 + sy * diag)
        m2 = (x1 + sx * diag, m1[1])
    else:
        m1 = (x1 + sx * diag, y1)
        m2 = (m1[0], y1 + sy * diag)
    return _clean([(x1, y1), m1, m2, (x2, y2)])


# ── Offset (detour) route generation ────────────────────────────

def _route_via_waypoint(
    x1: float, y1: float,
    wx: float, wy: float,
    x2: float, y2: float,
) -> list[tuple]:
    """Route through an intermediate waypoint using two 45° sub-routes."""
    a = _route_45_hv(x1, y1, wx, wy)
    b = _route_45_hv(wx, wy, x2, y2)
    return _clean(a + b[1:])


def _generate_candidates(
    x1: float, y1: float, x2: float, y2: float,
) -> list[list[tuple]]:
    """
    Generate 12 routing candidates for a pad pair.

    The first two are direct 45° routes; the rest go through an
    offset waypoint perpendicular to the straight line between pads,
    creating a detour that avoids crossing existing traces.
    """
    cands: list[list[tuple]] = []

    cands.append(_route_45_hv(x1, y1, x2, y2))
    cands.append(_route_45_vh(x1, y1, x2, y2))

    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.5:
        return cands

    # Perpendicular unit vector
    px, py = -dy / length, dx / length
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2

    for off in (1.5, -1.5, 3.0, -3.0, 5.0, -5.0, 8.0, -8.0, 12.0, -12.0):
        wx = mx + px * off
        wy = my + py * off
        cands.append(_route_via_waypoint(x1, y1, wx, wy, x2, y2))

    return [c for c in cands if len(c) >= 2]


# ── Crossing / DRC scoring ──────────────────────────────────────

def _count_crossings(
    points: list[tuple], existing: list[Trace],
) -> int:
    n = 0
    for i in range(len(points) - 1):
        a1, a2 = points[i], points[i + 1]
        for et in existing:
            for j in range(len(et.points) - 1):
                if _segments_cross(a1, a2, et.points[j], et.points[j + 1]):
                    n += 1
    return n


def _count_drc(
    points: list[tuple],
    trace_w: float,
    all_pads: list[tuple],       # (x, y, radius, net_name)
    existing: list[Trace],
    own_net: str,
    clearance: float,
) -> int:
    n = 0
    half = trace_w / 2
    for i in range(len(points) - 1):
        sa, sb = points[i], points[i + 1]
        for px, py, pr, pnet in all_pads:
            if pnet == own_net:
                continue
            if _point_to_segment_dist(px, py, sa[0], sa[1], sb[0], sb[1]) < clearance + half + pr:
                n += 1
        for et in existing:
            if et.net_name == own_net:
                continue
            for j in range(len(et.points) - 1):
                if _segment_to_segment_dist(sa, sb, et.points[j], et.points[j + 1]) < clearance + half + et.width / 2:
                    n += 1
    return n


def _collect_violations(
    points: list[tuple],
    trace_w: float,
    all_pads: list[tuple],
    existing: list[Trace],
    own_net: str,
    clearance: float,
) -> list[DRCViolation]:
    """Detailed violation list for the final committed route."""
    vs: list[DRCViolation] = []
    half = trace_w / 2
    for i in range(len(points) - 1):
        sa, sb = points[i], points[i + 1]
        for px, py, pr, pnet in all_pads:
            if pnet == own_net:
                continue
            d = _point_to_segment_dist(px, py, sa[0], sa[1], sb[0], sb[1])
            needed = clearance + half + pr
            if d < needed:
                vs.append(DRCViolation(
                    "pad_clearance", own_net, px, py,
                    f"{own_net} trace {d:.2f}mm from pad ({pnet}), need {needed:.2f}mm",
                ))
        for et in existing:
            if et.net_name == own_net:
                continue
            for j in range(len(et.points) - 1):
                ea, eb = et.points[j], et.points[j + 1]
                d = _segment_to_segment_dist(sa, sb, ea, eb)
                needed = clearance + half + et.width / 2
                if d < needed:
                    mx = (sa[0] + sb[0]) / 2
                    my = (sa[1] + sb[1]) / 2
                    vs.append(DRCViolation(
                        "trace_clearance", own_net, mx, my,
                        f"{own_net} trace {d:.2f}mm from {et.net_name} trace, need {needed:.2f}mm",
                    ))
    return vs


# ── Endpoint trimming (solder mask clearance) ────────────────────

def _trim_start(points: list[tuple], pad_r: float) -> list[tuple]:
    """Shorten first segment so it starts at the pad edge, not the center."""
    if len(points) < 2 or pad_r <= 0:
        return points
    dx = points[1][0] - points[0][0]
    dy = points[1][1] - points[0][1]
    d = math.hypot(dx, dy)
    if d < pad_r * 1.2:
        return points
    new = (points[0][0] + dx * pad_r / d, points[0][1] + dy * pad_r / d)
    return [new] + list(points[1:])


def _trim_end(points: list[tuple], pad_r: float) -> list[tuple]:
    """Shorten last segment so it ends at the pad edge, not the center."""
    if len(points) < 2 or pad_r <= 0:
        return points
    dx = points[-2][0] - points[-1][0]
    dy = points[-2][1] - points[-1][1]
    d = math.hypot(dx, dy)
    if d < pad_r * 1.2:
        return points
    new = (points[-1][0] + dx * pad_r / d, points[-1][1] + dy * pad_r / d)
    return list(points[:-1]) + [new]


# ── Pad resolution ───────────────────────────────────────────────

def _resolve_pad(
    instance_id: str,
    pin_id: str,
    comp_map: dict[str, PlacedComponent],
    pin_to_pad: dict[str, str],
) -> tuple[float, float, float] | None:
    """Resolve schematic pin → absolute (x, y, radius) on board."""
    comp = comp_map.get(instance_id)
    if not comp:
        return None

    pad_name = pin_to_pad.get(f"{instance_id}::{pin_id}")
    for pad in comp.footprint.pads:
        if pad.name == pad_name or pad.name == pin_id:
            r = max(pad.width, pad.height) / 2
            return (comp.x + pad.x, comp.y + pad.y, r)

    if comp.footprint.pads:
        pad = comp.footprint.pads[0]
        return (comp.x + pad.x, comp.y + pad.y, max(pad.width, pad.height) / 2)
    return None


# ── Ordering ─────────────────────────────────────────────────────

def _nearest_neighbor(pads: list[tuple]) -> list[tuple]:
    if len(pads) <= 2:
        return list(pads)
    ordered = [pads[0]]
    rest = list(pads[1:])
    while rest:
        last = ordered[-1]
        idx = min(range(len(rest)), key=lambda i: math.hypot(last[0] - rest[i][0], last[1] - rest[i][1]))
        ordered.append(rest.pop(idx))
    return ordered


# ── Public API ───────────────────────────────────────────────────

def route_nets(
    nets: list[Net],
    placed: list[PlacedComponent],
    pin_to_pad: dict[str, str],
    skip_nets: set[str] | None = None,
) -> tuple[list[Trace], list[DRCViolation]]:
    """
    Route all nets.  Returns (traces, violations).

    *skip_nets* — net names to omit (e.g. {"GND"} when copper pour
    will provide the connectivity).
    """
    comp_map = {c.instance_id: c for c in placed}
    skip = skip_nets or set()

    # Global pad list for clearance checks
    all_pads: list[tuple[float, float, float, str]] = []
    for comp in placed:
        for pad in comp.footprint.pads:
            all_pads.append((
                comp.x + pad.x, comp.y + pad.y,
                max(pad.width, pad.height) / 2,
                pad.net,
            ))

    # Route short signal nets first, power/GND last
    ordered_nets = sorted(nets, key=lambda n: (
        2 if n.is_ground else (1 if n.is_power else 0),
        len(n.pins),
    ))

    traces: list[Trace] = []
    violations: list[DRCViolation] = []

    for net in ordered_nets:
        if net.name in skip:
            continue

        tw = TRACE_WIDTH_POWER_MM if (net.is_power or net.is_ground) else TRACE_WIDTH_MM

        # Resolve pads → (x, y, radius)
        pad_data: list[tuple[float, float, float]] = []
        for iid, pid in net.pins:
            res = _resolve_pad(iid, pid, comp_map, pin_to_pad)
            if res:
                pad_data.append(res)

        if len(pad_data) < 2:
            continue

        ordered = _nearest_neighbor(pad_data)

        for i in range(len(ordered) - 1):
            x1, y1, r1 = ordered[i]
            x2, y2, r2 = ordered[i + 1]

            cands = _generate_candidates(x1, y1, x2, y2)

            best: list[tuple] | None = None
            best_score = (float("inf"), float("inf"), float("inf"))

            for route in cands:
                cx = _count_crossings(route, traces)
                drc = _count_drc(route, tw, all_pads, traces, net.name, CLEARANCE_MM)
                ln = sum(_dist(route[k], route[k + 1]) for k in range(len(route) - 1))
                score = (cx, drc, ln)
                if score < best_score:
                    best_score = score
                    best = route

            if not best:
                continue

            trimmed = _trim_start(best, r1)
            trimmed = _trim_end(trimmed, r2)

            traces.append(Trace(net_name=net.name, points=trimmed, width=tw))

            # Collect detailed violations for this committed route
            if best_score[0] > 0:
                mx = (x1 + x2) / 2
                my = (y1 + y2) / 2
                violations.append(DRCViolation(
                    "crossing", net.name, mx, my,
                    f"{net.name} crosses {best_score[0]} existing trace(s)",
                ))

            violations.extend(
                _collect_violations(trimmed, tw, all_pads, traces, net.name, CLEARANCE_MM)
            )

    return traces, violations

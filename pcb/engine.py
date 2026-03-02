"""
PCB generation engine — full professional pipeline:

  schematic JSON
    → global netlist (auto GND/VCC detection)
    → footprint assignment
    → pad positions overridden from admin's Placed Pins metadata
    → pad-net binding
    → grid placement with courtyard clearance
    → 45° trace routing with no-cross guarantee + DRC
    → GND copper pour (traces to GND skipped; pour provides connectivity)
    → JSON output (mm units)
"""

from __future__ import annotations
from .netlist import generate_netlist, Net
from .footprints import get_footprint, Footprint
from .placement import place_components, PlacedComponent, Board
from .routing import route_nets, Trace, DRCViolation
from .copper_pour import generate_pour, CopperPour
from .units import PX_PER_MM, TRACE_WIDTH_MM, SILKSCREEN_WIDTH_MM


def generate_pcb(schematic: dict) -> dict:
    instances = schematic.get("modules", [])
    wires = schematic.get("wires", [])

    # ── 1. Global netlist ────────────────────────────────────────
    nets = generate_netlist(wires, instances)

    # ── 2. Footprint assignment ──────────────────────────────────
    instance_fps: dict[str, Footprint] = {}
    for inst in instances:
        pin_count = len(inst.get("pins", []))
        fp = get_footprint(
            inst.get("moduleName", "Unknown"),
            inst.get("category"),
            max(pin_count, 2),
        )
        instance_fps[inst["instanceId"]] = fp

    # ── 3. Override pad positions with admin's Placed Pins ───────
    #    The admin places pins on the module image at (x, y) %
    #    positions.  We scale these percentages to the footprint
    #    body dimensions so pads appear exactly where the admin
    #    marked them.
    for inst in instances:
        fp = instance_fps.get(inst["instanceId"])
        if not fp:
            continue
        for idx, pin in enumerate(inst.get("pins", [])):
            if idx >= len(fp.pads):
                break
            pin_x_pct = pin.get("x")
            pin_y_pct = pin.get("y")
            if pin_x_pct is not None and pin_y_pct is not None:
                fp.pads[idx].x = (pin_x_pct / 100.0) * fp.width
                fp.pads[idx].y = (pin_y_pct / 100.0) * fp.height
            fp.pads[idx].name = pin.get("name", fp.pads[idx].name)

    # ── 4. Pin-to-pad mapping + pad-net binding ──────────────────
    pin_to_pad: dict[str, str] = {}
    net_by_pin: dict[str, str] = {}
    for net in nets:
        for inst_id, pin_id in net.pins:
            net_by_pin[f"{inst_id}::{pin_id}"] = net.name

    for inst in instances:
        fp = instance_fps.get(inst["instanceId"])
        if not fp:
            continue
        for idx, pin in enumerate(inst.get("pins", [])):
            key = f"{inst['instanceId']}::{pin['id']}"
            pad_name = fp.pads[idx].name if idx < len(fp.pads) else f"P{idx}"
            pin_to_pad[key] = pad_name
            if idx < len(fp.pads):
                fp.pads[idx].net = net_by_pin.get(key, "")

    enriched = [{**inst, "moduleName": inst.get("moduleName", "Unknown")} for inst in instances]

    # ── 5. Placement ─────────────────────────────────────────────
    board, placed = place_components(enriched, instance_fps)

    # ── 6. Routing ───────────────────────────────────────────────
    #    Skip GND routing when copper pour is active — the pour
    #    provides connectivity for the entire GND net.
    gnd_net = next((n for n in nets if n.is_ground), None)
    skip = {gnd_net.name} if gnd_net else set()

    traces, violations = route_nets(nets, placed, pin_to_pad, skip_nets=skip)

    # ── 7. Copper pour ───────────────────────────────────────────
    pour = generate_pour(board, placed, traces, gnd_net.name if gnd_net else "GND") if gnd_net else None

    # ── 8. Serialise ─────────────────────────────────────────────
    return _serialise(board, placed, traces, nets, violations, pour)


# ── Output ───────────────────────────────────────────────────────

def _serialise(
    board: Board,
    placed: list[PlacedComponent],
    traces: list[Trace],
    nets: list[Net],
    violations: list[DRCViolation],
    pour: CopperPour | None,
) -> dict:

    components_json = []
    for comp in placed:
        pads_json = []
        for pad in comp.footprint.pads:
            pads_json.append({
                "name": pad.name,
                "x": round(comp.x + pad.x, 3),
                "y": round(comp.y + pad.y, 3),
                "width": round(pad.width, 3),
                "height": round(pad.height, 3),
                "shape": pad.shape.value,
                "drill": round(pad.drill, 3),
                "net": pad.net,
            })

        silk_json = []
        for sl in comp.footprint.silkscreen:
            silk_json.append({
                "x1": round(comp.x + sl.x1, 3),
                "y1": round(comp.y + sl.y1, 3),
                "x2": round(comp.x + sl.x2, 3),
                "y2": round(comp.y + sl.y2, 3),
            })

        components_json.append({
            "instanceId": comp.instance_id,
            "moduleId": comp.module_id,
            "name": comp.module_name,
            "x": round(comp.x, 3),
            "y": round(comp.y, 3),
            "width": round(comp.width, 3),
            "height": round(comp.height, 3),
            "pads": pads_json,
            "silkscreen": silk_json,
        })

    traces_json = []
    for t in traces:
        traces_json.append({
            "netName": t.net_name,
            "width": round(t.width, 3),
            "points": [{"x": round(x, 3), "y": round(y, 3)} for x, y in t.points],
        })

    nets_json = []
    for n in nets:
        nets_json.append({
            "name": n.name,
            "pinCount": len(n.pins),
            "isGround": n.is_ground,
            "isPower": n.is_power,
        })

    drc_json = []
    for v in violations:
        drc_json.append({
            "kind": v.kind,
            "net": v.net,
            "x": round(v.x, 3),
            "y": round(v.y, 3),
            "detail": v.detail,
        })

    pour_json = None
    if pour:
        pour_json = {
            "net": pour.net,
            "clearance": pour.clearance,
            "padExclusions": [
                {"kind": e.kind, "cx": round(e.cx, 3), "cy": round(e.cy, 3), "radius": round(e.radius, 3)}
                for e in pour.pad_exclusions
            ],
            "traceExclusions": [
                {
                    "points": [{"x": round(x, 3), "y": round(y, 3)} for x, y in te.points],
                    "clearance": round(te.clearance, 3),
                }
                for te in pour.trace_exclusions
            ],
            "thermals": [
                {
                    "cx": round(th.cx, 3), "cy": round(th.cy, 3),
                    "outerRadius": round(th.outer_radius, 3),
                    "innerRadius": round(th.inner_radius, 3),
                    "spokeWidth": round(th.spoke_width, 3),
                    "spokeCount": th.spoke_count,
                }
                for th in pour.thermals
            ],
        }

    return {
        "board": {"width": board.width, "height": board.height},
        "units": {
            "coordinate": "mm",
            "pxPerMm": PX_PER_MM,
            "traceWidthDefault": TRACE_WIDTH_MM,
            "silkscreenWidth": SILKSCREEN_WIDTH_MM,
        },
        "components": components_json,
        "traces": traces_json,
        "nets": nets_json,
        "drc": drc_json,
        "copperPour": pour_json,
        "layer": "F.Cu",
    }

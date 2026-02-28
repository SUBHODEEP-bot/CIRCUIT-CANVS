"""
Main PCB generation engine — orchestrates the full pipeline:
  schematic JSON → netlist → footprint mapping → placement → routing → PCB JSON

Called by the Flask endpoint /api/generate-pcb.
"""

from __future__ import annotations
from .netlist import generate_netlist
from .footprints import get_footprint, Footprint
from .placement import place_components, PlacedComponent, Board
from .routing import route_nets, Trace


def generate_pcb(schematic: dict) -> dict:
    """
    Full PCB generation pipeline.

    Expected input (schematic JSON):
    {
      "modules": [
        {"instanceId": "...", "moduleId": "...", "moduleName": "ESP32",
         "category": "Microcontroller", "x": ..., "y": ...,
         "pins": [{"id": "pin-uuid", "name": "GPIO0", "pin_type": "Digital"}, ...]}
      ],
      "wires": [
        {"fromInstanceId": "...", "fromPinId": "...",
         "toInstanceId": "...", "toPinId": "...", "color": "..."}
      ]
    }

    Returns PCB layout JSON suitable for frontend rendering.
    """

    instances = schematic.get("modules", [])
    wires = schematic.get("wires", [])

    # 1. Generate netlist from wires
    nets = generate_netlist(wires)

    # 2. Map each instance to a PCB footprint
    instance_footprints: dict[str, Footprint] = {}
    for inst in instances:
        pin_count = len(inst.get("pins", []))
        fp = get_footprint(
            inst.get("moduleName", "Unknown"),
            inst.get("category"),
            max(pin_count, 2),
        )
        instance_footprints[inst["instanceId"]] = fp

    # Enrich instances with moduleName for placement
    enriched = []
    for inst in instances:
        enriched.append({
            **inst,
            "moduleName": inst.get("moduleName", "Unknown"),
        })

    # 3. Auto-place components on the board
    board, placed = place_components(enriched, instance_footprints)

    # 4. Build pin-to-pad mapping
    #    We map schematic pin IDs to footprint pad names by position index.
    pin_to_pad: dict[str, str] = {}
    for inst in instances:
        fp = instance_footprints.get(inst["instanceId"])
        if not fp:
            continue
        inst_pins = inst.get("pins", [])
        for idx, pin in enumerate(inst_pins):
            pad_name = fp.pads[idx].name if idx < len(fp.pads) else f"P{idx}"
            pin_to_pad[f"{inst['instanceId']}::{pin['id']}"] = pad_name

    # 5. Route nets
    traces = route_nets(nets, placed, pin_to_pad)

    # 6. Build output JSON
    return _build_output(board, placed, traces, nets)


def _build_output(
    board: Board,
    placed: list[PlacedComponent],
    traces: list[Trace],
    nets: list,
) -> dict:
    """Serialize the PCB layout to a JSON-friendly dict."""
    components_json = []
    for comp in placed:
        pads_json = []
        for pad in comp.footprint.pads:
            pads_json.append({
                "name": pad.name,
                "x": round(comp.x + pad.x, 2),
                "y": round(comp.y + pad.y, 2),
                "diameter": pad.diameter,
            })
        components_json.append({
            "instanceId": comp.instance_id,
            "moduleId": comp.module_id,
            "name": comp.module_name,
            "x": round(comp.x, 2),
            "y": round(comp.y, 2),
            "width": round(comp.width, 2),
            "height": round(comp.height, 2),
            "pads": pads_json,
        })

    traces_json = []
    for trace in traces:
        traces_json.append({
            "netName": trace.net_name,
            "width": trace.width,
            "points": [{"x": round(x, 2), "y": round(y, 2)} for x, y in trace.points],
        })

    nets_json = []
    for net in nets:
        nets_json.append({
            "name": net.name,
            "pinCount": len(net.pins),
        })

    return {
        "board": {
            "width": round(board.width, 2),
            "height": round(board.height, 2),
        },
        "components": components_json,
        "traces": traces_json,
        "nets": nets_json,
        "layer": "single",
    }

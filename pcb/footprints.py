"""
Footprint library — maps schematic module names / categories to
physical PCB footprint definitions.

Each footprint defines:
  - width / height in mm
  - list of pads with name, x, y offsets (relative to component origin),
    and pad diameter
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Pad:
    name: str
    x: float          # mm offset from component origin
    y: float          # mm offset from component origin
    diameter: float   # mm


@dataclass
class Footprint:
    name: str
    width: float      # mm
    height: float     # mm
    pads: list[Pad] = field(default_factory=list)


# Pre-built footprint library keyed by lowercase module name / category.
# When adding new modules in the admin panel, a matching entry here lets
# the PCB engine size the component realistically.
_FOOTPRINT_DB: dict[str, Footprint] = {
    "esp32": Footprint(
        name="ESP32",
        width=25.4,
        height=48.0,
        pads=[Pad(f"P{i}", x=(0 if i < 15 else 25.4), y=2.54 * (i % 15) + 2.54, diameter=1.0) for i in range(30)],
    ),
    "arduino nano": Footprint(
        name="Arduino Nano",
        width=18.0,
        height=45.0,
        pads=[Pad(f"P{i}", x=(0 if i < 15 else 18.0), y=2.54 * (i % 15) + 2.54, diameter=1.0) for i in range(30)],
    ),
    "mpu6050": Footprint(
        name="MPU6050",
        width=15.0,
        height=12.0,
        pads=[
            Pad("VCC", 0, 2.0, 0.8),
            Pad("GND", 0, 5.0, 0.8),
            Pad("SCL", 0, 8.0, 0.8),
            Pad("SDA", 0, 11.0, 0.8),
            Pad("AD0", 15.0, 2.0, 0.8),
            Pad("INT", 15.0, 5.0, 0.8),
            Pad("XDA", 15.0, 8.0, 0.8),
            Pad("XCL", 15.0, 11.0, 0.8),
        ],
    ),
    "led": Footprint(
        name="LED",
        width=5.0,
        height=3.0,
        pads=[Pad("A", 0, 1.5, 0.8), Pad("K", 5.0, 1.5, 0.8)],
    ),
    "resistor": Footprint(
        name="Resistor",
        width=6.0,
        height=2.5,
        pads=[Pad("1", 0, 1.25, 0.8), Pad("2", 6.0, 1.25, 0.8)],
    ),
    "capacitor": Footprint(
        name="Capacitor",
        width=5.0,
        height=3.0,
        pads=[Pad("1", 0, 1.5, 0.8), Pad("2", 5.0, 1.5, 0.8)],
    ),
    "sensor": Footprint(
        name="Sensor",
        width=12.0,
        height=10.0,
        pads=[
            Pad("VCC", 0, 2.0, 0.8),
            Pad("GND", 0, 5.0, 0.8),
            Pad("OUT", 0, 8.0, 0.8),
            Pad("EN", 12.0, 5.0, 0.8),
        ],
    ),
}


def _generate_generic_footprint(
    module_name: str, pin_count: int
) -> Footprint:
    """Generate a reasonable rectangular footprint for an unknown module."""
    rows = max(pin_count // 2, 1)
    pitch = 2.54
    width = 15.0
    height = max(rows * pitch + 4.0, 10.0)
    pads: list[Pad] = []
    for i in range(pin_count):
        side = 0.0 if i < (pin_count + 1) // 2 else width
        row = i if i < (pin_count + 1) // 2 else i - (pin_count + 1) // 2
        pads.append(Pad(f"P{i}", side, row * pitch + 2.0, 0.8))
    return Footprint(name=module_name, width=width, height=height, pads=pads)


def get_footprint(module_name: str, category: str | None, pin_count: int) -> Footprint:
    """
    Look up a footprint by module name or category.
    Falls back to a generic rectangular footprint.
    """
    key = module_name.strip().lower()
    if key in _FOOTPRINT_DB:
        return _FOOTPRINT_DB[key]

    if category:
        cat_key = category.strip().lower()
        if cat_key in _FOOTPRINT_DB:
            return _FOOTPRINT_DB[cat_key]

    return _generate_generic_footprint(module_name, pin_count)

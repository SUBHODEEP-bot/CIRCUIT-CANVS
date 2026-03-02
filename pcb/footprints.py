"""
Professional footprint library with pad geometry and silkscreen outlines.

Every footprint defines:
  - Pads with exact mm coordinates, shape, and drill size (if through-hole)
  - Silkscreen outline segments for the component body
  - Courtyard (bounding box with clearance for placement)

Pad coordinates are relative to the component origin (top-left corner).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class PadShape(Enum):
    CIRCLE = "circle"
    RECT   = "rect"
    OBLONG = "oblong"


@dataclass
class Pad:
    name: str
    x: float              # mm from component origin
    y: float              # mm from component origin
    width: float           # mm  (diameter for circles)
    height: float          # mm  (same as width for circles)
    shape: PadShape = PadShape.CIRCLE
    drill: float = 0.0    # mm — 0 means SMD pad, >0 means through-hole
    net: str = ""          # assigned during netlist binding


@dataclass
class SilkLine:
    """A single silkscreen line segment."""
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class Footprint:
    name: str
    width: float                   # mm — body width
    height: float                  # mm — body height
    pads: list[Pad] = field(default_factory=list)
    silkscreen: list[SilkLine] = field(default_factory=list)
    courtyard_margin: float = 0.5  # mm extra around body for placement clearance


def _rect_silk(w: float, h: float, inset: float = 0.3) -> list[SilkLine]:
    """Generate a rectangular silkscreen outline with pin-1 marker notch."""
    x0, y0 = inset, inset
    x1, y1 = w - inset, h - inset
    notch = min(2.0, (x1 - x0) * 0.15)
    return [
        SilkLine(x0 + notch, y0, x1, y0),   # top edge (after notch)
        SilkLine(x1, y0, x1, y1),            # right edge
        SilkLine(x1, y1, x0, y1),            # bottom edge
        SilkLine(x0, y1, x0, y0 + notch),    # left edge (stop before notch)
        SilkLine(x0, y0 + notch, x0 + notch, y0),  # pin-1 chamfer
    ]


def _dip_pads(
    pin_count: int, body_w: float, pitch: float = 2.54,
    pad_dia: float = 1.6, drill: float = 1.0,
    y_start: float = 2.54,
) -> list[Pad]:
    """Generate DIP through-hole pads — two columns along left/right edges."""
    half = pin_count // 2
    pads: list[Pad] = []
    for i in range(half):
        pads.append(Pad(
            name=f"{i + 1}",
            x=0, y=y_start + i * pitch,
            width=pad_dia, height=pad_dia,
            shape=PadShape.CIRCLE, drill=drill,
        ))
    for i in range(half):
        pads.append(Pad(
            name=f"{pin_count - i}",
            x=body_w, y=y_start + i * pitch,
            width=pad_dia, height=pad_dia,
            shape=PadShape.CIRCLE, drill=drill,
        ))
    return pads


def _header_pads(
    count: int, pitch: float = 2.54,
    pad_dia: float = 1.6, drill: float = 1.0,
    x_start: float = 1.27, y_start: float = 1.27,
    vertical: bool = True,
) -> list[Pad]:
    """Single-row pin header pads."""
    pads: list[Pad] = []
    for i in range(count):
        px = x_start if vertical else x_start + i * pitch
        py = y_start + i * pitch if vertical else y_start
        pads.append(Pad(
            name=f"{i + 1}", x=px, y=py,
            width=pad_dia, height=pad_dia,
            shape=PadShape.CIRCLE, drill=drill,
        ))
    return pads


# ══════════════════════════════════════════════════════════════════
#  FOOTPRINT DATABASE
# ══════════════════════════════════════════════════════════════════

_FOOTPRINT_DB: dict[str, Footprint] = {}


def _register(key: str, fp: Footprint):
    _FOOTPRINT_DB[key.lower()] = fp


# ── ESP32 DevKit (30-pin, 2×15 DIP @ 2.54 mm pitch) ─────────────
_esp32_w, _esp32_h = 25.4, 48.26
_register("esp32", Footprint(
    name="ESP32",
    width=_esp32_w, height=_esp32_h,
    pads=_dip_pads(30, _esp32_w, pitch=2.54, pad_dia=1.6, drill=1.0, y_start=2.54),
    silkscreen=_rect_silk(_esp32_w, _esp32_h),
))

# ── Arduino Nano (30-pin DIP @ 2.54 mm) ─────────────────────────
_nano_w, _nano_h = 18.0, 45.0
_register("arduino nano", Footprint(
    name="Arduino Nano",
    width=_nano_w, height=_nano_h,
    pads=_dip_pads(30, _nano_w, pitch=2.54, pad_dia=1.6, drill=1.0, y_start=2.54),
    silkscreen=_rect_silk(_nano_w, _nano_h),
))

# ── Arduino Uno (wide DIP shield headers) ───────────────────────
_uno_w, _uno_h = 53.34, 68.58
_register("arduino uno", Footprint(
    name="Arduino Uno",
    width=_uno_w, height=_uno_h,
    pads=_dip_pads(28, _uno_w, pitch=2.54, pad_dia=1.6, drill=1.0, y_start=5.0),
    silkscreen=_rect_silk(_uno_w, _uno_h),
))

# ── MPU6050 breakout (8-pin header @ 2.54 mm) ───────────────────
_mpu_w, _mpu_h = 15.24, 20.32
_register("mpu6050", Footprint(
    name="MPU6050",
    width=_mpu_w, height=_mpu_h,
    pads=[
        Pad("VCC", 0,       2.54, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("GND", 0,       5.08, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("SCL", 0,       7.62, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("SDA", 0,      10.16, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("XDA", _mpu_w, 2.54, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("XCL", _mpu_w, 5.08, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("AD0", _mpu_w, 7.62, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("INT", _mpu_w, 10.16, 1.6, 1.6, PadShape.CIRCLE, 1.0),
    ],
    silkscreen=_rect_silk(_mpu_w, _mpu_h),
))

# ── OLED 0.96″ (4-pin I2C header) ───────────────────────────────
_oled_w, _oled_h = 27.0, 27.0
_register("oled", Footprint(
    name="OLED 0.96\"",
    width=_oled_w, height=_oled_h,
    pads=[
        Pad("GND", 7.62,  _oled_h, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("VCC", 10.16, _oled_h, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("SCL", 12.70, _oled_h, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("SDA", 15.24, _oled_h, 1.6, 1.6, PadShape.CIRCLE, 1.0),
    ],
    silkscreen=_rect_silk(_oled_w, _oled_h),
))

# ── DHT11 / DHT22 sensor (3 usable pins) ────────────────────────
_dht_w, _dht_h = 12.0, 20.0
_register("dht11", Footprint(
    name="DHT11",
    width=_dht_w, height=_dht_h,
    pads=[
        Pad("VCC",  2.54, _dht_h, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("DATA", 5.08, _dht_h, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("GND",  9.46, _dht_h, 1.6, 1.6, PadShape.CIRCLE, 1.0),
    ],
    silkscreen=_rect_silk(_dht_w, _dht_h),
))
_register("dht22", _FOOTPRINT_DB["dht11"])

# ── HC-SR04 ultrasonic (4-pin header) ────────────────────────────
_hcsr_w, _hcsr_h = 45.0, 20.0
_register("hc-sr04", Footprint(
    name="HC-SR04",
    width=_hcsr_w, height=_hcsr_h,
    pads=[
        Pad("VCC",  15.24, 0, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("TRIG", 17.78, 0, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("ECHO", 20.32, 0, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("GND",  22.86, 0, 1.6, 1.6, PadShape.CIRCLE, 1.0),
    ],
    silkscreen=_rect_silk(_hcsr_w, _hcsr_h),
))

# ── Passive: LED (2-pin, 5 mm radial) ───────────────────────────
_register("led", Footprint(
    name="LED 5mm",
    width=6.0, height=5.0,
    pads=[
        Pad("A", 1.27, 2.54, 1.6, 1.6, PadShape.CIRCLE, 0.8),
        Pad("K", 4.73, 2.54, 1.6, 1.6, PadShape.RECT,   0.8),
    ],
    silkscreen=[
        SilkLine(0.3, 0.3, 5.7, 0.3), SilkLine(5.7, 0.3, 5.7, 4.7),
        SilkLine(5.7, 4.7, 0.3, 4.7), SilkLine(0.3, 4.7, 0.3, 0.3),
    ],
))

# ── Passive: Resistor (axial, 2-pin) ────────────────────────────
_register("resistor", Footprint(
    name="Resistor",
    width=10.16, height=4.0,
    pads=[
        Pad("1", 0,     2.0, 1.6, 1.6, PadShape.CIRCLE, 0.8),
        Pad("2", 10.16, 2.0, 1.6, 1.6, PadShape.CIRCLE, 0.8),
    ],
    silkscreen=[
        SilkLine(2.0, 0.5, 8.16, 0.5), SilkLine(8.16, 0.5, 8.16, 3.5),
        SilkLine(8.16, 3.5, 2.0, 3.5),  SilkLine(2.0, 3.5, 2.0, 0.5),
    ],
))

# ── Passive: Capacitor (radial, 2-pin) ──────────────────────────
_register("capacitor", Footprint(
    name="Capacitor",
    width=5.08, height=5.08,
    pads=[
        Pad("1", 1.27, 2.54, 1.6, 1.6, PadShape.CIRCLE, 0.8),
        Pad("2", 3.81, 2.54, 1.6, 1.6, PadShape.CIRCLE, 0.8),
    ],
    silkscreen=[
        SilkLine(0.3, 0.3, 4.78, 0.3), SilkLine(4.78, 0.3, 4.78, 4.78),
        SilkLine(4.78, 4.78, 0.3, 4.78), SilkLine(0.3, 4.78, 0.3, 0.3),
    ],
))

# ── Generic sensor breakout ──────────────────────────────────────
_register("sensor", Footprint(
    name="Sensor",
    width=15.24, height=12.7,
    pads=[
        Pad("VCC", 0,     2.54, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("GND", 0,     5.08, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("OUT", 0,     7.62, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("EN",  15.24, 5.08, 1.6, 1.6, PadShape.CIRCLE, 1.0),
    ],
    silkscreen=_rect_silk(15.24, 12.7),
))

# ── Relay module (3-pin control + 3-pin output) ─────────────────
_relay_w, _relay_h = 33.0, 25.0
_register("relay", Footprint(
    name="Relay Module",
    width=_relay_w, height=_relay_h,
    pads=[
        Pad("VCC",  0, 5.0,  1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("GND",  0, 10.0, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("IN",   0, 15.0, 1.6, 1.6, PadShape.CIRCLE, 1.0),
        Pad("COM",  _relay_w, 5.0,  2.0, 2.0, PadShape.CIRCLE, 1.2),
        Pad("NO",   _relay_w, 12.5, 2.0, 2.0, PadShape.CIRCLE, 1.2),
        Pad("NC",   _relay_w, 20.0, 2.0, 2.0, PadShape.CIRCLE, 1.2),
    ],
    silkscreen=_rect_silk(_relay_w, _relay_h),
))


# ══════════════════════════════════════════════════════════════════
#  GENERIC FOOTPRINT GENERATOR (fallback for unknown modules)
# ══════════════════════════════════════════════════════════════════

def _generate_generic_footprint(module_name: str, pin_count: int) -> Footprint:
    """
    Build a dual-row DIP-style footprint for any module not in the DB.
    Pin count is distributed evenly across left/right columns.
    """
    pitch = 2.54
    half = max(pin_count // 2, 1)
    body_w = 15.24
    body_h = max(half * pitch + 4.0, 10.16)

    pads: list[Pad] = []
    for i in range(half):
        pads.append(Pad(
            name=f"{i + 1}",
            x=0, y=pitch + i * pitch,
            width=1.6, height=1.6,
            shape=PadShape.CIRCLE, drill=1.0,
        ))
    remainder = pin_count - half
    for i in range(remainder):
        pads.append(Pad(
            name=f"{pin_count - i}",
            x=body_w, y=pitch + i * pitch,
            width=1.6, height=1.6,
            shape=PadShape.CIRCLE, drill=1.0,
        ))

    return Footprint(
        name=module_name,
        width=body_w, height=body_h,
        pads=pads,
        silkscreen=_rect_silk(body_w, body_h),
    )


def get_footprint(module_name: str, category: str | None, pin_count: int) -> Footprint:
    """
    Resolve a footprint by module name, then category, then generic fallback.
    Returns a deep-ish copy so callers can mutate pad nets freely.
    """
    import copy

    key = module_name.strip().lower()
    if key in _FOOTPRINT_DB:
        return copy.deepcopy(_FOOTPRINT_DB[key])

    if category:
        cat_key = category.strip().lower()
        if cat_key in _FOOTPRINT_DB:
            return copy.deepcopy(_FOOTPRINT_DB[cat_key])

    return _generate_generic_footprint(module_name, max(pin_count, 2))

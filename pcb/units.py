"""
Unit system for PCB layout — all internal calculations use millimetres.

Provides conversion utilities and industry-standard design rules
so every dimension in the engine maps to a physically manufacturable board.
"""

from __future__ import annotations

# ── Conversion constants ──────────────────────────────────────────
MM_PER_MIL  = 0.0254          # 1 mil = 0.0254 mm
MIL_PER_MM  = 1.0 / MM_PER_MIL
MM_PER_INCH = 25.4
INCH_PER_MM = 1.0 / MM_PER_INCH

# Screen pixels  ↔  physical mm   (used by the frontend renderer)
# This is the "scale factor" the frontend multiplies mm values by
# to get canvas pixels.  Changing it here lets us zoom the whole
# board without touching rendering code.
PX_PER_MM = 6.0               # 6 px on screen ≈ 1 mm on the board


def mm_to_mil(mm: float) -> float:
    return mm * MIL_PER_MM


def mil_to_mm(mil: float) -> float:
    return mil * MM_PER_MIL


def mm_to_px(mm: float) -> float:
    return mm * PX_PER_MM


def px_to_mm(px: float) -> float:
    return px / PX_PER_MM


def inch_to_mm(inch: float) -> float:
    return inch * MM_PER_INCH


def mm_to_units(mm: float) -> float:
    """Convert millimeters to internal units (pixels)."""
    return mm_to_px(mm)


# ── Standard design rules (IPC Class 2 — general electronics) ─────
TRACE_WIDTH_MM       = 0.254     # 10 mil — standard signal trace
TRACE_WIDTH_POWER_MM = 0.508     # 20 mil — power / GND trace
CLEARANCE_MM         = 0.254     # 10 mil — minimum copper-to-copper gap
PAD_ANNULAR_RING_MM  = 0.254     # 10 mil annular ring
VIA_DRILL_MM         = 0.3
VIA_ANNULAR_MM       = 0.15
SOLDER_MASK_EXPANSION = 0.05     # 2 mil mask expansion per side
SILKSCREEN_WIDTH_MM  = 0.15      # line width for silkscreen outlines
BOARD_EDGE_CLEARANCE = 0.5       # keep copper 0.5 mm from board edge

# Copper pour
POUR_CLEARANCE_MM    = 0.3       # gap between pour and foreign copper
THERMAL_SPOKE_WIDTH  = 0.3       # thermal relief spoke width
THERMAL_GAP_MM       = 0.25      # gap in thermal relief

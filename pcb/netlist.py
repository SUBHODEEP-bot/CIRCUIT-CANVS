"""
Global netlist generator — builds electrically-correct nets from
schematic wires and auto-detects power/ground nets by pin name.

Every trace on the PCB is validated against this netlist: only pins
belonging to the same Net are allowed to be routed together.
"""

from __future__ import annotations
from dataclasses import dataclass, field

# Pin names that are auto-assigned to the global GND net
_GND_NAMES = frozenset({"gnd", "vss", "gnd0", "agnd", "dgnd", "pgnd"})

# Pin names that are auto-assigned to a global power net
_VCC_NAMES = frozenset({"vcc", "vdd", "vin", "3v3", "3.3v", "5v", "v+"})


@dataclass
class Net:
    name: str
    pins: list[tuple[str, str]] = field(default_factory=list)
    is_power: bool = False
    is_ground: bool = False


class _UnionFind:
    """Path-compressed union-find for O(α(n)) net merging."""

    def __init__(self):
        self._parent: dict[str, str] = {}
        self._rank: dict[str, int] = {}

    def find(self, x: str) -> str:
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: str, b: str):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1


def _pin_key(instance_id: str, pin_id: str) -> str:
    return f"{instance_id}::{pin_id}"


def generate_netlist(
    wires: list[dict],
    instances: list[dict] | None = None,
) -> list[Net]:
    """
    Build a global netlist.

    Parameters
    ----------
    wires : list[dict]
        Each wire has fromInstanceId, fromPinId, toInstanceId, toPinId.
    instances : list[dict] | None
        Module instances with their pin lists. Used to auto-detect
        power/ground nets by pin name.

    Returns
    -------
    list[Net]  sorted by net name.
    """
    uf = _UnionFind()

    # Build a lookup: pin_key → pin_name (lowercase) for power/GND detection
    pin_name_map: dict[str, str] = {}
    if instances:
        for inst in instances:
            for pin in inst.get("pins", []):
                key = _pin_key(inst["instanceId"], pin["id"])
                pin_name_map[key] = (pin.get("name") or "").strip().lower()

    # ── Auto-merge all GND pins into one global GND net ──────────
    gnd_keys: list[str] = []
    vcc_keys: list[str] = []
    for key, name in pin_name_map.items():
        if name in _GND_NAMES:
            gnd_keys.append(key)
        elif name in _VCC_NAMES:
            vcc_keys.append(key)

    for i in range(1, len(gnd_keys)):
        uf.union(gnd_keys[0], gnd_keys[i])
    for i in range(1, len(vcc_keys)):
        uf.union(vcc_keys[0], vcc_keys[i])

    # ── Merge pins connected by wires ────────────────────────────
    all_keys: set[str] = set()
    for w in wires:
        a = _pin_key(w["fromInstanceId"], w["fromPinId"])
        b = _pin_key(w["toInstanceId"], w["toPinId"])
        uf.union(a, b)
        all_keys.update((a, b))

    # Include power/gnd keys even if they have no explicit wires
    all_keys.update(gnd_keys)
    all_keys.update(vcc_keys)

    # ── Group by root ────────────────────────────────────────────
    groups: dict[str, list[tuple[str, str]]] = {}
    for key in all_keys:
        root = uf.find(key)
        inst_id, pin_id = key.split("::", 1)
        groups.setdefault(root, []).append((inst_id, pin_id))

    # ── Assign meaningful names ──────────────────────────────────
    gnd_root = uf.find(gnd_keys[0]) if gnd_keys else None
    vcc_root = uf.find(vcc_keys[0]) if vcc_keys else None

    nets: list[Net] = []
    signal_idx = 0
    for root, pins in sorted(groups.items()):
        if root == gnd_root:
            nets.append(Net(name="GND", pins=pins, is_ground=True))
        elif root == vcc_root:
            nets.append(Net(name="VCC", pins=pins, is_power=True))
        else:
            nets.append(Net(name=f"N{signal_idx}", pins=pins))
            signal_idx += 1

    return nets

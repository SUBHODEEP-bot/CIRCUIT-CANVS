"""
Netlist generator — groups connected pins into electrical nets.

Input:  schematic JSON with components (placed module instances) and
        connections (wires between pins).
Output: list of Net objects, each containing the set of
        (instance_id, pin_id) tuples that are electrically connected.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Net:
    name: str
    pins: list[tuple[str, str]] = field(default_factory=list)


class UnionFind:
    """Simple union-find to merge connected pins into nets."""

    def __init__(self):
        self._parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        if x not in self._parent:
            self._parent[x] = x
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


def _pin_key(instance_id: str, pin_id: str) -> str:
    return f"{instance_id}::{pin_id}"


def generate_netlist(wires: list[dict]) -> list[Net]:
    """
    Build a netlist from the wire list.

    Each wire has:
        fromInstanceId, fromPinId, toInstanceId, toPinId
    """
    uf = UnionFind()

    for w in wires:
        a = _pin_key(w["fromInstanceId"], w["fromPinId"])
        b = _pin_key(w["toInstanceId"], w["toPinId"])
        uf.union(a, b)

    # Group pins by their root representative
    groups: dict[str, list[tuple[str, str]]] = {}
    all_keys: set[str] = set()
    for w in wires:
        all_keys.add(_pin_key(w["fromInstanceId"], w["fromPinId"]))
        all_keys.add(_pin_key(w["toInstanceId"], w["toPinId"]))

    for key in all_keys:
        root = uf.find(key)
        groups.setdefault(root, [])
        inst_id, pin_id = key.split("::", 1)
        groups[root].append((inst_id, pin_id))

    nets: list[Net] = []
    for idx, (_, pins) in enumerate(sorted(groups.items())):
        nets.append(Net(name=f"NET{idx}", pins=pins))

    return nets

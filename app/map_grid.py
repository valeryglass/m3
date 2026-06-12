# app/map_grid.py

"""Discrete grid layer for map visualization.

This module answers:

* which cells exist?
* which district owns which cells?
* where are borders between territories?

It does NOT:

* generate map_payload
* decide semantic meaning
* render SVG/HTML
  """

from **future** import annotations

from dataclasses import dataclass
from typing import Iterable

from app.map_topology import MapTopology, TopologyNode

@dataclass(frozen=True)
class GridCell:
q: int
r: int
x: float
y: float
owner_id: str | None
tags: tuple[str, ...] = ()

@dataclass(frozen=True)
class GridModel:
kind: str
width: int
height: int
cell_size: float
cells: tuple[GridCell, ...]

def build_hex_grid(
topology: MapTopology,
*,
cell_size: float = 28.0,
) -> GridModel:
"""Build deterministic hex grid and assign ownership to topology nodes.

```
v0 goal:
- create hex cells inside topology bounds
- assign each cell to nearest district node
- limit ownership radius using node.radius_hint

This is a grid layer, not terrain.
"""
cells: list[GridCell] = []

# Pointy-top axial hex approximation.
# Good enough for SVG/debug renderer.
cols = int(topology.width / (cell_size * 1.5)) + 2
rows = int(topology.height / (cell_size * 1.75)) + 2

nodes = list(topology.nodes)

for q in range(cols):
    for r in range(rows):
        x = cell_size * 1.5 * q
        y = cell_size * (3**0.5) * (r + 0.5 * (q % 2))

        if x > topology.width or y > topology.height:
            continue

        owner = _nearest_owner(x, y, nodes)

        cells.append(
            GridCell(
                q=q,
                r=r,
                x=x,
                y=y,
                owner_id=owner.entity_id if owner else None,
                tags=(f"owner:{owner.entity_id}",) if owner else (),
            )
        )

return GridModel(
    kind="hex",
    width=topology.width,
    height=topology.height,
    cell_size=cell_size,
    cells=tuple(cells),
)
```

def _nearest_owner(
x: float,
y: float,
nodes: Iterable[TopologyNode],
) -> TopologyNode | None:
"""Return nearest node if point lies inside its radius hint.

```
TODO(agent):
Later version may use weighted Voronoi / territory growth instead of nearest center.
"""
best_node: TopologyNode | None = None
best_dist_sq: float | None = None

for node in nodes:
    dx = x - node.x
    dy = y - node.y
    dist_sq = dx * dx + dy * dy

    if dist_sq > node.radius_hint * node.radius_hint:
        continue

    if best_dist_sq is None or dist_sq < best_dist_sq:
        best_node = node
        best_dist_sq = dist_sq

return best_node
```

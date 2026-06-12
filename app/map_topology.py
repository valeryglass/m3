# app/map_topology.py

"""Renderer-neutral spatial topology for map payloads.

This module answers:

* what map entities become spatial nodes?
* what nodes are near each other?
* where are approximate continuous centers?

It does NOT:

* render SVG/HTML
* create grid cells
* modify map_payload contract
  """

from **future** import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class TopologyNode:
id: str
entity_id: str
entity_type: str
label: str
x: float
y: float
weight: float
radius_hint: float
similarity_keys: tuple[str, ...]

@dataclass(frozen=True)
class TopologyEdge:
id: str
from_node: str
to_node: str
kind: str
strength: float

@dataclass(frozen=True)
class MapTopology:
width: int
height: int
nodes: tuple[TopologyNode, ...]
edges: tuple[TopologyEdge, ...]

def build_topology(
payload: dict[str, Any],
*,
width: int = 1200,
height: int = 800,
) -> MapTopology:
"""Build deterministic continuous topology from map_payload.

```
Initial version should mostly extract district nodes and neighbor edges.
Later versions can include gates, roads, destinations, landmarks.
"""
entities = payload.get("entities", [])
neighbors = payload.get("neighbors", [])

districts = [e for e in entities if e.get("type") == "district"]

# TODO(agent): reuse existing district positioning logic from map_payload_html.py
# or move it here if already implemented there.
positions = _district_positions_stub(districts, neighbors, width / 2, height / 2)

nodes: list[TopologyNode] = []
for entity in districts:
    entity_id = str(entity.get("id", ""))
    metrics = entity.get("metrics", {}) or {}
    hints = entity.get("compiler_hints", {}) or {}

    x, y = positions.get(entity_id, (width / 2, height / 2))

    nodes.append(
        TopologyNode(
            id=f"node-{entity_id}",
            entity_id=entity_id,
            entity_type="district",
            label=str(entity.get("label", entity_id)),
            x=float(x),
            y=float(y),
            weight=float(metrics.get("weight", 0.0) or 0.0),
            radius_hint=40.0 + 60.0 * float(metrics.get("weight", 0.0) or 0.0),
            similarity_keys=tuple(hints.get("semantic_similarity_keys", []) or []),
        )
    )

node_ids = {node.entity_id: node.id for node in nodes}

edges: list[TopologyEdge] = []
for index, neighbor in enumerate(sorted(neighbors, key=lambda n: str(n.get("id", "")))):
    source = str(neighbor.get("from", ""))
    target = str(neighbor.get("to", ""))
    if source not in node_ids or target not in node_ids:
        continue

    edges.append(
        TopologyEdge(
            id=str(neighbor.get("id") or f"topology-edge-{index + 1}"),
            from_node=node_ids[source],
            to_node=node_ids[target],
            kind="neighbor",
            strength=float(neighbor.get("score", neighbor.get("weight", 0.0)) or 0.0),
        )
    )

return MapTopology(width=width, height=height, nodes=tuple(nodes), edges=tuple(edges))
```

def _district_positions_stub(
districts: list[dict[str, Any]],
neighbors: list[dict[str, Any]],
center_x: float,
center_y: float,
) -> dict[str, tuple[float, float]]:
"""Temporary placeholder.

```
TODO(agent):
Replace with extracted deterministic force layout from map_payload_html.py.
This function exists only to make the module boundary explicit.
"""
if not districts:
    return {}

if len(districts) == 1:
    return {str(districts[0]["id"]): (center_x, center_y)}

# Simple deterministic fallback line. Not final layout.
step = 80.0
start = center_x - step * (len(districts) - 1) / 2
return {
    str(entity["id"]): (start + index * step, center_y)
    for index, entity in enumerate(districts)
}
```

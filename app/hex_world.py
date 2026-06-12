from __future__ import annotations

"""Hex-world spatial compiler for map payloads.

The hex world is a derived, renderer-neutral layout artifact:

```
map_payload -> map_topology -> hex_world -> renderer
```

It should be rebuildable from current data. It must not write coordinates back
into episodes, annotation-runs, or the map payload contract.
"""

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from app.map_grid import (
    GridCell,
    HexCoord,
    axial_to_pixel,
    build_hex_grid,
    hex_line,
    hex_neighbors,
    parse_hex_id,
    pixel_to_axial,
)
from app.map_topology import MapTopology, TopologyEntity, build_topology


VERSION = "0.1"


@dataclass(frozen=True)
class RegionPlacement:
    id: str
    source_entity_id: str
    source_entity_type: str
    label: str
    anchor_cell_id: str
    cell_ids: tuple[str, ...]
    border_cell_ids: tuple[str, ...]


@dataclass(frozen=True)
class HexPath:
    id: str
    kind: str
    from_region_id: str
    to_region_id: str
    cell_ids: tuple[str, ...]
    source_id: str | None = None


@dataclass(frozen=True)
class HexFieldCell:
    cell_id: str
    weight: float


@dataclass(frozen=True)
class HexField:
    id: str
    source_entity_id: str
    source_entity_type: str
    layer: str
    cells: tuple[HexFieldCell, ...]


@dataclass(frozen=True)
class HexAnchor:
    id: str
    source_entity_id: str
    source_entity_type: str
    kind: str
    cell_id: str
    label: str


@dataclass(frozen=True)
class HexBoundary:
    id: str
    between_cell_ids: tuple[str, str]
    between_region_ids: tuple[str, str]
    tags: tuple[str, ...] = ("border",)


@dataclass(frozen=True)
class HexWorld:
    kind: str
    version: str
    source: str | None
    width: int
    height: int
    cell_size: float
    orientation: str
    coordinate_system: str
    cells: tuple[GridCell, ...]
    regions: tuple[RegionPlacement, ...]
    paths: tuple[HexPath, ...]
    fields: tuple[HexField, ...]
    anchors: tuple[HexAnchor, ...]
    boundaries: tuple[HexBoundary, ...]
    provenance: dict[str, Any]


def build_hex_world(
    payload: dict[str, Any],
    *,
    width: int = 1200,
    height: int = 800,
    cell_size: float = 28.0,
) -> HexWorld:
    """Compile semantic map payload into a generative hex-world layout."""

    topology = build_topology(payload, width=width, height=height)
    grid = build_hex_grid(topology, cell_size=cell_size)
    cell_by_id = {cell.id: cell for cell in grid.cells}
    region_by_id = {entity.id: entity for entity in topology.entities if entity.spatial_role == "region"}

    regions = _region_placements(topology, grid.cells, cell_size=cell_size)
    paths = _straight_paths(topology, cell_size=cell_size)
    fields = _climate_fields(payload, regions)
    anchors = _anchors(payload, regions)
    boundaries = _boundaries(grid.cells, cell_by_id)

    return HexWorld(
        kind="hex_world",
        version=VERSION,
        source=payload.get("source"),
        width=width,
        height=height,
        cell_size=cell_size,
        orientation=grid.orientation,
        coordinate_system=grid.coordinate_system,
        cells=grid.cells,
        regions=regions,
        paths=paths,
        fields=fields,
        anchors=anchors,
        boundaries=boundaries,
        provenance={
            "generated_from": "map_payload",
            "map_payload_version": payload.get("version"),
            "temporary_region_source_types": sorted({entity.source_entity_type for entity in region_by_id.values()}),
            "layout_policy": "generative_no_position_lock",
            "road_policy": "straight_hex_line_between_region_anchors",
        },
    )


def hex_world_to_dict(world: HexWorld) -> dict[str, Any]:
    return {
        "kind": world.kind,
        "version": world.version,
        "source": world.source,
        "grid": {
            "width": world.width,
            "height": world.height,
            "cell_size": world.cell_size,
            "orientation": world.orientation,
            "coordinate_system": world.coordinate_system,
        },
        "cells": [
            {
                "id": cell.id,
                "q": cell.q,
                "r": cell.r,
                "s": cell.s,
                "x": round(cell.x, 3),
                "y": round(cell.y, 3),
                "owner_id": cell.owner_id,
                "tags": list(cell.tags),
            }
            for cell in world.cells
        ],
        "regions": [
            {
                "id": region.id,
                "source_entity_id": region.source_entity_id,
                "source_entity_type": region.source_entity_type,
                "label": region.label,
                "anchor_cell_id": region.anchor_cell_id,
                "cell_ids": list(region.cell_ids),
                "border_cell_ids": list(region.border_cell_ids),
            }
            for region in world.regions
        ],
        "paths": [
            {
                "id": path.id,
                "kind": path.kind,
                "from_region_id": path.from_region_id,
                "to_region_id": path.to_region_id,
                "cell_ids": list(path.cell_ids),
                "source_id": path.source_id,
            }
            for path in world.paths
        ],
        "fields": [
            {
                "id": field.id,
                "source_entity_id": field.source_entity_id,
                "source_entity_type": field.source_entity_type,
                "layer": field.layer,
                "cells": [
                    {"cell_id": cell.cell_id, "weight": cell.weight}
                    for cell in field.cells
                ],
            }
            for field in world.fields
        ],
        "anchors": [
            {
                "id": anchor.id,
                "source_entity_id": anchor.source_entity_id,
                "source_entity_type": anchor.source_entity_type,
                "kind": anchor.kind,
                "cell_id": anchor.cell_id,
                "label": anchor.label,
            }
            for anchor in world.anchors
        ],
        "boundaries": [
            {
                "id": boundary.id,
                "between_cell_ids": list(boundary.between_cell_ids),
                "between_region_ids": list(boundary.between_region_ids),
                "tags": list(boundary.tags),
            }
            for boundary in world.boundaries
        ],
        "provenance": world.provenance,
    }


def write_hex_world(
    payload: dict[str, Any],
    output_path: Path,
    *,
    width: int = 1200,
    height: int = 800,
    cell_size: float = 28.0,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    world = build_hex_world(payload, width=width, height=height, cell_size=cell_size)
    output_path.write_text(json.dumps(hex_world_to_dict(world), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def _region_placements(
    topology: MapTopology,
    cells: tuple[GridCell, ...],
    *,
    cell_size: float,
) -> tuple[RegionPlacement, ...]:
    cells_by_owner: dict[str, list[str]] = defaultdict(list)
    for cell in cells:
        if cell.owner_id:
            cells_by_owner[cell.owner_id].append(cell.id)

    placements: list[RegionPlacement] = []
    for entity in sorted(topology.entities, key=lambda item: item.id):
        if entity.spatial_role != "region":
            continue
        anchor = pixel_to_axial(entity.x, entity.y, cell_size=cell_size).id
        owned = tuple(sorted(cells_by_owner.get(entity.id, []), key=_cell_sort_key))
        placements.append(
            RegionPlacement(
                id=entity.id,
                source_entity_id=entity.source_entity_id,
                source_entity_type=entity.source_entity_type,
                label=entity.label,
                anchor_cell_id=anchor,
                cell_ids=owned,
                border_cell_ids=_border_cell_ids(owned, cells),
            )
        )
    return tuple(placements)


def _straight_paths(topology: MapTopology, *, cell_size: float) -> tuple[HexPath, ...]:
    entity_by_id = {entity.id: entity for entity in topology.entities}
    paths: list[HexPath] = []
    for relation in topology.relations:
        source = entity_by_id.get(relation.from_entity_id)
        target = entity_by_id.get(relation.to_entity_id)
        if source is None or target is None:
            continue
        source_cell = pixel_to_axial(source.x, source.y, cell_size=cell_size)
        target_cell = pixel_to_axial(target.x, target.y, cell_size=cell_size)
        paths.append(
            HexPath(
                id=f"path:{relation.id}",
                kind="straight_hex_relation",
                from_region_id=source.id,
                to_region_id=target.id,
                cell_ids=tuple(coord.id for coord in hex_line(source_cell, target_cell)),
                source_id=relation.source_id,
            )
        )
    return tuple(paths)


def _climate_fields(payload: dict[str, Any], regions: tuple[RegionPlacement, ...]) -> tuple[HexField, ...]:
    entities_by_id = {str(entity.get("id") or ""): entity for entity in payload.get("entities", []) or []}
    regions_by_source_id = {region.source_entity_id: region for region in regions}
    field_cells: dict[str, dict[str, float]] = defaultdict(dict)

    for link in payload.get("links", []) or []:
        if str(link.get("type") or "") != "climate_to_district":
            continue
        climate_id = str(link.get("from") or "")
        region = regions_by_source_id.get(str(link.get("to") or ""))
        climate = entities_by_id.get(climate_id)
        if region is None or climate is None or climate.get("type") != "climate":
            continue
        weight = _safe_weight(link.get("weight"))
        for cell_id in region.cell_ids:
            field_cells[climate_id][cell_id] = max(weight, field_cells[climate_id].get(cell_id, 0.0))

    fields: list[HexField] = []
    for climate_id, cells in sorted(field_cells.items()):
        climate = entities_by_id[climate_id]
        fields.append(
            HexField(
                id=f"field:{climate_id}",
                source_entity_id=climate_id,
                source_entity_type="climate",
                layer="climate",
                cells=tuple(
                    HexFieldCell(cell_id=cell_id, weight=round(weight, 3))
                    for cell_id, weight in sorted(cells.items(), key=lambda item: _cell_sort_key(item[0]))
                ),
            )
        )
    return tuple(fields)


def _anchors(payload: dict[str, Any], regions: tuple[RegionPlacement, ...]) -> tuple[HexAnchor, ...]:
    """Create minimal anchored non-region entities.

    First slice anchors landmarks/gates/crossroads to the first linked region when
    available. This preserves the boundary for future true edge/vertex anchors.
    """

    anchor_types = {"gate", "landmark", "crossroads", "destination"}
    entities_by_id = {str(entity.get("id") or ""): entity for entity in payload.get("entities", []) or []}
    regions_by_source_id = {region.source_entity_id: region for region in regions}
    links = payload.get("links", []) or []
    anchors: list[HexAnchor] = []

    for entity_id, entity in sorted(entities_by_id.items()):
        entity_type = str(entity.get("type") or "")
        if entity_type not in anchor_types:
            continue
        linked_region = _linked_region(entity_id, links, regions_by_source_id)
        if linked_region is None:
            continue
        anchors.append(
            HexAnchor(
                id=f"anchor:{entity_id}",
                source_entity_id=entity_id,
                source_entity_type=entity_type,
                kind=entity_type,
                cell_id=linked_region.anchor_cell_id,
                label=str(entity.get("label") or entity_id),
            )
        )
    return tuple(anchors)


def _boundaries(cells: tuple[GridCell, ...], cell_by_id: dict[str, GridCell]) -> tuple[HexBoundary, ...]:
    boundaries: dict[str, HexBoundary] = {}
    for cell in cells:
        if cell.owner_id is None:
            continue
        for neighbor in hex_neighbors(HexCoord(cell.q, cell.r)):
            neighbor_cell = cell_by_id.get(neighbor.id)
            if neighbor_cell is None or neighbor_cell.owner_id is None:
                continue
            if neighbor_cell.owner_id == cell.owner_id:
                continue
            cell_pair = tuple(sorted((cell.id, neighbor_cell.id), key=_cell_sort_key))
            owner_pair = tuple(sorted((cell.owner_id, neighbor_cell.owner_id)))
            boundary_id = f"boundary:{cell_pair[0]}:{cell_pair[1]}"
            boundaries[boundary_id] = HexBoundary(
                id=boundary_id,
                between_cell_ids=cell_pair,
                between_region_ids=owner_pair,
            )
    return tuple(boundaries[key] for key in sorted(boundaries))


def _border_cell_ids(owned: tuple[str, ...], cells: tuple[GridCell, ...]) -> tuple[str, ...]:
    owned_set = set(owned)
    if not owned_set:
        return ()
    all_cell_ids = {cell.id for cell in cells}
    border: list[str] = []
    for cell_id in owned:
        coord = parse_hex_id(cell_id)
        if any(neighbor.id not in owned_set and neighbor.id in all_cell_ids for neighbor in hex_neighbors(coord)):
            border.append(cell_id)
    return tuple(sorted(border, key=_cell_sort_key))


def _linked_region(entity_id: str, links: list[dict[str, Any]], regions_by_source_id: dict[str, RegionPlacement]) -> RegionPlacement | None:
    for link in links:
        source = str(link.get("from") or "")
        target = str(link.get("to") or "")
        if source == entity_id and target in regions_by_source_id:
            return regions_by_source_id[target]
        if target == entity_id and source in regions_by_source_id:
            return regions_by_source_id[source]
    return None


def _cell_sort_key(cell_id: str) -> tuple[int, int]:
    coord = parse_hex_id(cell_id)
    return (coord.q, coord.r)


def _safe_weight(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0

from __future__ import annotations

"""Renderer-neutral spatial topology for map payloads.

This module is the first boundary after ``map_payload``. It should translate
semantic map entities into neutral spatial candidates without rendering and
without making current districts the permanent map truth.

Current policy:

* current ``district`` payload entities may become temporary ``region`` seeds.
* future attractors / graph communities may also become ``region`` seeds.
* topology keeps source IDs so renderer/grid code does not depend on the
  current district compiler.
"""

from dataclasses import dataclass
import math
from typing import Any


REGION_SOURCE_TYPES = frozenset({"district", "attractor", "region"})


@dataclass(frozen=True)
class TopologyEntity:
    """Spatial candidate extracted from semantic map payload."""

    id: str
    source_entity_id: str
    source_entity_type: str
    spatial_role: str
    label: str
    x: float
    y: float
    weight: float
    radius_hint: float
    similarity_keys: tuple[str, ...]


@dataclass(frozen=True)
class TopologyRelation:
    """Spatial relation between topology entities."""

    id: str
    from_entity_id: str
    to_entity_id: str
    kind: str
    strength: float
    source_id: str | None = None


@dataclass(frozen=True)
class MapTopology:
    """Renderer-neutral spatial graph.

    ``entities`` are still continuous-position candidates. The discrete map is
    compiled later by ``hex_world`` / ``map_grid``.
    """

    width: int
    height: int
    entities: tuple[TopologyEntity, ...]
    relations: tuple[TopologyRelation, ...]

    @property
    def nodes(self) -> tuple[TopologyEntity, ...]:
        """Compatibility alias for the older draft name."""

        return self.entities

    @property
    def edges(self) -> tuple[TopologyRelation, ...]:
        """Compatibility alias for the older draft name."""

        return self.relations


def build_topology(
    payload: dict[str, Any],
    *,
    width: int = 1200,
    height: int = 800,
) -> MapTopology:
    """Build deterministic topology from a map payload.

    The first slice intentionally focuses on region seeds and neighbor
    relations. It avoids layout lock-in and avoids treating ``district`` as the
    final spatial truth.
    """

    source_entities = list(payload.get("entities", []) or [])
    region_sources = [entity for entity in source_entities if _is_region_source(entity)]
    positions = _radial_positions(region_sources, width=width, height=height)

    entities: list[TopologyEntity] = []
    source_to_topology_id: dict[str, str] = {}

    for source in region_sources:
        source_id = str(source.get("id", "")).strip()
        if not source_id:
            continue

        topology_id = f"region:{source_id}"
        source_to_topology_id[source_id] = topology_id

        metrics = source.get("metrics", {}) or {}
        hints = source.get("compiler_hints", {}) or {}
        weight = _safe_float(metrics.get("weight"), default=0.0)
        x, y = positions.get(source_id, (width / 2.0, height / 2.0))

        entities.append(
            TopologyEntity(
                id=topology_id,
                source_entity_id=source_id,
                source_entity_type=str(source.get("type") or "unknown"),
                spatial_role="region",
                label=str(source.get("label") or source_id),
                x=float(x),
                y=float(y),
                weight=weight,
                radius_hint=_radius_hint(weight, metrics),
                similarity_keys=tuple(str(item) for item in hints.get("semantic_similarity_keys", []) or []),
            )
        )

    relations = _neighbor_relations(payload, source_to_topology_id)
    return MapTopology(
        width=width,
        height=height,
        entities=tuple(sorted(entities, key=lambda item: item.id)),
        relations=tuple(relations),
    )


def _is_region_source(entity: dict[str, Any]) -> bool:
    entity_type = str(entity.get("type") or "")
    hints = entity.get("compiler_hints", {}) or {}
    role = str(hints.get("suggested_map_role") or "")
    return entity_type in REGION_SOURCE_TYPES or role in REGION_SOURCE_TYPES


def _radial_positions(
    entities: list[dict[str, Any]],
    *,
    width: int,
    height: int,
) -> dict[str, tuple[float, float]]:
    """Return deterministic continuous seed positions.

    This is intentionally simple. The canonical spatial output is the later
    hex-world artifact, not this temporary continuous placement.
    """

    if not entities:
        return {}

    ordered = sorted(
        entities,
        key=lambda entity: (
            -_safe_float((entity.get("compiler_hints", {}) or {}).get("layout_priority"), default=0.0),
            str(entity.get("id") or ""),
        ),
    )
    center_x = width / 2.0
    center_y = height / 2.0

    if len(ordered) == 1:
        return {str(ordered[0].get("id")): (center_x, center_y)}

    radius = max(120.0, min(width, height) * 0.28)
    result: dict[str, tuple[float, float]] = {}
    for index, entity in enumerate(ordered):
        angle = -math.pi / 2.0 + (2.0 * math.pi * index / len(ordered))
        source_id = str(entity.get("id") or "")
        result[source_id] = (
            center_x + radius * math.cos(angle),
            center_y + radius * math.sin(angle),
        )
    return result


def _neighbor_relations(
    payload: dict[str, Any],
    source_to_topology_id: dict[str, str],
) -> list[TopologyRelation]:
    relations: list[TopologyRelation] = []
    neighbors = sorted(payload.get("neighbors", []) or [], key=lambda item: str(item.get("id") or ""))

    for index, neighbor in enumerate(neighbors):
        source = source_to_topology_id.get(str(neighbor.get("from") or ""))
        target = source_to_topology_id.get(str(neighbor.get("to") or ""))
        if source is None or target is None:
            continue

        relations.append(
            TopologyRelation(
                id=str(neighbor.get("id") or f"region-neighbor-{index + 1}"),
                from_entity_id=source,
                to_entity_id=target,
                kind=str(neighbor.get("type") or "neighbor"),
                strength=_safe_float(neighbor.get("score", neighbor.get("weight")), default=0.0),
                source_id=str(neighbor.get("id") or "") or None,
            )
        )
    return relations


def _radius_hint(weight: float, metrics: dict[str, Any]) -> float:
    count = max(1.0, _safe_float(metrics.get("count"), default=1.0))
    return 64.0 + 64.0 * max(weight, 0.0) + 8.0 * min(count, 8.0)


def _safe_float(value: Any, *, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

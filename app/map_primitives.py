from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


VERSION = "0.1"
PRIMITIVE_KIND_BY_ENTITY_TYPE = {
    "district": "Region",
    "road": "Path",
    "gate": "Boundary",
    "crossroads": "Boundary",
    "landmark": "Anchor",
    "destination": "Anchor",
    "climate": "Field",
    "architecture": "Field",
}


@dataclass(frozen=True)
class MapPrimitive:
    kind: str
    role: str
    label: str
    source_entity_id: str
    source_entity_type: str
    support_count: int
    episode_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MapPrimitivePayload:
    kind: str
    version: str
    source_kind: str
    primitives: tuple[MapPrimitive, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "version": self.version,
            "source_kind": self.source_kind,
            "primitives": tuple(item.to_dict() for item in self.primitives),
        }


def build_map_primitives(map_payload: dict[str, Any]) -> MapPrimitivePayload:
    primitives = []
    for entity in map_payload.get("entities", []):
        entity_type = str(entity.get("type", ""))
        primitive_kind = PRIMITIVE_KIND_BY_ENTITY_TYPE.get(entity_type)
        if primitive_kind is None:
            continue
        provenance = entity.get("provenance") or {}
        episode_ids = tuple(sorted(str(item) for item in provenance.get("episode_ids", ())))
        metrics = entity.get("metrics") or {}
        support_count = int(metrics.get("count") or len(episode_ids))
        primitives.append(
            MapPrimitive(
                kind=primitive_kind,
                role=entity_type,
                label=str(entity.get("label", "")),
                source_entity_id=str(entity.get("id", "")),
                source_entity_type=entity_type,
                support_count=support_count,
                episode_ids=episode_ids,
            )
        )
        primitives.append(
            MapPrimitive(
                kind="Label",
                role=f"{entity_type}_label",
                label=str(entity.get("label", "")),
                source_entity_id=str(entity.get("id", "")),
                source_entity_type=entity_type,
                support_count=support_count,
                episode_ids=episode_ids,
            )
        )
    return MapPrimitivePayload(
        kind="map_primitives",
        version=VERSION,
        source_kind=str(map_payload.get("kind", "map_payload")),
        primitives=tuple(
            sorted(
                primitives,
                key=lambda item: (
                    item.kind,
                    item.role,
                    item.source_entity_id,
                    item.label,
                ),
            )
        ),
    )

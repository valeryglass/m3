from app.map_topology import build_topology


def test_build_topology_maps_districts_to_neutral_regions():
    topology = build_topology(_payload(), width=900, height=600)

    assert topology.width == 900
    assert topology.height == 600
    assert [entity.id for entity in topology.entities] == [
        "region:district-1",
        "region:district-2",
    ]
    assert {entity.source_entity_type for entity in topology.entities} == {"district"}
    assert {entity.spatial_role for entity in topology.entities} == {"region"}


def test_build_topology_ignores_neighbor_links_with_missing_region_ids():
    payload = _payload()
    payload["neighbors"].append(
        {
            "id": "missing-neighbor",
            "type": "district_similarity",
            "from": "district-1",
            "to": "missing-district",
            "score": 1.0,
        }
    )

    topology = build_topology(payload)

    assert [relation.id for relation in topology.relations] == ["neighbor-1"]
    assert topology.relations[0].from_entity_id == "region:district-1"
    assert topology.relations[0].to_entity_id == "region:district-2"


def test_build_topology_is_deterministic():
    first = build_topology(_payload())
    second = build_topology(_payload())

    assert first == second


def _payload():
    return {
        "kind": "map_payload",
        "version": "0.1",
        "source": "telegram-chat:123",
        "entities": [
            _district("district-2", "second", weight=0.5),
            _district("district-1", "first", weight=1.0),
            {"id": "climate-1", "type": "climate", "label": "pressure"},
        ],
        "neighbors": [
            {
                "id": "neighbor-1",
                "type": "district_similarity",
                "from": "district-1",
                "to": "district-2",
                "score": 0.6,
            }
        ],
        "links": [],
    }


def _district(entity_id: str, label: str, *, weight: float):
    return {
        "id": entity_id,
        "type": "district",
        "label": label,
        "metrics": {"count": 2, "weight": weight},
        "compiler_hints": {
            "layout_priority": weight,
            "semantic_similarity_keys": [label],
            "suggested_map_role": "district",
        },
    }

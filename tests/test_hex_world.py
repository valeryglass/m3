from app.hex_world import build_hex_world, hex_world_to_dict


def test_build_hex_world_compiles_regions_paths_and_climate_field():
    world = build_hex_world(_payload(), width=900, height=600, cell_size=32)

    assert world.kind == "hex_world"
    assert world.coordinate_system == "axial"
    assert world.regions
    assert [region.source_entity_type for region in world.regions] == ["district", "district"]
    assert world.paths
    assert all(path.cell_ids for path in world.paths)
    assert world.fields
    assert world.fields[0].layer == "climate"
    assert all(cell.weight == 0.75 for cell in world.fields[0].cells)


def test_hex_world_serializes_without_district_as_renderer_truth():
    world_dict = hex_world_to_dict(build_hex_world(_payload(), width=900, height=600, cell_size=32))

    assert world_dict["kind"] == "hex_world"
    assert world_dict["regions"][0]["id"].startswith("region:")
    assert world_dict["regions"][0]["source_entity_type"] == "district"
    assert world_dict["provenance"]["layout_policy"] == "generative_no_position_lock"


def _payload():
    return {
        "kind": "map_payload",
        "version": "0.1",
        "source": "telegram-chat:123",
        "entities": [
            _district("district-1", "first", weight=1.0),
            _district("district-2", "second", weight=0.8),
            {"id": "climate-1", "type": "climate", "label": "pressure"},
            {"id": "landmark-1", "type": "landmark", "label": "small proof"},
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
        "links": [
            {
                "id": "climate-link-1",
                "type": "climate_to_district",
                "from": "climate-1",
                "to": "district-1",
                "weight": 0.75,
                "provenance": {"episode_ids": ["episode-1"]},
            },
            {
                "id": "landmark-link-1",
                "type": "landmark_to_district",
                "from": "landmark-1",
                "to": "district-1",
                "weight": 1.0,
                "provenance": {"episode_ids": ["episode-1"]},
            },
        ],
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

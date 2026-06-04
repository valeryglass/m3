import json
import math

from app.map_payload_html import (
    _district_positions,
    _ellipse_positions,
    render_html,
    write_html,
)


def test_render_html_includes_document_svg_and_payload_labels():
    html = render_html(_payload())

    assert html.startswith("<!doctype html>")
    assert "<svg" in html
    assert "Map Payload" in html
    assert "telegram-chat:123" in html
    assert "social + страх + avoid" in html
    assert "district" in html


def test_render_html_uses_map_specific_visual_classes():
    html = render_html(_payload())

    for class_name in (
        "district-area",
        "gate-marker",
        "road-path",
        "destination-marker",
        "cluster-halo",
        "neighbor-link",
        "crossroads-marker",
        "climate-band",
        "architecture-block",
        "landmark-marker",
    ):
        assert class_name in html


def test_render_html_escapes_labels():
    payload = _payload()
    payload["entities"][0]["label"] = "<script>alert(1)</script>"
    payload["clusters"][0]["label"] = "<b>cluster</b>"

    html = render_html(payload)

    assert "<script>" not in html
    assert "<b>cluster</b>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;b&gt;cluster&lt;/b&gt;" in html


def test_write_html_writes_requested_output(tmp_path):
    source = tmp_path / "map.json"
    output = tmp_path / "map.html"
    source.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")

    path = write_html(source, output)

    assert path == output
    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_district_positions_empty_returns_empty():
    assert _district_positions([], [], 100, 200, 50, 40) == {}


def test_district_positions_single_district_uses_center():
    positions = _district_positions(
        [_entity("district-1", "district", "one", 1)],
        [],
        100,
        200,
        50,
        40,
    )

    assert positions == {"district-1": (100, 200)}


def test_district_positions_without_neighbors_falls_back_to_ellipse():
    districts = [
        _entity("district-1", "district", "one", 1),
        _entity("district-2", "district", "two", 1),
    ]

    assert _district_positions(districts, [], 100, 200, 50, 40) == _ellipse_positions(
        districts,
        100,
        200,
        50,
        40,
    )


def test_district_positions_connected_districts_are_closer_than_unconnected():
    districts = [
        _entity("district-1", "district", "one", 1),
        _entity("district-2", "district", "two", 1),
        _entity("district-3", "district", "three", 1),
    ]
    neighbors = [
        {
            "id": "district_similarity-1",
            "type": "district_similarity",
            "from": "district-1",
            "to": "district-2",
            "score": 1.0,
            "shared_keys": [],
            "differing_keys": [],
            "provenance": {"episode_ids": [], "shared_episode_ids": []},
        }
    ]

    positions = _district_positions(districts, neighbors, 680, 440, 370, 235)

    assert _distance(positions["district-1"], positions["district-2"]) < _distance(
        positions["district-1"],
        positions["district-3"],
    )


def test_district_positions_are_deterministic():
    districts = [
        _entity("district-1", "district", "one", 1),
        _entity("district-2", "district", "two", 1),
        _entity("district-3", "district", "three", 1),
    ]
    neighbors = [
        {
            "id": "district_similarity-1",
            "type": "district_similarity",
            "from": "district-1",
            "to": "district-2",
            "score": 0.6,
            "shared_keys": [],
            "differing_keys": [],
            "provenance": {"episode_ids": [], "shared_episode_ids": []},
        }
    ]

    assert _district_positions(districts, neighbors, 100, 100, 70, 60) == _district_positions(
        districts,
        neighbors,
        100,
        100,
        70,
        60,
    )


def _payload():
    return {
        "kind": "map_payload",
        "version": "0.1",
        "source": "telegram-chat:123",
        "episodes": 2,
        "timespan_quant": "1week",
        "similarity": {"version": "symbolic_v1"},
        "entities": [
            _entity("district-1", "district", "social + страх + avoid", 2),
            _entity("district-2", "district", "social + страх + approach", 2),
            _entity("gate-1", "gate", "social", 2),
            _entity("climate-1", "climate", "страх", 2),
            _entity("architecture-1", "architecture", "prediction", 2),
            _entity("road-1", "road", "avoid", 2),
            _entity("destination-1", "destination", "short_term: relief", 2),
            _entity("crossroads-1", "crossroads", "social -> страх", 2),
            _entity("landmark-1", "landmark", "social -> страх -> avoid", 1),
        ],
        "links": [
            {
                "id": "gate_to_district-1",
                "type": "gate_to_district",
                "from": "gate-1",
                "to": "district-1",
                "weight": 1.0,
                "provenance": {"episode_ids": ["episode-20260430-1"]},
            }
        ],
        "clusters": [
            {
                "id": "district-cluster-1",
                "type": "district_similarity_cluster",
                "label": "Social-Страх Cluster",
                "member_entity_ids": ["district-1", "district-2"],
                "centroid_signature": {
                    "trigger": "social",
                    "emotion": "страх",
                    "behavior": "approach",
                },
                "metrics": {
                    "member_count": 2,
                    "episode_count": 2,
                    "weight": 1.0,
                    "recurrence_weeks": 1,
                    "first_week": "2026-W18",
                    "last_week": "2026-W18",
                    "cohesion": 0.6,
                    "density": 1.0,
                },
                "compiler_hints": {
                    "layout_priority": 1.0,
                    "centrality": 1.0,
                    "density": 1.0,
                    "suggested_map_role": "district_cluster",
                    "semantic_similarity_keys": [
                        "trigger:social",
                        "emotion:страх",
                        "behavior:approach",
                    ],
                },
                "provenance": {"episode_ids": ["episode-20260430-1"]},
            }
        ],
        "neighbors": [
            {
                "id": "district_similarity-1",
                "type": "district_similarity",
                "from": "district-1",
                "to": "district-2",
                "score": 0.6,
                "shared_keys": ["emotion:страх", "trigger:social"],
                "differing_keys": ["behavior:approach", "behavior:avoid"],
                "provenance": {
                    "episode_ids": ["episode-20260430-1"],
                    "shared_episode_ids": [],
                },
            }
        ],
        "provenance": {
            "generated_from": "graph_signatures",
            "graph_ready_episode_ids": [],
            "skipped_episode_ids": [],
        },
    }


def _entity(entity_id, entity_type, label, count):
    return {
        "id": entity_id,
        "type": entity_type,
        "label": label,
        "parent_id": None,
        "signature": {},
        "metrics": {
            "count": count,
            "weight": 1.0,
            "recurrence_weeks": 1,
            "first_week": "2026-W18",
            "last_week": "2026-W18",
            "novelty_flag": False,
            "stability_flag": False,
            "rarity_flag": False,
            "surprise_flag": False,
        },
        "compiler_hints": {
            "layout_priority": 1.0,
            "semantic_similarity_keys": [],
            "centrality": 1.0,
            "density": 1.0,
            "suggested_map_role": entity_type,
        },
        "cluster_membership": {"cluster_id": "district-cluster-1" if entity_type == "district" else None},
        "provenance": {"episode_ids": ["episode-20260430-1"]},
    }


def _distance(left, right):
    return math.hypot(left[0] - right[0], left[1] - right[1])

import json
import math
import re

import pytest

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


def test_render_html_includes_checkbox_controls_for_all_layers():
    html = render_html(_payload())

    for layer in (
        "climate",
        "clusters",
        "neighbors",
        "roads",
        "destinations",
        "gates",
        "districts",
        "architecture",
        "crossroads",
        "landmarks",
    ):
        assert f'value="{layer}" checked' in html
        assert f'data-layer="{layer}" data-hidden="false"' in html

    assert "data-layer-toggle" in html
    assert "layer.dataset.hidden" in html


def test_render_html_spatializes_architecture_destinations_and_climate():
    html = render_html(_payload())

    assert 'x="44" y="128">gates' not in html
    assert 'x="1180" y="128">architecture' not in html
    assert 'x="1160" y="548">destinations' not in html
    assert "architecture-segment" in html
    assert "architecture-wedge" in html
    assert '<rect class="architecture-block' not in html
    assert "destination-poi" in html
    assert '<polygon class="destination-marker' in html
    assert "climate-field" in html
    assert "rgba(37, 99, 235" in html
    assert html.index('<ellipse class="climate-band') < html.index(
        '<circle class="district-area"'
    )


def test_gates_render_on_border_with_entry_paths():
    html = render_html(_payload())

    assert "gate-entry-path" in html
    assert "gate-marker" in html
    assert 'cx="95"' not in html


def test_destinations_use_horizon_triangle_styles():
    payload = _payload()
    payload["entities"].append(
        _entity("destination-2", "destination", "long_term: learning", 1)
    )
    payload["entities"][-1]["signature"] = {"horizon": "long_term", "outcome": "learning"}
    payload["links"].append(
        {
            "id": "road_to_destination-2",
            "type": "road_to_destination",
            "from": "road-1",
            "to": "destination-2",
            "weight": 1.0,
            "provenance": {"episode_ids": ["episode-20260430-2"]},
        }
    )

    html = render_html(payload)

    assert 'data-horizon="short_term"' in html
    assert "destination-short-term" in html
    assert 'data-horizon="long_term"' in html
    assert "destination-long-term" in html


def test_destination_identity_coordinates_are_stable():
    first = _destination_centers(render_html(_payload()))
    second = _destination_centers(render_html(_payload()))

    assert first == second


def test_different_destination_identities_get_different_positions():
    payload = _payload()
    payload["entities"].append(
        _destination("destination-2", "short_term", "learning", 1)
    )
    payload["links"].append(
        {
            "id": "road_to_destination-2",
            "type": "road_to_destination",
            "from": "road-1",
            "to": "destination-2",
            "weight": 1.0,
            "provenance": {"episode_ids": ["episode-20260430-2"]},
        }
    )

    centers = _destination_centers(render_html(payload))

    assert len(set(centers)) == 2


def test_short_term_destinations_stay_closer_than_long_term():
    payload = _payload()
    payload["entities"] = [
        _entity("district-1", "district", "source district", 3),
        _entity("road-1", "road", "avoid", 2),
        _destination("destination-short", "short_term", "relief", 1),
        _destination("destination-long", "long_term", "relief", 1),
    ]
    payload["links"] = [
        _district_to_road("district_to_road-1", "district-1", 3),
        {
            "id": "road_to_destination-1",
            "type": "road_to_destination",
            "from": "road-1",
            "to": "destination-short",
            "weight": 1.0,
            "provenance": {"episode_ids": ["episode-20260430-1"]},
        },
        {
            "id": "road_to_destination-2",
            "type": "road_to_destination",
            "from": "road-1",
            "to": "destination-long",
            "weight": 1.0,
            "provenance": {"episode_ids": ["episode-20260430-2"]},
        },
    ]

    html = render_html(payload)
    district = next(iter(_district_circles_by_label(html).values()))
    centers = _destination_centers(html)

    distances = sorted(
        math.hypot(center[0] - district[0], center[1] - district[1])
        for center in centers
    )
    assert distances[0] < distances[1]


def test_destination_pois_remain_within_svg_bounds():
    centers = _destination_centers(render_html(_payload()))

    for x, y in centers:
        assert 0 <= x <= 1480
        assert 0 <= y <= 900


def test_road_paths_start_from_district_boundary_not_center():
    html = render_html(_payload())
    districts = _district_circles_by_label(html)
    district_x, district_y, radius = districts["social + страх + avoid"]
    start_x, start_y = map(
        float,
        _first_match(
        r'<path class="road-path" d="M ([0-9.]+) ([0-9.]+) Q ',
        html,
        ),
    )

    assert math.hypot(start_x - district_x, start_y - district_y) == pytest.approx(
        radius,
        abs=0.2,
    )
    assert (start_x, start_y) != (district_x, district_y)


def test_multi_source_roads_are_capped_and_ordered_by_support():
    payload = _payload()
    payload["entities"].extend(
        [
            _entity("district-3", "district", "third", 3),
            _entity("district-4", "district", "fourth", 4),
            _entity("district-5", "district", "fifth", 5),
        ]
    )
    payload["links"].extend(
        [
            _district_to_road("district_to_road-2", "district-2", 4),
            _district_to_road("district_to_road-3", "district-3", 5),
            _district_to_road("district_to_road-4", "district-4", 3),
            _district_to_road("district_to_road-5", "district-5", 2),
        ]
    )

    html = render_html(payload)
    path_starts = re.findall(r'<path class="road-path" d="M ([0-9.]+) ([0-9.]+) Q ', html)
    district_starts = _district_boundary_starts_by_label(html)

    assert len(path_starts) == 3
    assert path_starts == [
        district_starts["third"],
        district_starts["social + страх + approa..."],
        district_starts["fourth"],
    ]


def test_architecture_proportions_use_link_episode_provenance():
    payload = _payload()
    payload["links"] = [
        link for link in payload["links"] if link["type"] != "architecture_to_district"
    ]
    payload["entities"].append(_entity("architecture-2", "architecture", "meaning", 4))
    payload["links"].extend(
        [
            {
                "id": "architecture_to_district-1",
                "type": "architecture_to_district",
                "from": "architecture-1",
                "to": "district-1",
                "weight": 0.1,
                "provenance": {
                    "episode_ids": [
                        "episode-20260430-1",
                        "episode-20260430-2",
                        "episode-20260430-3",
                    ]
                },
            },
            {
                "id": "architecture_to_district-2",
                "type": "architecture_to_district",
                "from": "architecture-2",
                "to": "district-1",
                "weight": 0.9,
                "provenance": {"episode_ids": ["episode-20260430-4"]},
            },
        ]
    )

    html = render_html(payload)

    assert 'data-proportion="0.75"' in html
    assert 'data-proportion="0.25"' in html
    wedge_fills = re.findall(r'class="architecture-block[^"]*"[^>]*fill="([^"]+)"', html)
    assert len(set(wedge_fills)) >= 2


def test_architecture_proportions_fall_back_to_weight_without_provenance():
    payload = _payload()
    payload["links"] = [
        link for link in payload["links"] if link["type"] != "architecture_to_district"
    ]
    payload["entities"].append(_entity("architecture-2", "architecture", "meaning", 4))
    payload["links"].extend(
        [
            {
                "id": "architecture_to_district-1",
                "type": "architecture_to_district",
                "from": "architecture-1",
                "to": "district-1",
                "weight": 2.0,
            },
            {
                "id": "architecture_to_district-2",
                "type": "architecture_to_district",
                "from": "architecture-2",
                "to": "district-1",
                "weight": 1.0,
            },
        ]
    )

    html = render_html(payload)

    assert 'data-proportion="0.67"' in html
    assert 'data-proportion="0.33"' in html


def test_render_html_escapes_labels():
    payload = _payload()
    payload["entities"][0]["label"] = "<script>alert(1)</script>"
    payload["clusters"][0]["label"] = "<b>cluster</b>"

    html = render_html(payload)

    assert "<script>alert" not in html
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
            },
            {
                "id": "climate_to_district-1",
                "type": "climate_to_district",
                "from": "climate-1",
                "to": "district-1",
                "weight": 1.0,
                "provenance": {"episode_ids": ["episode-20260430-1"]},
            },
            {
                "id": "architecture_to_district-1",
                "type": "architecture_to_district",
                "from": "architecture-1",
                "to": "district-1",
                "weight": 1.0,
                "provenance": {"episode_ids": ["episode-20260430-1"]},
            },
            {
                "id": "district_to_road-1",
                "type": "district_to_road",
                "from": "district-1",
                "to": "road-1",
                "weight": 1.0,
                "provenance": {"episode_ids": ["episode-20260430-1"]},
            },
            {
                "id": "road_to_destination-1",
                "type": "road_to_destination",
                "from": "road-1",
                "to": "destination-1",
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


def _district_to_road(link_id, district_id, support):
    return {
        "id": link_id,
        "type": "district_to_road",
        "from": district_id,
        "to": "road-1",
        "weight": 1.0,
        "provenance": {
            "episode_ids": [
                f"episode-20260430-{index}"
                for index in range(1, support + 1)
            ]
        },
    }


def _destination(entity_id, horizon, outcome, count):
    entity = _entity(entity_id, "destination", f"{horizon}: {outcome}", count)
    entity["signature"] = {"horizon": horizon, "outcome": outcome}
    return entity


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


def _first_match(pattern, text):
    match = re.search(pattern, text)
    assert match is not None
    return match.groups()


def _destination_centers(html):
    centers = []
    for points in re.findall(
        r'<polygon class="destination-marker[^"]*" points="([^"]+)"',
        html,
    ):
        pairs = [
            tuple(map(float, point.split(",")))
            for point in points.split()
        ]
        centers.append(
            (
                round(sum(point[0] for point in pairs) / len(pairs), 1),
                round(sum(point[1] for point in pairs) / len(pairs), 1),
            )
        )
    return centers


def _district_circles_by_label(html):
    return {
        match.group(4): (
            float(match.group(1)),
            float(match.group(2)),
            float(match.group(3)),
        )
        for match in re.finditer(
            r'<circle class="district-area" cx="([0-9.]+)" cy="([0-9.]+)" r="([0-9.]+)" />'
            r'.*?<text class="node-label" x="[^"]+" y="[^"]+">([^<]+)</text>',
            html,
        )
    }


def _district_boundary_starts_by_label(html):
    circles = _district_circles_by_label(html)
    starts_by_label = {}
    path_starts = re.findall(r'<path class="road-path" d="M ([0-9.]+) ([0-9.]+) Q ', html)
    for label, circle in circles.items():
        for start in path_starts:
            distance = math.hypot(float(start[0]) - circle[0], float(start[1]) - circle[1])
            if distance == pytest.approx(circle[2], abs=0.2):
                starts_by_label[label] = start
    return starts_by_label

import json

import pytest

from app.graph_report import load_episodes
from app.map_payload import build_map_payload, main, write_map_payload
from app.schemas.episode import Episode


def test_map_payload_builds_compiler_json_for_one_source():
    episodes = [
        _load(_episode("episode-20260430-1", source="telegram-chat:123")),
        _load(_episode("episode-20260430-2", source="telegram-chat:123")),
        _load(_episode("episode-20260430-3", source="telegram-chat:456")),
        _load(_episode("episode-20260430-4", source="telegram-chat:123", graph_ready=False)),
    ]

    payload = build_map_payload(episodes, source="telegram-chat:123")

    assert payload["kind"] == "map_payload"
    assert payload["version"] == "0.1"
    assert payload["source"] == "telegram-chat:123"
    assert payload["episodes"] == 3
    assert payload["timespan_quant"] == "1week"
    assert payload["similarity"] == {"version": "symbolic_v1"}
    assert payload["analytics"]["source"] == "insight_payload"
    assert payload["analytics"]["insight_payload"]["kind"] == "insight_payload"
    assert payload["analytics"]["spatial_payload"]["kind"] == "spatial_payload"
    assert "clusters" in payload
    assert "neighbors" in payload
    assert payload["provenance"] == {
        "generated_from": "graph_signatures",
        "graph_ready_episode_ids": [
            "episode-20260430-1",
            "episode-20260430-2",
        ],
        "skipped_episode_ids": ["episode-20260430-4"],
        "coverage": {
            "observed_count": 3,
            "annotation_row_count": 0,
            "annotated_count": 3,
            "pending_count": 0,
            "pending_episode_ids": [],
            "state": "full",
        },
    }


def test_map_payload_entities_are_complete_and_deterministic():
    episodes = [
        _load(_episode("episode-20260430-1")),
        _load(_episode("episode-20260430-2")),
        _load(_episode("episode-20260508-1", behavior_type="approach")),
    ]

    payload = build_map_payload(episodes, source="telegram-chat:123")
    entities = payload["entities"]
    district = _entity(entities, "district", "social + страх + avoid")

    assert district == {
        "id": "district-1",
        "type": "district",
        "label": "social + страх + avoid",
        "parent_id": None,
        "signature": {"trigger": "social", "emotion": "страх", "behavior": "avoid"},
        "metrics": {
            "count": 2,
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
            "semantic_similarity_keys": ["social", "страх", "avoid"],
            "centrality": 1.0,
            "density": 0.375,
            "suggested_map_role": "district",
        },
        "cluster_membership": {"cluster_id": None},
        "provenance": {"episode_ids": ["episode-20260430-1", "episode-20260430-2"]},
    }
    for entity_type in (
        "gate",
        "climate",
        "architecture",
        "road",
        "crossroads",
        "landmark",
        "destination",
    ):
        assert any(item["type"] == entity_type for item in entities)


def test_map_payload_required_fields_exist_when_source_data_is_sparse():
    payload = build_map_payload(
        [_load(_episode("episode-20260430-1", graph_ready=False))],
        source="telegram-chat:123",
    )

    assert payload["entities"] == []
    assert payload["links"] == []
    assert payload["clusters"] == []
    assert payload["neighbors"] == []
    assert payload["provenance"]["graph_ready_episode_ids"] == []
    assert payload["provenance"]["skipped_episode_ids"] == ["episode-20260430-1"]
    assert payload["provenance"]["coverage"]["pending_count"] == 0


def test_map_payload_links_reference_valid_entities_and_have_normalized_weights():
    payload = build_map_payload(
        [
            _load(_episode("episode-20260430-1")),
            _load(_episode("episode-20260430-2")),
            _load(_episode("episode-20260508-1", behavior_type="approach")),
        ],
        source="telegram-chat:123",
    )
    entity_ids = {entity["id"] for entity in payload["entities"]}

    assert payload["links"]
    for link in payload["links"]:
        assert {
            "id",
            "type",
            "from",
            "to",
            "weight",
            "provenance",
        } == set(link)
        assert link["from"] in entity_ids
        assert link["to"] in entity_ids
        assert 0.0 <= link["weight"] <= 1.0
        assert link["provenance"]["episode_ids"]


def test_map_payload_clusters_and_neighbors_are_deterministic():
    payload = build_map_payload(
        [
            _load(_episode("episode-20260430-1")),
            _load(_episode("episode-20260430-2")),
            _load(_episode("episode-20260508-1", behavior_type="approach")),
            _load(_episode("episode-20260508-2", behavior_type="approach")),
        ],
        source="telegram-chat:123",
    )
    entity_ids = {entity["id"] for entity in payload["entities"]}
    district_ids = {entity["id"] for entity in payload["entities"] if entity["type"] == "district"}

    assert payload["neighbors"] == [
        {
            "id": "district_similarity-1",
            "type": "district_similarity",
            "from": "district-1",
            "to": "district-2",
            "score": 0.6,
            "shared_keys": ["emotion:страх", "trigger:social"],
            "differing_keys": ["behavior:approach", "behavior:avoid"],
            "provenance": {
                "episode_ids": [
                    "episode-20260430-1",
                    "episode-20260430-2",
                    "episode-20260508-1",
                    "episode-20260508-2",
                ],
                "shared_episode_ids": [],
            },
        }
    ]
    assert payload["clusters"][0]["id"] == "district-cluster-1"
    assert payload["clusters"][0]["label"] == "Social-Страх Cluster"
    assert payload["clusters"][0]["member_entity_ids"] == ["district-1", "district-2"]
    assert payload["clusters"][0]["centroid_signature"] == {
        "trigger": "social",
        "emotion": "страх",
        "behavior": "approach",
    }
    assert payload["clusters"][0]["metrics"] == {
        "member_count": 2,
        "episode_count": 4,
        "weight": 1.0,
        "recurrence_weeks": 2,
        "first_week": "2026-W18",
        "last_week": "2026-W19",
        "cohesion": 0.6,
        "density": 1.0,
    }
    assert payload["clusters"][0]["compiler_hints"] == {
        "layout_priority": 1.0,
        "centrality": 1.0,
        "density": 1.0,
        "suggested_map_role": "district_cluster",
        "semantic_similarity_keys": [
            "trigger:social",
            "emotion:страх",
            "behavior:approach",
        ],
    }
    assert set(payload["clusters"][0]["member_entity_ids"]).issubset(district_ids)
    assert payload["neighbors"][0]["from"] in entity_ids
    assert payload["neighbors"][0]["to"] in entity_ids
    for district in (entity for entity in payload["entities"] if entity["type"] == "district"):
        assert district["cluster_membership"] == {"cluster_id": "district-cluster-1"}


def test_map_payload_entities_always_include_cluster_membership():
    payload = build_map_payload(
        [
            _load(_episode("episode-20260430-1")),
            _load(_episode("episode-20260430-2")),
        ],
        source="telegram-chat:123",
    )

    assert payload["entities"]
    assert all("cluster_membership" in entity for entity in payload["entities"])
    assert all("cluster_id" in entity["cluster_membership"] for entity in payload["entities"])


def test_map_payload_weights_are_normalized_within_entity_type():
    payload = build_map_payload(
        [
            _load(_episode("episode-20260430-1")),
            _load(_episode("episode-20260430-2")),
            _load(_episode("episode-20260508-1", behavior_type="approach")),
        ],
        source="telegram-chat:123",
    )

    roads = [entity for entity in payload["entities"] if entity["type"] == "road"]

    assert _entity(roads, "road", "avoid")["metrics"]["weight"] == 1.0
    assert _entity(roads, "road", "approach")["metrics"]["weight"] == 0.5


def test_map_payload_exposes_same_insight_payload_for_downstream_consumers():
    payload = build_map_payload(
        [
            _load(_episode("episode-20260430-1")),
            _load(_episode("episode-20260430-2")),
            _load(_episode("episode-20260508-1", behavior_type="approach")),
        ],
        source="telegram-chat:123",
    )

    insight = payload["analytics"]["insight_payload"]
    spatial = payload["analytics"]["spatial_payload"]

    assert insight["dominant_motif"] == {
        "trigger": "social",
        "emotion": "страх",
        "behavior": "avoid",
        "support_count": 2,
        "episode_ids": ("episode-20260430-1", "episode-20260430-2"),
    }
    assert spatial["paths"][0]["signature"] == {
        "trigger": "social",
        "emotion": "страх",
        "behavior": "avoid",
    }


def test_map_payload_writes_requested_path(tmp_path):
    episodes = [_load(_episode("episode-20260430-1"))]
    output = tmp_path / "map-payload" / "telegram-chat-123.json"

    path = write_map_payload(episodes, output, source="telegram-chat:123")

    data = json.loads(path.read_text(encoding="utf-8"))
    assert path == output
    assert data["source"] == "telegram-chat:123"


def test_map_payload_cli_writes_output(tmp_path, monkeypatch, capsys):
    episode_dir = tmp_path / "episodes"
    episode_dir.mkdir()
    (episode_dir / "episode-20260430-1.json").write_text(
        json.dumps(_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )
    output = tmp_path / "map.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "map_payload",
            "--episode-dir",
            str(episode_dir),
            "--source",
            "telegram-chat:123",
            "--output",
            str(output),
        ],
    )

    main()

    assert capsys.readouterr().out.strip() == str(output)
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "map_payload"
    assert data["provenance"]["episode_dir"] == episode_dir.as_posix()
    assert data["provenance"]["source_scope"] == "telegram-chat:123"
    assert "generated_at" in data["provenance"]


def test_map_payload_cli_default_output_uses_exports_dir(tmp_path, monkeypatch, capsys):
    episode_dir = tmp_path / "episodes"
    episode_dir.mkdir()
    (episode_dir / "episode-20260430-1.json").write_text(
        json.dumps(_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "map_payload",
            "--episode-dir",
            str(episode_dir),
            "--source",
            "telegram-chat:123",
        ],
    )

    main()

    output = tmp_path / "data" / "exports" / "map-payload" / "telegram-chat-123.json"
    assert capsys.readouterr().out.strip() == output.relative_to(tmp_path).as_posix()
    assert json.loads(output.read_text(encoding="utf-8"))["kind"] == "map_payload"


def test_map_payload_cli_includes_annotation_run_provenance(
    tmp_path,
    monkeypatch,
    capsys,
):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    run_dir.mkdir(parents=True)
    (episode_dir / "episode-20260430-1.json").write_text(
        json.dumps(_observed_only_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )
    _write_annotation_run(
        run_dir,
        {
            "episode_id": "episode-20260430-1",
            "derived": _episode("episode-20260430-1")["derived"],
        },
    )
    output = tmp_path / "map.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "map_payload",
            "--episode-dir",
            str(episode_dir),
            "--annotation-run-dir",
            str(run_dir),
            "--source",
            "telegram-chat:123",
            "--output",
            str(output),
        ],
    )

    main()

    assert capsys.readouterr().out.strip() == str(output)
    provenance = json.loads(output.read_text(encoding="utf-8"))["provenance"]
    assert provenance["annotation_run_id"] == "run-test"
    assert provenance["annotation_run_path"] == run_dir.as_posix()
    assert provenance["episode_dir"] == episode_dir.as_posix()


def test_map_payload_loads_episode_files(tmp_path):
    (tmp_path / "episode-20260430-1.json").write_text(
        json.dumps(_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )

    payload = build_map_payload(load_episodes(tmp_path), source="telegram-chat:123")

    assert payload["episodes"] == 1


def test_map_payload_builds_from_annotation_run_format(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    run_dir.mkdir(parents=True)
    (episode_dir / "episode-20260430-1.json").write_text(
        json.dumps(_observed_only_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "annotation_run_id": "run-test",
                "schema_version": "episode.v1",
                "taxonomy_version": "taxonomy.v1",
                "prompt_version": "prompt.v1",
                "created_at": "2026-05-01T00:00:00Z",
                "source_episode_count": 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "annotations.jsonl").write_text(
        json.dumps(
            {
                "episode_id": "episode-20260430-1",
                "derived": _episode("episode-20260430-1")["derived"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_map_payload(
        load_episodes(episode_dir, annotation_run_dir=run_dir),
        source="telegram-chat:123",
    )

    assert payload["episodes"] == 1
    assert payload["provenance"]["graph_ready_episode_ids"] == ["episode-20260430-1"]


def test_map_payload_builds_with_partial_annotation_coverage(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    (episode_dir / "episode-20260430-1.json").write_text(
        json.dumps(_observed_only_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )
    (episode_dir / "episode-20260430-2.json").write_text(
        json.dumps(_observed_only_episode("episode-20260430-2"), ensure_ascii=False),
        encoding="utf-8",
    )
    _write_annotation_run(
        run_dir,
        {
            "episode_id": "episode-20260430-1",
            "derived": _episode("episode-20260430-1")["derived"],
        },
    )

    from app.analytics_loader import annotation_coverage_for_episode_ids

    episodes = load_episodes(episode_dir, annotation_run_dir=run_dir)
    payload = build_map_payload(
        episodes,
        source="telegram-chat:123",
        coverage=annotation_coverage_for_episode_ids(
            {episode.id for episode in episodes},
            annotation_run_dir=run_dir,
        ),
    )

    assert payload["provenance"]["coverage"] == {
        "observed_count": 2,
        "annotation_row_count": 1,
        "annotated_count": 1,
        "pending_count": 1,
        "pending_episode_ids": ["episode-20260430-2"],
        "state": "partial",
    }


def test_map_payload_cli_require_full_coverage_fails_on_partial_run(
    tmp_path,
    monkeypatch,
):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    (episode_dir / "episode-20260430-1.json").write_text(
        json.dumps(_observed_only_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )
    _write_annotation_run(
        run_dir,
        {
            "episode_id": "episode-20260430-1",
            "derived": _episode("episode-20260430-1")["derived"],
        },
    )
    (run_dir / "annotations.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "map_payload",
            "--episode-dir",
            str(episode_dir),
            "--annotation-run-dir",
            str(run_dir),
            "--source",
            "telegram-chat:123",
            "--output",
            str(tmp_path / "map.json"),
            "--require-full-coverage",
        ],
    )

    with pytest.raises(ValueError, match="coverage is partial"):
        main()


def test_map_payload_builds_from_latest_annotation_run_by_default(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    run_dir = run_root / "run-20260605"
    episode_dir.mkdir()
    run_dir.mkdir(parents=True)
    (episode_dir / "episode-20260430-1.json").write_text(
        json.dumps(_observed_only_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )
    _write_annotation_run(
        run_dir,
        {
            "episode_id": "episode-20260430-1",
            "derived": _episode("episode-20260430-1")["derived"],
        },
    )

    payload = build_map_payload(
        load_episodes(episode_dir, annotation_run_root=run_root),
        source="telegram-chat:123",
    )

    assert payload["provenance"]["graph_ready_episode_ids"] == ["episode-20260430-1"]


def _entity(entities, entity_type, label):
    return next(
        entity
        for entity in entities
        if entity["type"] == entity_type and entity["label"] == label
    )


def _load(data):
    return Episode.model_validate(data)


def _observed_only_episode(episode_id):
    data = _episode(episode_id)
    data["episode_id"] = data.pop("id")
    data["metadata"] = {"capture_version": "test"}
    data.pop("derived")
    return data


def _write_annotation_run(run_dir, row):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "annotation_run_id": run_dir.name,
                "schema_version": "episode.v1",
                "taxonomy_version": "taxonomy.v1",
                "prompt_version": "prompt.v1",
                "created_at": "2026-05-01T00:00:00Z",
                "source_episode_count": 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "annotations.jsonl").write_text(
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _episode(
    episode_id,
    *,
    source="telegram-chat:123",
    emotion="страх",
    behavior_type="avoid",
    graph_ready=True,
):
    derived = {
        "nodes": [],
        "trigger_annotations": [],
        "actor_annotations": [],
        "cognition_annotations": [],
        "emotion_annotations": [],
        "behavior_annotations": [],
        "outcome_annotations": [],
        "relations": [],
    }
    if graph_ready:
        derived = {
            "nodes": [
                {
                    "id": "node-1",
                    "node_origin": "observed",
                    "kind": "cognition",
                    "text": "They will judge me.",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "they will judge me",
                    "confidence": 0.9,
                },
                {
                    "id": "node-2",
                    "node_origin": "observed",
                    "kind": "short_outcome",
                    "text": "Relief.",
                    "source_field": "observed.short_term_consequence",
                    "source_quote": "Relief.",
                    "confidence": 0.85,
                },
                {
                    "id": "node-3",
                    "node_origin": "observed",
                    "kind": "long_outcome",
                    "text": "Still unresolved.",
                    "source_field": "observed.long_term_consequence",
                    "source_quote": "Still unresolved.",
                    "confidence": 0.85,
                },
            ],
            "trigger_annotations": [
                {
                    "id": "trigger-annotation-1",
                    "type": "social",
                    "source_field": "observed.situation",
                    "source_quote": "group chat",
                    "confidence": 0.8,
                }
            ],
            "actor_annotations": [],
            "cognition_annotations": [
                {
                    "id": "cognition-annotation-1",
                    "node_id": "node-1",
                    "text": "They will judge me.",
                    "kind": "prediction",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "they will judge me",
                    "confidence": 0.85,
                }
            ],
            "emotion_annotations": [
                {
                    "id": "emotion-annotation-1",
                    "label": emotion,
                    "intensity": 0.66,
                    "valence": -0.8,
                    "arousal": 0.8,
                    "source_field": "observed.emotion",
                    "source_quote": emotion,
                    "confidence": 0.9,
                }
            ],
            "behavior_annotations": [
                {
                    "id": "behavior-annotation-1",
                    "type": behavior_type,
                    "source_field": "observed.behavior",
                    "source_quote": "closed the chat",
                    "confidence": 0.9,
                }
            ],
            "outcome_annotations": [
                {
                    "id": "outcome-annotation-1",
                    "node_id": "node-2",
                    "horizon": "short_term",
                    "type": "relief",
                    "source_field": "observed.short_term_consequence",
                    "source_quote": "Relief.",
                    "confidence": 0.85,
                },
                {
                    "id": "outcome-annotation-2",
                    "node_id": "node-3",
                    "horizon": "long_term",
                    "type": "unresolved",
                    "source_field": "observed.long_term_consequence",
                    "source_quote": "Still unresolved.",
                    "confidence": 0.85,
                },
            ],
            "relations": [
                {
                    "id": "relation-1",
                    "type": "belongs_to",
                    "from_ref": "node-1",
                    "to_ref": "episode",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "they will judge me",
                    "confidence": 1.0,
                }
            ],
        }
    return {
        "id": episode_id,
        "date": f"{episode_id[8:12]}-{episode_id[12:14]}-{episode_id[14:16]}",
        "source": source,
        "observed": {
            "situation": {"value": "Group chat.", "source_quote": "group chat"},
            "automatic_thought": {
                "value": "They will judge me.",
                "source_quote": "they will judge me",
            },
            "emotion": {"value": emotion, "source_quote": emotion},
            "physical": {"value": "Tight chest.", "source_quote": "tight chest"},
            "behavior": {"value": "Closed the chat.", "source_quote": "closed the chat"},
            "short_term_consequence": {"value": "Relief.", "source_quote": "Relief."},
            "long_term_consequence": {
                "value": "Still unresolved.",
                "source_quote": "Still unresolved.",
            },
        },
        "derived": derived,
    }

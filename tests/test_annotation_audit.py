import json

import pytest

from app.annotation_audit import audit_episode_dir
from app.derived_normalizer import empty_derived


def test_audit_counts_valid_invalid_and_derived_coverage(tmp_path):
    episode_dir = tmp_path / "episodes"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode(derived=empty_derived()))
    _write_json(
        episode_dir / "episode-20260430-2.json",
        _episode("episode-20260430-2", derived=_derived()),
    )
    (episode_dir / "episode-20260430-3.json").write_text("{broken", encoding="utf-8")

    summary = audit_episode_dir(episode_dir)

    assert summary.total == 3
    assert summary.observed_count == 2
    assert summary.annotation_row_count == 0
    assert summary.annotated_count == 2
    assert summary.pending_count == 0
    assert summary.pending_episode_ids == ()
    assert summary.coverage == "full"
    assert summary.valid == 2
    assert summary.invalid == 1
    assert summary.empty_derived == 1
    assert summary.with_nodes == 1
    assert summary.with_annotations == 1
    assert summary.with_relations == 1
    assert summary.observed_ready == 2
    assert summary.annotation_ready == 1
    assert summary.graph_ready == 1
    assert summary.report_ready == 1
    assert summary.payload_eligible == 1
    assert summary.gap_reasons == {"empty_derived": 1}
    assert summary.nodes_total == 3
    assert summary.trigger_annotations_total == 1
    assert summary.cognition_annotations_total == 1
    assert summary.emotion_annotations_total == 1
    assert summary.behavior_annotations_total == 1
    assert summary.relations_total == 1
    assert summary.invalid_files == ("episode-20260430-3.json: JSONDecodeError",)


def test_audit_hydrates_selected_annotation_run(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(run_dir, [_annotation_row("episode-20260430-1", _derived())])

    summary = audit_episode_dir(episode_dir, annotation_run_dir=run_dir)

    assert summary.total == 1
    assert summary.observed_count == 1
    assert summary.annotation_row_count == 1
    assert summary.annotated_count == 1
    assert summary.pending_count == 0
    assert summary.coverage == "full"
    assert summary.empty_derived == 0
    assert summary.annotation_ready == 1
    assert summary.graph_ready == 1
    assert summary.report_ready == 1
    assert summary.payload_eligible == 1


def test_audit_missing_annotation_row_is_explicit_gap(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(run_dir, [])

    summary = audit_episode_dir(episode_dir, annotation_run_dir=run_dir)

    assert summary.total == 1
    assert summary.observed_count == 1
    assert summary.annotation_row_count == 0
    assert summary.annotated_count == 0
    assert summary.pending_count == 1
    assert summary.pending_episode_ids == ("episode-20260430-1",)
    assert summary.coverage == "partial"
    assert summary.empty_derived == 1
    assert summary.annotation_ready == 0
    assert summary.graph_ready == 0
    assert summary.gap_reasons == {"empty_derived": 1}


def test_audit_require_full_coverage_fails_on_partial_coverage(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(run_dir, [])

    with pytest.raises(ValueError, match="coverage is partial"):
        audit_episode_dir(
            episode_dir,
            annotation_run_dir=run_dir,
            require_full=True,
        )


def test_audit_is_read_only(tmp_path):
    episode_dir = tmp_path / "episodes"
    episode_dir.mkdir()
    path = episode_dir / "episode-20260430-1.json"
    _write_json(path, _observed_only_episode())
    before = {item.name: item.read_text(encoding="utf-8") for item in episode_dir.iterdir()}

    audit_episode_dir(episode_dir)

    after = {item.name: item.read_text(encoding="utf-8") for item in episode_dir.iterdir()}
    assert after == before
    assert sorted(item.name for item in tmp_path.iterdir()) == ["episodes"]


def _episode(
    episode_id="episode-20260430-1",
    *,
    derived=None,
    source="telegram-chat:123",
):
    data = _observed_only_episode(episode_id=episode_id, source=source)
    data["derived"] = _derived() if derived is None else derived
    return data


def _observed_only_episode(
    episode_id="episode-20260430-1",
    *,
    source="telegram-chat:123",
):
    return {
        "id": episode_id,
        "date": "2026-04-30",
        "source": source,
        "observed": {
            "situation": {"value": "Group chat.", "source_quote": "group chat"},
            "automatic_thought": {
                "value": "They will judge me.",
                "source_quote": "they will judge me",
            },
            "emotion": {"value": "страх", "source_quote": "страх"},
            "physical": {"value": "Tight chest.", "source_quote": "tight chest"},
            "behavior": {"value": "Closed chat.", "source_quote": "closed chat"},
            "short_term_consequence": {"value": "Relief.", "source_quote": "relief"},
            "long_term_consequence": {
                "value": "Question unresolved.",
                "source_quote": "unresolved",
            },
        },
    }


def _derived():
    return {
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
                "kind": "emotion",
                "text": "страх",
                "source_field": "observed.emotion",
                "source_quote": "страх",
                "confidence": 0.9,
            },
            {
                "id": "node-3",
                "node_origin": "observed",
                "kind": "behavior",
                "text": "Closed chat.",
                "source_field": "observed.behavior",
                "source_quote": "closed chat",
                "confidence": 0.9,
            },
        ],
        "trigger_annotations": [
            {
                "id": "trigger-annotation-1",
                "type": "social",
                "source_field": "observed.situation",
                "source_quote": "group chat",
                "confidence": 0.9,
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
                "confidence": 0.8,
            }
        ],
        "emotion_annotations": [
            {
                "id": "emotion-annotation-1",
                "node_id": "node-2",
                "label": "страх",
                "valence": -0.8,
                "arousal": 0.9,
                "source_field": "observed.emotion",
                "source_quote": "страх",
                "confidence": 0.9,
            }
        ],
        "behavior_annotations": [
            {
                "id": "behavior-annotation-1",
                "node_id": "node-3",
                "type": "avoid",
                "source_field": "observed.behavior",
                "source_quote": "closed chat",
                "confidence": 0.9,
            }
        ],
        "outcome_annotations": [],
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


def _annotation_row(episode_id, derived):
    return {"episode_id": episode_id, "derived": derived}


def _write_annotation_run(run_dir, rows):
    run_dir.mkdir(parents=True)
    _write_json(
        run_dir / "manifest.json",
        {
            "annotation_run_id": "run-test",
            "schema_version": "episode-v1",
            "taxonomy_version": "taxonomy-v1",
            "prompt_version": "prompt-v1",
            "created_at": "2026-06-05T00:00:00Z",
            "source_episode_count": len(rows),
        },
    )
    (run_dir / "annotations.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

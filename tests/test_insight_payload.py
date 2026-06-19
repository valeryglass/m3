import json

import pytest

from app.analytics_loader import AnnotationCoverage
from app.graph_report import build_report
from app.insight_payload import build_insight_payload, main
from app.schemas.episode import Episode


def test_insight_payload_collects_target_agnostic_entities():
    report = build_report(
        [
            _load(_episode("episode-20260430-1", behavior_type="avoid")),
            _load(_episode("episode-20260430-2", behavior_type="avoid")),
            _load(_episode("episode-20260430-3", behavior_type="avoid")),
            _load(_episode("episode-20260430-4", behavior_type="approach")),
        ],
        coverage=AnnotationCoverage(
            observed_count=4,
            annotation_row_count=4,
            annotated_count=4,
            pending_count=0,
            pending_episode_ids=(),
            coverage="full",
        ),
    )

    payload = build_insight_payload(report)

    assert payload.kind == "insight_payload"
    assert payload.sample.total_episodes == 4
    assert payload.background.trigger == "social"
    assert payload.dominant_motif is not None
    assert payload.dominant_motif.support_count == 3
    assert payload.main_fork is not None
    assert payload.main_fork.support_count == 4
    assert payload.counterexample is not None
    assert payload.counterexample.dominant.behavior == "avoid"
    assert payload.counterexample.alternative.behavior == "approach"
    assert payload.outcome_patterns[0].horizon == "short_term"
    assert payload.outcome_patterns[0].total_count == 3


def test_insight_payload_to_dict_is_json_serializable_and_raw():
    report = build_report([_load(_episode("episode-20260430-1"))])

    payload_dict = build_insight_payload(report).to_dict()

    json.dumps(payload_dict, ensure_ascii=False)
    assert payload_dict["kind"] == "insight_payload"
    assert "Развилка реакций" not in json.dumps(payload_dict, ensure_ascii=False)
    assert "контакт с людьми" not in json.dumps(payload_dict, ensure_ascii=False)


def test_insight_payload_cli_writes_debug_json(tmp_path, monkeypatch, capsys):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    episode = _episode("episode-20260430-1")
    (episode_dir / "episode-20260430-1.json").write_text(
        json.dumps(episode, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_annotation_run(
        run_dir,
        [("episode-20260430-1", episode["derived"])],
    )
    output = tmp_path / "insight.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "insight_payload",
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
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "insight_payload"
    assert data["sample"]["total_episodes"] == 1
    assert data["sample"]["graph_ready_episode_ids"] == ["episode-20260430-1"]


def test_insight_payload_cli_accepts_full_multi_source_run(
    tmp_path,
    monkeypatch,
    capsys,
):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    first = _episode("episode-20260430-1")
    second = _episode("episode-20260430-2")
    second["source"] = "telegram-chat:456"
    for episode in (first, second):
        (episode_dir / f"{episode['id']}.json").write_text(
            json.dumps(episode, ensure_ascii=False),
            encoding="utf-8",
        )
    _write_annotation_run(
        run_dir,
        [(first["id"], first["derived"]), (second["id"], second["derived"])],
    )
    output = tmp_path / "insight.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "insight_payload",
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
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["coverage"]["state"] == "full"
    assert data["sample"]["total_episodes"] == 1
    assert data["sample"]["payload_eligible_count"] == 1


def test_insight_payload_cli_rejects_partial_coverage_without_writing(
    tmp_path,
    monkeypatch,
):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    first = _episode("episode-20260430-1")
    second = _episode("episode-20260430-2")
    for episode in (first, second):
        (episode_dir / f"{episode['id']}.json").write_text(
            json.dumps(episode, ensure_ascii=False),
            encoding="utf-8",
    )
    _write_annotation_run(run_dir, [(first["id"], first["derived"])])
    output = tmp_path / "insight.json"
    output.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "insight_payload",
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

    with pytest.raises(ValueError, match="coverage is partial"):
        main()

    assert output.read_text(encoding="utf-8") == "existing"


def test_insight_payload_cli_rejects_empty_derived_without_writing(
    tmp_path,
    monkeypatch,
):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    episode = _episode("episode-20260430-1")
    (episode_dir / f"{episode['id']}.json").write_text(
        json.dumps(episode, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_annotation_run(run_dir, [(episode["id"], _empty_derived())])
    output = tmp_path / "insight.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "insight_payload",
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

    with pytest.raises(ValueError, match="payload readiness is incomplete"):
        main()

    assert not output.exists()


def _load(data):
    return Episode.model_validate(data)


def _write_annotation_run(run_dir, rows):
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "annotation_run_id": run_dir.name,
                "schema_version": "episode.v1",
                "taxonomy_version": "taxonomy.v1",
                "prompt_version": "prompt.v1",
                "created_at": "2026-05-01T00:00:00Z",
                "source_episode_count": len(rows),
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "annotations.jsonl").write_text(
        "".join(
            json.dumps(
                {"episode_id": episode_id, "derived": derived},
                ensure_ascii=False,
            )
            + "\n"
            for episode_id, derived in rows
        ),
        encoding="utf-8",
    )


def _empty_derived():
    return {
        "nodes": [],
        "trigger_annotations": [],
        "actor_annotations": [],
        "cognition_annotations": [],
        "emotion_annotations": [],
        "behavior_annotations": [],
        "outcome_annotations": [],
        "relations": [],
    }


def _episode(
    episode_id,
    *,
    behavior_type="avoid",
    outcome_type="relief",
    emotion_label="страх",
):
    return {
        "id": episode_id,
        "date": f"{episode_id[8:12]}-{episode_id[12:14]}-{episode_id[14:16]}",
        "source": "telegram-chat:123",
        "observed": {
            "situation": {"value": "Group chat.", "source_quote": "group chat"},
            "automatic_thought": {
                "value": "They will judge me.",
                "source_quote": "they will judge me",
            },
            "emotion": {"value": emotion_label, "source_quote": emotion_label},
            "physical": {"value": "Tight chest.", "source_quote": "tight chest"},
            "behavior": {"value": "Closed the chat.", "source_quote": "Closed the chat."},
            "short_term_consequence": {"value": "Relief.", "source_quote": "Relief."},
            "long_term_consequence": {
                "value": "Still unresolved.",
                "source_quote": "Still unresolved.",
            },
        },
        "derived": {
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
                    "label": emotion_label,
                    "intensity": 0.66,
                    "valence": -0.8,
                    "arousal": 0.8,
                    "source_field": "observed.emotion",
                    "source_quote": emotion_label,
                    "confidence": 0.9,
                }
            ],
            "behavior_annotations": [
                {
                    "id": "behavior-annotation-1",
                    "type": behavior_type,
                    "source_field": "observed.behavior",
                    "source_quote": "Closed the chat.",
                    "confidence": 0.9,
                }
            ],
            "outcome_annotations": [
                {
                    "id": "outcome-annotation-1",
                    "node_id": "node-2",
                    "horizon": "short_term",
                    "type": outcome_type,
                    "source_field": "observed.short_term_consequence",
                    "source_quote": "Relief.",
                    "confidence": 0.85,
                }
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
        },
    }

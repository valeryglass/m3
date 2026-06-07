import json

import pytest

from app.analytics_loader import (
    annotation_coverage,
    annotation_coverage_for_episode_ids,
    load_analytics_episodes,
    require_full_coverage,
)
from app.derived_normalizer import empty_derived


def test_loads_embedded_derived_episode(tmp_path):
    episode_dir = tmp_path / "episodes"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode())

    episodes = load_analytics_episodes(episode_dir)

    assert len(episodes) == 1
    assert episodes[0].id == "episode-20260430-1"
    assert episodes[0].derived.nodes[0].id == "node-1"


def test_loads_current_derived_alias(tmp_path):
    episode_dir = tmp_path / "episodes"
    episode_dir.mkdir()
    data = _episode()
    data["current_derived"] = data.pop("derived")
    _write_json(episode_dir / "episode-20260430-1.json", data)

    episodes = load_analytics_episodes(episode_dir)

    assert episodes[0].derived.cognition_annotations[0].kind == "prediction"


def test_loads_observed_only_episode_with_annotation_run(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(run_dir, [_annotation_row("episode-20260430-1", _derived())])

    episodes = load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)

    assert episodes[0].derived.nodes[0].id == "node-1"
    assert episodes[0].derived.relations[0].type == "belongs_to"


def test_annotation_run_overrides_embedded_derived(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    embedded = _episode()
    embedded["derived"] = empty_derived()
    _write_json(episode_dir / "episode-20260430-1.json", embedded)
    _write_annotation_run(run_dir, [_annotation_row("episode-20260430-1", _derived())])

    episodes = load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)

    assert episodes[0].derived.nodes


def test_explicit_annotation_run_overrides_latest_discovered_run(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    explicit_run = run_root / "run-20260601"
    latest_run = run_root / "run-20260602"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(
        explicit_run,
        [_annotation_row("episode-20260430-1", _derived(text="explicit"))],
    )
    _write_annotation_run(
        latest_run,
        [_annotation_row("episode-20260430-1", _derived(text="latest"))],
    )

    episodes = load_analytics_episodes(
        episode_dir,
        annotation_run_dir=explicit_run,
        annotation_run_root=run_root,
    )

    assert episodes[0].derived.nodes[0].text == "explicit"


def test_env_annotation_run_overrides_root_discovery(tmp_path, monkeypatch):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    env_run = run_root / "run-20260601"
    latest_run = run_root / "run-20260602"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(
        env_run,
        [_annotation_row("episode-20260430-1", _derived(text="env"))],
    )
    _write_annotation_run(
        latest_run,
        [_annotation_row("episode-20260430-1", _derived(text="latest"))],
    )
    monkeypatch.setenv("M3_ANNOTATION_RUN_DIR", str(env_run))

    episodes = load_analytics_episodes(
        episode_dir,
        annotation_run_root=run_root,
    )

    assert episodes[0].derived.nodes[0].text == "env"


def test_latest_valid_annotation_run_is_discovered(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    older_run = run_root / "run-20260601"
    latest_run = run_root / "run-20260602"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(
        older_run,
        [_annotation_row("episode-20260430-1", _derived(text="older"))],
    )
    _write_annotation_run(
        latest_run,
        [_annotation_row("episode-20260430-1", _derived(text="latest"))],
    )

    episodes = load_analytics_episodes(
        episode_dir,
        annotation_run_root=run_root,
    )

    assert episodes[0].derived.nodes[0].text == "latest"


def test_invalid_latest_discovered_run_is_skipped_for_older_valid_run(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    older_run = run_root / "run-20260601"
    invalid_latest = run_root / "run-20260602"
    episode_dir.mkdir()
    invalid_latest.mkdir(parents=True)
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(
        older_run,
        [_annotation_row("episode-20260430-1", _derived(text="older"))],
    )
    _write_json(invalid_latest / "manifest.json", {"annotation_run_id": "bad"})
    (invalid_latest / "annotations.jsonl").write_text("", encoding="utf-8")

    episodes = load_analytics_episodes(
        episode_dir,
        annotation_run_root=run_root,
    )

    assert episodes[0].derived.nodes[0].text == "older"


def test_no_valid_discovered_run_falls_back_to_embedded_derived(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    invalid_run = run_root / "run-20260601"
    episode_dir.mkdir()
    invalid_run.mkdir(parents=True)
    _write_json(episode_dir / "episode-20260430-1.json", _episode())
    _write_json(invalid_run / "manifest.json", {"annotation_run_id": "bad"})
    (invalid_run / "annotations.jsonl").write_text("", encoding="utf-8")

    episodes = load_analytics_episodes(
        episode_dir,
        annotation_run_root=run_root,
    )

    assert episodes[0].derived.nodes[0].text == "They will judge me."


def test_missing_annotation_row_uses_empty_derived(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(run_dir, [])

    episodes = load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)

    assert episodes[0].derived.model_dump(mode="json") == empty_derived()


def test_annotation_coverage_reports_full_and_partial_runs(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_json(
        episode_dir / "episode-20260430-2.json",
        _observed_only_episode() | {"episode_id": "episode-20260430-2"},
    )
    _write_annotation_run(run_dir, [_annotation_row("episode-20260430-1", _derived())])

    coverage = annotation_coverage(episode_dir, annotation_run_dir=run_dir)

    assert coverage.observed_count == 2
    assert coverage.annotation_row_count == 1
    assert coverage.annotated_count == 1
    assert coverage.pending_count == 1
    assert coverage.pending_episode_ids == ("episode-20260430-2",)
    assert coverage.coverage == "partial"

    with pytest.raises(ValueError, match="coverage is partial"):
        require_full_coverage(coverage)


def test_annotation_coverage_can_count_subset_while_validating_full_run(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_json(
        episode_dir / "episode-20260430-2.json",
        _observed_only_episode() | {"episode_id": "episode-20260430-2"},
    )
    _write_annotation_run(
        run_dir,
        [
            _annotation_row("episode-20260430-1", _derived()),
            _annotation_row("episode-20260430-2", _derived()),
        ],
    )

    coverage = annotation_coverage(
        episode_dir,
        annotation_run_dir=run_dir,
    )
    scoped = annotation_coverage_for_episode_ids(
        {"episode-20260430-1"},
        annotation_run_dir=run_dir,
        known_episode_ids={"episode-20260430-1", "episode-20260430-2"},
    )

    assert coverage.coverage == "full"
    assert scoped.observed_count == 1
    assert scoped.annotated_count == 1
    assert scoped.pending_count == 0


def test_missing_annotation_row_does_not_fall_back_to_embedded_derived(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode())
    _write_annotation_run(run_dir, [])

    episodes = load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)

    assert episodes[0].derived.model_dump(mode="json") == empty_derived()


def test_duplicate_annotation_rows_fail(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(
        run_dir,
        [
            _annotation_row("episode-20260430-1", _derived()),
            _annotation_row("episode-20260430-1", _derived()),
        ],
    )

    with pytest.raises(ValueError, match="duplicate annotation row"):
        load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)


def test_unknown_annotation_episode_fails(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_annotation_run(run_dir, [_annotation_row("episode-20260430-2", _derived())])

    with pytest.raises(ValueError, match="unknown episode"):
        load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)


def test_malformed_manifest_fails(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    run_dir.mkdir(parents=True)
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_json(run_dir / "manifest.json", {"annotation_run_id": "run-test"})
    (run_dir / "annotations.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="manifest"):
        load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)


def test_malformed_annotation_row_fails(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    run_dir.mkdir(parents=True)
    _write_json(episode_dir / "episode-20260430-1.json", _observed_only_episode())
    _write_manifest(run_dir)
    (run_dir / "annotations.jsonl").write_text('{"episode_id": 1}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="row"):
        load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)


def _observed_only_episode():
    data = _episode()
    data.pop("derived")
    data["episode_id"] = data.pop("id")
    data["metadata"] = {"capture_version": "test"}
    return data


def _episode():
    return {
        "id": "episode-20260430-1",
        "date": "2026-04-30",
        "source": "telegram-chat:123",
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
        "derived": _derived(),
    }


def _derived(text="They will judge me."):
    return {
        "nodes": [
            {
                "id": "node-1",
                "node_origin": "observed",
                "kind": "cognition",
                "text": text,
                "source_field": "observed.automatic_thought",
                "source_quote": "they will judge me",
                "confidence": 0.9,
            }
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
        "emotion_annotations": [],
        "behavior_annotations": [],
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
    _write_manifest(run_dir)
    (run_dir / "annotations.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_manifest(run_dir):
    _write_json(
        run_dir / "manifest.json",
        {
            "annotation_run_id": "run-test",
            "schema_version": "episode-v1",
            "taxonomy_version": "taxonomy-v1",
            "prompt_version": "prompt-v1",
            "created_at": "2026-06-05T00:00:00Z",
            "source_episode_count": 1,
        },
    )


def _write_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

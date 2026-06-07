import json

import pytest

from app.analytics_loader import load_analytics_episodes
from app.annotation_migration import (
    build_baseline_run,
    check_observed_only,
    strip_embedded_derived,
)
from app.derived_normalizer import empty_derived
from app.graph_report import build_report, load_episodes
from app.map_payload import build_map_payload
from app.schemas.episode import Episode


def test_baseline_dry_run_creates_no_files(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode())

    summary = build_baseline_run(
        episode_dir,
        output_root,
        timestamp="20260605-120000",
    )

    assert summary.dry_run is True
    assert summary.episode_count == 1
    assert summary.row_count == 1
    assert summary.empty_derived_count == 0
    assert summary.readiness_matches is True
    assert not output_root.exists()


def test_baseline_write_creates_manifest_and_annotations(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode())

    summary = build_baseline_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260605-120000",
    )

    run_dir = output_root / "run-20260605-120000-baseline"
    assert summary.dry_run is False
    assert summary.run_dir == run_dir.as_posix()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = _read_jsonl(run_dir / "annotations.jsonl")
    assert manifest["annotation_run_id"] == "run-20260605-120000-baseline"
    assert manifest["schema_version"] == "episode-v1"
    assert manifest["taxonomy_version"] == "graph-v1"
    assert manifest["prompt_version"] == "embedded-derived-baseline"
    assert manifest["source_episode_count"] == 1
    assert rows[0]["episode_id"] == "episode-20260430-1"


def test_generated_run_can_be_selected_explicitly(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    episode = _episode()
    derived = episode.pop("derived")
    _write_json(episode_dir / "episode-20260430-1.json", episode)
    episode_with_derived = _episode()
    episode_with_derived["derived"] = derived
    _write_json(episode_dir / "episode-20260430-1.json", episode_with_derived)

    summary = build_baseline_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260605-120000",
    )

    episodes = load_analytics_episodes(
        episode_dir,
        annotation_run_dir=output_root / "run-20260605-120000-baseline",
    )
    assert summary.row_count == 1
    assert episodes[0].derived.nodes[0].id == "node-1"


def test_row_count_matches_active_episode_count(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode())
    _write_json(
        episode_dir / "episode-20260430-2.json",
        _episode("episode-20260430-2"),
    )

    summary = build_baseline_run(
        episode_dir,
        output_root,
        timestamp="20260605-120000",
    )

    assert summary.episode_count == 2
    assert summary.row_count == 2


def test_embedded_and_current_derived_export(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    embedded = _episode("episode-20260430-1", text="embedded")
    current = _episode("episode-20260430-2", text="current")
    current["current_derived"] = current.pop("derived")
    _write_json(episode_dir / "episode-20260430-1.json", embedded)
    _write_json(episode_dir / "episode-20260430-2.json", current)

    build_baseline_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260605-120000",
    )

    rows = _read_jsonl(
        output_root / "run-20260605-120000-baseline" / "annotations.jsonl"
    )
    assert rows[0]["derived"]["nodes"][0]["text"] == "embedded"
    assert rows[1]["derived"]["nodes"][0]["text"] == "current"


def test_missing_derived_exports_empty_and_counts_gap(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    episode = _episode()
    episode.pop("derived")
    _write_json(episode_dir / "episode-20260430-1.json", episode)

    summary = build_baseline_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260605-120000",
    )

    rows = _read_jsonl(
        output_root / "run-20260605-120000-baseline" / "annotations.jsonl"
    )
    assert summary.empty_derived_count == 1
    assert rows[0]["derived"] == empty_derived()


def test_duplicate_episode_ids_fail(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode())
    _write_json(episode_dir / "episode-20260430-2.json", _episode())

    with pytest.raises(ValueError, match="duplicate episode id"):
        build_baseline_run(
            episode_dir,
            output_root,
            write=True,
            timestamp="20260605-120000",
        )
    assert not output_root.exists()


def test_invalid_derived_fails_before_writing(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    episode = _episode()
    episode["derived"]["nodes"][0]["source_field"] = "observed.physical"
    _write_json(episode_dir / "episode-20260430-1.json", episode)

    with pytest.raises(ValueError, match="invalid episode derived"):
        build_baseline_run(
            episode_dir,
            output_root,
            write=True,
            timestamp="20260605-120000",
        )
    assert not output_root.exists()


def test_existing_output_run_dir_fails(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    run_dir = output_root / "run-20260605-120000-baseline"
    episode_dir.mkdir()
    run_dir.mkdir(parents=True)
    _write_json(episode_dir / "episode-20260430-1.json", _episode())

    with pytest.raises(ValueError, match="already exists"):
        build_baseline_run(
            episode_dir,
            output_root,
            write=True,
            timestamp="20260605-120000",
        )


def test_readiness_counts_match_between_embedded_and_generated_run(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode())

    summary = build_baseline_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260605-120000",
    )

    assert summary.embedded_readiness == summary.generated_run_readiness
    assert summary.readiness_matches is True


def test_strip_dry_run_writes_nothing(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    before = (episode_dir / "episode-20260430-1.json").read_text(encoding="utf-8")

    summary = strip_embedded_derived(
        episode_dir,
        run_dir,
        backup_root,
        timestamp="20260605-130000",
    )

    assert summary.dry_run is True
    assert summary.would_strip_count == 1
    assert summary.stripped_count == 0
    assert summary.backup_dir is None
    assert summary.restore_hint is None
    assert summary.readiness_matches is True
    assert summary.readiness_policy == "exact_match"
    assert summary.allow_readiness_improvement is False
    assert summary.readiness_delta == {
        "graph_ready": 0,
        "report_ready": 0,
        "payload_eligible": 0,
    }
    assert (episode_dir / "episode-20260430-1.json").read_text(encoding="utf-8") == before
    assert not backup_root.exists()


def test_readiness_improvement_fails_without_flag(tmp_path):
    episode_dir, run_dir, backup_root = _improvement_fixture(tmp_path)

    with pytest.raises(ValueError, match="allow-readiness-improvement"):
        strip_embedded_derived(
            episode_dir,
            run_dir,
            backup_root,
            timestamp="20260605-130000",
        )
    assert not backup_root.exists()


def test_readiness_improvement_succeeds_with_flag_in_dry_run(tmp_path):
    episode_dir, run_dir, backup_root = _improvement_fixture(tmp_path)
    before = (episode_dir / "episode-20260430-1.json").read_text(encoding="utf-8")

    summary = strip_embedded_derived(
        episode_dir,
        run_dir,
        backup_root,
        allow_readiness_improvement=True,
        timestamp="20260605-130000",
    )

    assert summary.dry_run is True
    assert summary.readiness_policy == "allow_improvement"
    assert summary.allow_readiness_improvement is True
    assert summary.readiness_delta == {
        "graph_ready": 1,
        "report_ready": 1,
        "payload_eligible": 1,
    }
    assert (episode_dir / "episode-20260430-1.json").read_text(encoding="utf-8") == before
    assert not backup_root.exists()


def test_readiness_improvement_succeeds_with_flag_in_write_mode(tmp_path):
    episode_dir, run_dir, backup_root = _improvement_fixture(tmp_path)

    summary = strip_embedded_derived(
        episode_dir,
        run_dir,
        backup_root,
        write=True,
        allow_readiness_improvement=True,
        timestamp="20260605-130000",
    )

    backup_dir = backup_root / "episodes-derived-migration-20260605-130000"
    stripped = json.loads(
        (episode_dir / "episode-20260430-1.json").read_text(encoding="utf-8")
    )
    assert summary.stripped_count == 1
    assert summary.backup_dir == backup_dir.as_posix()
    assert summary.readiness_policy == "allow_improvement"
    assert summary.readiness_delta == {
        "graph_ready": 1,
        "report_ready": 1,
        "payload_eligible": 1,
    }
    assert (backup_dir / "episode-20260430-1.json").exists()
    assert "derived" not in stripped
    assert "current_derived" not in stripped


def test_strip_write_creates_backup_and_removes_embedded_fields(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    episode_path = episode_dir / "episode-20260430-1.json"
    original = json.loads(episode_path.read_text(encoding="utf-8"))

    summary = strip_embedded_derived(
        episode_dir,
        run_dir,
        backup_root,
        write=True,
        timestamp="20260605-130000",
    )

    backup_dir = backup_root / "episodes-derived-migration-20260605-130000"
    stripped = json.loads(episode_path.read_text(encoding="utf-8"))
    backup = json.loads((backup_dir / "episode-20260430-1.json").read_text(encoding="utf-8"))
    assert summary.dry_run is False
    assert summary.stripped_count == 1
    assert summary.backup_dir == backup_dir.as_posix()
    assert summary.restore_hint is not None
    assert backup == original
    assert "derived" not in stripped
    assert "current_derived" not in stripped
    for key, value in original.items():
        if key not in {"derived", "current_derived"}:
            assert stripped[key] == value


def test_strip_removes_current_derived(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    backup_root = tmp_path / "backups"
    episode_dir.mkdir()
    episode = _episode()
    episode["current_derived"] = episode.pop("derived")
    _write_json(episode_dir / "episode-20260430-1.json", episode)
    build_baseline_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260605-120000",
    )

    strip_embedded_derived(
        episode_dir,
        output_root / "run-20260605-120000-baseline",
        backup_root,
        write=True,
        timestamp="20260605-130000",
    )

    stripped = json.loads((episode_dir / "episode-20260430-1.json").read_text(encoding="utf-8"))
    assert "derived" not in stripped
    assert "current_derived" not in stripped


def test_backup_verification_failure_stops_before_strip(tmp_path, monkeypatch):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)

    def skip_copy(source_path, backup_path):
        return None

    monkeypatch.setattr("app.annotation_migration._copy_episode_backup", skip_copy)
    with pytest.raises(ValueError, match="backup missing"):
        strip_embedded_derived(
            episode_dir,
            run_dir,
            backup_root,
            write=True,
            timestamp="20260605-130000",
        )
    data = json.loads((episode_dir / "episode-20260430-1.json").read_text(encoding="utf-8"))
    assert "derived" in data


def test_backup_dir_collision_fails_safely(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    (backup_root / "episodes-derived-migration-20260605-130000").mkdir(parents=True)

    with pytest.raises(ValueError, match="backup directory already exists"):
        strip_embedded_derived(
            episode_dir,
            run_dir,
            backup_root,
            write=True,
            timestamp="20260605-130000",
        )
    data = json.loads((episode_dir / "episode-20260430-1.json").read_text(encoding="utf-8"))
    assert "derived" in data


def test_invalid_annotation_run_fails_before_backup(tmp_path):
    episode_dir = tmp_path / "episodes"
    backup_root = tmp_path / "backups"
    run_dir = tmp_path / "annotation-runs" / "run-bad"
    episode_dir.mkdir()
    run_dir.mkdir(parents=True)
    _write_json(episode_dir / "episode-20260430-1.json", _episode())

    with pytest.raises(ValueError, match="invalid annotation run manifest"):
        strip_embedded_derived(episode_dir, run_dir, backup_root, write=True)
    assert not backup_root.exists()


def test_duplicate_annotation_rows_fail_before_backup(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    row = _read_jsonl(run_dir / "annotations.jsonl")[0]
    (run_dir / "annotations.jsonl").write_text(
        json.dumps(row) + "\n" + json.dumps(row) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate annotation row"):
        strip_embedded_derived(episode_dir, run_dir, backup_root, write=True)
    assert not backup_root.exists()


def test_unknown_annotation_row_fails_before_backup(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    row = _read_jsonl(run_dir / "annotations.jsonl")[0]
    row["episode_id"] = "episode-20260430-9"
    (run_dir / "annotations.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown episode"):
        strip_embedded_derived(episode_dir, run_dir, backup_root, write=True)
    assert not backup_root.exists()


def test_annotation_row_count_mismatch_fails_before_backup(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    (run_dir / "annotations.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="row count"):
        strip_embedded_derived(episode_dir, run_dir, backup_root, write=True)
    assert not backup_root.exists()


def test_readiness_mismatch_fails_before_backup(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    row = _read_jsonl(run_dir / "annotations.jsonl")[0]
    row["derived"] = empty_derived()
    (run_dir / "annotations.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="regresses"):
        strip_embedded_derived(episode_dir, run_dir, backup_root, write=True)
    assert not backup_root.exists()


def test_readiness_regression_fails_even_with_improvement_flag(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    row = _read_jsonl(run_dir / "annotations.jsonl")[0]
    row["derived"] = empty_derived()
    (run_dir / "annotations.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="regresses"):
        strip_embedded_derived(
            episode_dir,
            run_dir,
            backup_root,
            write=True,
            allow_readiness_improvement=True,
        )
    assert not backup_root.exists()


def test_stripped_episode_validates_and_loads_with_explicit_run(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)

    strip_embedded_derived(
        episode_dir,
        run_dir,
        backup_root,
        write=True,
        timestamp="20260605-130000",
    )

    data = json.loads((episode_dir / "episode-20260430-1.json").read_text(encoding="utf-8"))
    episode = Episode.model_validate(data)
    loaded = load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)
    assert episode.derived.nodes == []
    assert loaded[0].derived.nodes[0].id == "node-1"


def test_graph_report_and_map_payload_build_from_stripped_episode(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    strip_embedded_derived(
        episode_dir,
        run_dir,
        backup_root,
        write=True,
        timestamp="20260605-130000",
    )

    episodes = load_episodes(episode_dir, annotation_run_dir=run_dir)
    report = build_report(episodes)
    payload = build_map_payload(episodes, source="telegram-chat:123")

    assert len(report.graph_ready) == 1
    assert report.readiness[0].payload_eligible is True
    assert payload["provenance"]["graph_ready_episode_ids"] == ["episode-20260430-1"]


def test_check_observed_only_fails_when_top_level_derived_remains(tmp_path):
    episode_dir = tmp_path / "episodes"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode())

    with pytest.raises(ValueError, match="top-level derived"):
        check_observed_only(episode_dir)


def test_selected_annotation_run_still_overrides_embedded_derived(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    episode = _episode(text="Embedded different")
    _write_json(episode_dir / "episode-20260430-1.json", episode)

    loaded = load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)

    assert loaded[0].derived.nodes[0].text == "They will judge me."


def _episode(episode_id="episode-20260430-1", *, text="They will judge me."):
    return {
        "id": episode_id,
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
        "derived": _derived(text=text),
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
                "text": text,
                "kind": "prediction",
                "source_field": "observed.automatic_thought",
                "source_quote": "they will judge me",
                "confidence": 0.8,
            }
        ],
        "emotion_annotations": [
            {
                "id": "emotion-annotation-1",
                "label": "страх",
                "intensity": 0.7,
                "valence": -0.8,
                "arousal": 0.8,
                "source_field": "observed.emotion",
                "source_quote": "страх",
                "confidence": 0.85,
            }
        ],
        "behavior_annotations": [
            {
                "id": "behavior-annotation-1",
                "type": "avoid",
                "source_field": "observed.behavior",
                "source_quote": "closed chat",
                "confidence": 0.85,
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


def _write_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _baseline_fixture(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    backup_root = tmp_path / "backups"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode())
    build_baseline_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260605-120000",
    )
    return episode_dir, output_root / "run-20260605-120000-baseline", backup_root


def _improvement_fixture(tmp_path):
    episode_dir, run_dir, backup_root = _baseline_fixture(tmp_path)
    episode = _episode()
    episode["derived"] = empty_derived()
    _write_json(episode_dir / "episode-20260430-1.json", episode)
    return episode_dir, run_dir, backup_root

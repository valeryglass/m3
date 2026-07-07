import json

from app.annotation_producer import produce_annotation_run
from app.fresh_analytics_status import (
    RECOMMENDATION_BLOCKED,
    RECOMMENDATION_FULL_SNAPSHOT,
    RECOMMENDATION_MISSING_ONLY,
    RECOMMENDATION_NO_OP_EMPTY,
    RECOMMENDATION_NO_OP_FULL_COVERAGE,
    build_status,
)


def test_fresh_analytics_status_no_episodes_is_noop_empty(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()

    status = build_status(episode_dir, run_root)

    assert status["recommendation"] == RECOMMENDATION_NO_OP_EMPTY
    assert status["recommended_command"] == ""
    assert status["observed_episode_count"] == 0
    assert status["selected_annotation_run_path"] is None
    assert status["dry_run"]["snapshot_written"] is False


def test_fresh_analytics_status_without_run_recommends_full_snapshot(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    journal_path = tmp_path / "journal.jsonl"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260503-1.json", _episode())

    status = build_status(episode_dir, run_root, journal_log=journal_path)

    assert status["recommendation"] == RECOMMENDATION_FULL_SNAPSHOT
    assert "make annotation-full" in status["recommended_command"]
    assert status["selected_annotation_run_path"] is None
    assert status["dry_run"]["generated_count"] == 1
    assert not run_root.exists()
    events = _read_jsonl(journal_path)
    assert events[0]["event_type"] == "fresh_analytics.status_checked"
    assert events[0]["details"]["recommendation"] == RECOMMENDATION_FULL_SNAPSHOT


def test_fresh_analytics_status_full_run_is_noop_full_coverage(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260503-1.json", _episode())
    produce_annotation_run(
        episode_dir,
        run_root,
        write=True,
        timestamp="20260618-120000",
    )

    status = build_status(episode_dir, run_root)

    run_dir = run_root / "run-20260618-120000-deterministic"
    assert status["recommendation"] == RECOMMENDATION_NO_OP_FULL_COVERAGE
    assert status["selected_annotation_run_path"] == run_dir.as_posix()
    assert status["selected_annotation_run_id"] == "run-20260618-120000-deterministic"
    assert status["coverage"] == "full"
    assert status["dry_run"]["generated_count"] == 0
    assert "make beta-analytics" in status["recommended_command"]
    assert f"ANNOTATION_RUN_DIR={run_dir.as_posix()}" in status["recommended_command"]


def test_fresh_analytics_status_partial_run_recommends_missing_only(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260503-1.json", _episode("episode-20260503-1"))
    produce_annotation_run(
        episode_dir,
        run_root,
        write=True,
        timestamp="20260618-120000",
    )
    _write_json(episode_dir / "episode-20260503-2.json", _episode("episode-20260503-2"))

    status = build_status(episode_dir, run_root)

    run_dir = run_root / "run-20260618-120000-deterministic"
    assert status["recommendation"] == RECOMMENDATION_MISSING_ONLY
    assert status["coverage"] == "partial"
    assert status["pending_count"] == 1
    assert status["pending_episode_ids"] == ["episode-20260503-2"]
    assert status["dry_run"]["generated_count"] == 1
    assert status["dry_run"]["coverage_after"] == "full"
    assert "make annotation-missing" in status["recommended_command"]
    assert f"ANNOTATION_RUN_DIR={run_dir.as_posix()}" in status["recommended_command"]
    assert not (run_root / "run-20260618-120001-deterministic").exists()


def test_fresh_analytics_status_invalid_episode_is_blocked(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    journal_path = tmp_path / "journal.jsonl"
    episode_dir.mkdir()
    (episode_dir / "episode-20260503-1.json").write_text("{broken", encoding="utf-8")

    status = build_status(episode_dir, run_root, journal_log=journal_path)

    assert status["recommendation"] == RECOMMENDATION_BLOCKED
    assert "Expecting property name" in status["blocker"]
    assert status["recommended_command"] == ""
    events = _read_jsonl(journal_path)
    assert events[0]["stage"] == "blocked"
    assert events[0]["level"] == "error"


def test_fresh_analytics_status_incomplete_missing_only_is_blocked(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    first = _episode("episode-20260503-1")
    second = _episode("episode-20260503-2")
    second["source"] = "telegram-chat:456"
    _write_json(episode_dir / "episode-20260503-1.json", first)
    produce_annotation_run(
        episode_dir,
        run_root,
        write=True,
        timestamp="20260618-120000",
    )
    _write_json(episode_dir / "episode-20260503-2.json", second)

    status = build_status(
        episode_dir,
        run_root,
        source="telegram-chat:123",
    )

    assert status["recommendation"] == RECOMMENDATION_BLOCKED
    assert "snapshot is incomplete" in status["blocker"]


def test_fresh_analytics_status_explicit_run_overrides_latest(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260503-1.json", _episode("episode-20260503-1"))
    produce_annotation_run(
        episode_dir,
        run_root,
        write=True,
        timestamp="20260618-120000",
    )
    _write_json(episode_dir / "episode-20260503-2.json", _episode("episode-20260503-2"))
    produce_annotation_run(
        episode_dir,
        run_root,
        write=True,
        timestamp="20260618-130000",
    )

    explicit_run = run_root / "run-20260618-120000-deterministic"
    latest_run = run_root / "run-20260618-130000-deterministic"
    status = build_status(
        episode_dir,
        run_root,
        annotation_run_dir=explicit_run,
    )

    assert latest_run.exists()
    assert status["selected_annotation_run_path"] == explicit_run.as_posix()
    assert status["selected_annotation_run_id"] == "run-20260618-120000-deterministic"
    assert status["recommendation"] == RECOMMENDATION_MISSING_ONLY


def _episode(episode_id="episode-20260503-1"):
    return {
        "id": episode_id,
        "date": "2026-05-03",
        "source": "telegram-chat:123",
        "observed": {
            "situation": {"value": "Group chat.", "source_quote": "group chat"},
            "trigger": {"value": "message", "source_quote": "message"},
            "actor": {"value": "colleague", "source_quote": "colleague"},
            "quote": {"value": "ping", "source_quote": "ping"},
            "automatic_thought": {
                "value": "They will judge me.",
                "source_quote": "they will judge me",
            },
            "emotion": {"value": "fear", "source_quote": "fear"},
            "behavior": {"value": "Closed chat.", "source_quote": "closed chat"},
            "physical": {"value": "Tight chest.", "source_quote": "tight chest"},
            "short_term_consequence": {"value": "Relief.", "source_quote": "relief"},
            "long_term_consequence": {
                "value": "Question unresolved.",
                "source_quote": "unresolved",
            },
        },
    }


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

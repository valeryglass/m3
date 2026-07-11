import asyncio
import json

from app.analytics_refresh import (
    FRESHNESS_BLOCKED,
    FRESHNESS_EMPTY,
    FRESHNESS_READY,
    FRESHNESS_STALE,
    AnalyticsRefreshCoordinator,
    inspect_analytics_freshness,
    refresh_analytics_once,
)
from app.analytics_loader import selected_annotation_run


def test_empty_episode_dir_is_ready_noop(tmp_path):
    status = inspect_analytics_freshness(
        tmp_path / "episodes",
        tmp_path / "annotation-runs",
    )

    assert status.state == FRESHNESS_EMPTY
    assert status.pending_count == 0


def test_full_snapshot_is_created_when_no_run_exists(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_episode(episode_dir, _episode("episode-20260711-1"))

    before = inspect_analytics_freshness(episode_dir, run_root)
    result = refresh_analytics_once(episode_dir, run_root)

    assert before.state == FRESHNESS_STALE
    assert result.action == "full_snapshot"
    assert result.freshness.state == FRESHNESS_READY
    assert result.freshness.annotation_row_count == 1
    assert result.summary is not None
    assert result.summary.snapshot_written is True


def test_missing_only_refresh_publishes_complete_snapshot(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_episode(episode_dir, _episode("episode-20260711-1"))
    first = refresh_analytics_once(episode_dir, run_root)
    _write_episode(episode_dir, _episode("episode-20260711-2"))

    result = refresh_analytics_once(episode_dir, run_root)
    selected = selected_annotation_run(episode_dir, annotation_run_root=run_root)

    assert first.freshness.state == FRESHNESS_READY
    assert result.action == "missing_only"
    assert result.freshness.state == FRESHNESS_READY
    assert result.summary is not None
    assert result.summary.carried_forward_count == 1
    assert result.summary.generated_count == 1
    assert result.summary.final_snapshot_count == 2
    assert selected is not None
    assert len(selected.rows) == 2


def test_explicit_stale_run_blocks_automatic_selection_change(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_episode(episode_dir, _episode("episode-20260711-1"))
    first = refresh_analytics_once(episode_dir, run_root)
    pinned = run_root / first.summary.run_id
    _write_episode(episode_dir, _episode("episode-20260711-2"))

    result = refresh_analytics_once(
        episode_dir,
        run_root,
        annotation_run_dir=pinned,
    )

    assert result.action == "blocked"
    assert result.freshness.state == FRESHNESS_BLOCKED
    assert result.freshness.blocker == "explicit_annotation_run_is_pinned"
    assert len(tuple(run_root.glob("run-*"))) == 1


def test_startup_recovery_discovers_pending_episode(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    journal_path = tmp_path / "journal.jsonl"
    episode_dir.mkdir()
    _write_episode(episode_dir, _episode("episode-20260711-1"))
    coordinator = AnalyticsRefreshCoordinator(
        episode_dir,
        run_root,
        journal_log=journal_path,
    )

    async def scenario():
        startup = await coordinator.start()
        final = await coordinator.wait_idle()
        return startup, final

    startup, final = asyncio.run(scenario())

    assert startup.state == FRESHNESS_STALE
    assert final.state == FRESHNESS_READY
    events = _read_jsonl(journal_path)
    assert any(event["event_type"] == "analytics_refresh.queued" for event in events)
    assert any(event["event_type"] == "analytics_refresh.published" for event in events)


def test_simultaneous_enqueues_coalesce_to_one_snapshot(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_episode(episode_dir, _episode("episode-20260711-1"))
    _write_episode(episode_dir, _episode("episode-20260711-2"))
    coordinator = AnalyticsRefreshCoordinator(episode_dir, run_root)

    async def scenario():
        await asyncio.gather(
            coordinator.enqueue("episode-20260711-1"),
            coordinator.enqueue("episode-20260711-2"),
        )
        return await coordinator.wait_idle()

    final = asyncio.run(scenario())

    assert final.state == FRESHNESS_READY
    assert final.observed_count == 2
    assert len(tuple(run_root.glob("run-*"))) == 1


def test_invalid_episode_blocks_without_content_in_journal(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    journal_path = tmp_path / "journal.jsonl"
    episode_dir.mkdir()
    (episode_dir / "episode-20260711-1.json").write_text(
        '{"id": "episode-20260711-1", "observed": "private words"}',
        encoding="utf-8",
    )
    coordinator = AnalyticsRefreshCoordinator(
        episode_dir,
        run_root,
        journal_log=journal_path,
    )

    async def scenario():
        await coordinator.start()
        return await coordinator.wait_idle()

    status = asyncio.run(scenario())

    assert status.state == FRESHNESS_BLOCKED
    rendered = journal_path.read_text(encoding="utf-8")
    assert "annotation_refresh_failed" in rendered
    assert "private words" not in rendered


def test_refresh_failure_preserves_last_valid_run(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_episode(episode_dir, _episode("episode-20260711-1"))
    first = refresh_analytics_once(episode_dir, run_root)
    invalid = _episode("episode-20260711-2")
    invalid["observed"] = "private invalid material"
    _write_episode(episode_dir, invalid)

    result = refresh_analytics_once(episode_dir, run_root)
    selected = selected_annotation_run(episode_dir, annotation_run_root=run_root)

    assert result.freshness.state == FRESHNESS_BLOCKED
    assert result.freshness.blocker == "annotation_refresh_failed"
    assert selected is not None
    assert selected.manifest.annotation_run_id == first.summary.run_id
    assert len(tuple(run_root.glob("run-*"))) == 1


def _episode(episode_id):
    return {
        "id": episode_id,
        "date": "2026-07-11",
        "source": "telegram-chat:123",
        "observed": {
            "situation": {"value": "ситуация", "source_quote": "ситуация"},
            "trigger": {"value": "сообщение", "source_quote": "сообщение"},
            "actor": {"value": "человек", "source_quote": "человек"},
            "quote": {"value": "фраза", "source_quote": "фраза"},
            "automatic_thought": {"value": "мысль", "source_quote": "мысль"},
            "emotion": {"value": "страх", "source_quote": "страх"},
            "behavior": {"value": "ответил", "source_quote": "ответил"},
            "physical": {"value": "напряжение", "source_quote": "напряжение"},
            "short_term_consequence": {"value": "легче", "source_quote": "легче"},
            "long_term_consequence": {"value": "завершил", "source_quote": "завершил"},
        },
    }


def _write_episode(episode_dir, episode):
    (episode_dir / f"{episode['id']}.json").write_text(
        json.dumps(episode, ensure_ascii=False),
        encoding="utf-8",
    )


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

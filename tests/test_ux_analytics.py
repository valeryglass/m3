from datetime import datetime, timezone

from app.ux_analytics import summarize_events
from app.ux_events import base_event


def test_summarize_events_counts_completion_retries_and_lengths():
    events = [
        base_event(
            "session_started",
            "session-1",
            "123",
            created_at=_dt(12, 0),
        ),
        base_event(
            "step_prompted",
            "session-1",
            "123",
            created_at=_dt(12, 0),
            target="episode_date",
            target_index=0,
        ),
        base_event(
            "step_answered",
            "session-1",
            "123",
            created_at=_dt(12, 1),
            target="episode_date",
            target_index=0,
            duration_sec=60,
            advanced=False,
            answer_chars=3,
        ),
        base_event(
            "step_prompted",
            "session-1",
            "123",
            created_at=_dt(12, 1),
            target="episode_date",
            target_index=0,
        ),
        base_event(
            "step_answered",
            "session-1",
            "123",
            created_at=_dt(12, 2),
            target="episode_date",
            target_index=0,
            duration_sec=60,
            advanced=True,
            answer_chars=10,
        ),
        base_event(
            "session_completed",
            "session-1",
            "123",
            created_at=_dt(12, 10),
        ),
    ]

    summary = summarize_events(events, now=_dt(12, 11), idle_after_sec=7200)

    assert summary["sessions_started"] == 1
    assert summary["sessions_completed"] == 1
    assert summary["completion_rate"] == 1.0
    assert summary["avg_session_duration_sec"] == 600.0
    assert summary["retry_count_by_target"] == {"episode_date": 1}
    assert summary["answer_chars_avg_by_target"] == {"episode_date": 6.5}
    assert summary["steps_prompted_by_target"] == {"episode_date": 2}
    assert summary["steps_answered_by_target"] == {"episode_date": 2}


def test_summarize_events_counts_cancel_and_idle_deadends():
    events = [
        base_event("session_started", "session-1", "123", created_at=_dt(9, 0)),
        base_event(
            "step_prompted",
            "session-1",
            "123",
            created_at=_dt(9, 0),
            target="situation",
            target_index=1,
        ),
        base_event(
            "session_cancelled",
            "session-1",
            "123",
            created_at=_dt(9, 5),
            target="situation",
            target_index=1,
        ),
        base_event("session_started", "session-2", "456", created_at=_dt(10, 0)),
        base_event(
            "step_prompted",
            "session-2",
            "456",
            created_at=_dt(10, 0),
            target="behavior",
            target_index=2,
        ),
    ]

    summary = summarize_events(events, now=_dt(13, 0), idle_after_sec=7200)

    assert summary["sessions_started"] == 2
    assert summary["sessions_cancelled"] == 1
    assert summary["cancel_deadends_by_target"] == {"situation": 1}
    assert summary["idle_deadends_by_target"] == {"behavior": 1}
    assert summary["abandoned_count"] == 1
    assert summary["sessions_per_user"] == {"123": 1, "456": 1}
    assert summary["repeat_users"] == 0


def _dt(hour: int, minute: int) -> datetime:
    return datetime(2026, 5, 1, hour, minute, tzinfo=timezone.utc)

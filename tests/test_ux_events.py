from datetime import datetime, timezone

from app.ux_events import UxEventLog, base_event, new_session_id, telegram_event


def test_ux_event_log_appends_and_reads_jsonl(tmp_path):
    log = UxEventLog(tmp_path / "events.jsonl")
    event = base_event(
        "step_answered",
        "session-1",
        "123",
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        target="situation",
        target_index=1,
        duration_sec=10,
        advanced=True,
        answer_chars=42,
    )

    log.append(event)

    assert log.read() == [event]


def test_new_session_id_uses_user_and_timestamp():
    session_id = new_session_id(
        "123", datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    )

    assert session_id == "session-123-20260501T120000Z"


def test_telegram_event_stores_safe_metadata_only():
    event = telegram_event(
        "unauthorized_attempt",
        "456",
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        chat_id=456,
        message_kind="command",
        command="/start",
    )

    assert event == {
        "chat_id": 456,
        "command": "/start",
        "created_at": "2026-05-01T12:00:00Z",
        "event_type": "unauthorized_attempt",
        "message_kind": "command",
        "user_id": "456",
    }

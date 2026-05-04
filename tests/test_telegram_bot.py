import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import app.telegram_bot as telegram_bot
from app.loop_extractor import LoopSession
from app.storage import JsonStorage
from app.tone_engine import ToneEngine
from app.ux_events import UxEventLog, format_utc


def test_telegram_bot_module_imports_without_contacting_telegram():
    assert callable(telegram_bot.main)


def test_authorize_logs_unauthorized_attempt_without_session(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/start")
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=456),
        effective_user=SimpleNamespace(id=456),
        message=message,
    )
    settings = SimpleNamespace(telegram_allowed_chat_ids=frozenset({123}))

    authorized = _run(telegram_bot._authorize(update, settings, ToneEngine.default(), ux_events))

    assert authorized is False
    assert message.replies == ["Нет доступа."]
    assert storage.load_session(456) is None
    events = ux_events.read()
    assert len(events) == 2
    assert events[0]["created_at"] == events[1]["created_at"]
    assert events[0] == {
        "chat_id": 456,
        "command": "/start",
        "created_at": events[0]["created_at"],
        "event_type": "update_received",
        "message_kind": "command",
        "user_id": "456",
    }
    assert events[1] == {
        "chat_id": 456,
        "command": "/start",
        "created_at": events[1]["created_at"],
        "event_type": "unauthorized_attempt",
        "message_kind": "command",
        "user_id": "456",
    }


def test_stale_initial_session_expires_and_logs_reason(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    now = datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc)
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=0,
        episode_date="2026-05-02",
        last_prompted_at=format_utc(now - timedelta(seconds=601)),
    )
    storage.save_session(session)

    expired = telegram_bot._expire_initial_session_if_stale(
        storage, ux_events, session, 123, now, 600
    )

    assert expired is True
    assert storage.load_session(123) is None
    assert ux_events.read() == [
        {
            "cancel_reason": "initial_session_expired",
            "created_at": "2026-05-02T12:00:00Z",
            "event_type": "session_cancelled",
            "session_id": "session-123",
            "target": "situation",
            "target_index": 0,
            "user_id": "123",
        }
    ]


def test_non_initial_stale_session_does_not_expire(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    now = datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc)
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=1,
        episode_date="2026-05-02",
        last_prompted_at=format_utc(now - timedelta(seconds=3600)),
    )
    storage.save_session(session)

    expired = telegram_bot._expire_initial_session_if_stale(
        storage, ux_events, session, 123, now, 600
    )

    assert expired is False
    assert storage.load_session(123) is not None
    assert ux_events.read() == []


def test_expired_session_reply_comes_from_tone_engine():
    tone = ToneEngine.default()

    assert telegram_bot._expired_initial_session_text(tone) == (
        "Прошлая сессия истекла до первого ответа. Отправь /start заново."
    )


def test_new_session_uses_creation_date():
    now = datetime(2026, 5, 3, 9, 44, tzinfo=timezone.utc)

    session = telegram_bot._new_session_for_now(123, now)

    assert session.episode_date == telegram_bot._episode_date_for_now(now)
    assert session.target_index == 0


def test_start_new_session_prompts_without_observed_answer(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    now = datetime(2026, 5, 3, 9, 44, tzinfo=timezone.utc)

    session = telegram_bot._start_new_session(storage, ux_events, 123, now)
    loaded = storage.load_session(123)

    assert loaded is not None
    assert session.target_index == 0
    assert loaded.target_index == 0
    assert loaded.observed == {}
    assert ux_events.read() == [
        {
            "created_at": "2026-05-03T09:44:00Z",
            "event_type": "session_started",
            "session_id": session.session_id,
            "user_id": "123",
        },
        {
            "created_at": "2026-05-03T09:44:00Z",
            "event_type": "step_prompted",
            "session_id": session.session_id,
            "target": "situation",
            "target_index": 0,
            "user_id": "123",
        },
    ]


def test_ensure_episode_date_fills_legacy_session():
    now = datetime(2026, 5, 3, 9, 44, tzinfo=timezone.utc)
    session = LoopSession(chat_id=123, episode_date=None)

    telegram_bot._ensure_episode_date(session, now)

    assert session.episode_date == telegram_bot._episode_date_for_now(now)


def test_restart_cancel_event_uses_current_target():
    now = datetime(2026, 5, 3, 9, 44, tzinfo=timezone.utc)
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=1,
        episode_date="2026-05-03",
        observed={"situation": {"value": "s", "source_quote": "s"}},
    )

    event = telegram_bot._session_cancelled_event(
        session,
        "123",
        now=now,
        cancel_reason="restart",
    )

    assert event["event_type"] == "session_cancelled"
    assert event["cancel_reason"] == "restart"
    assert event["target"] == "behavior"


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.replies = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


def _run(coro):
    return asyncio.run(coro)

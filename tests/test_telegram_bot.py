from datetime import datetime, timedelta, timezone

import app.telegram_bot as telegram_bot
from app.loop_extractor import LoopSession
from app.storage import JsonStorage
from app.tone_engine import ToneEngine
from app.ux_events import UxEventLog, format_utc


def test_telegram_bot_module_imports_without_contacting_telegram():
    assert callable(telegram_bot.main)


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


def test_ensure_episode_date_fills_legacy_session():
    now = datetime(2026, 5, 3, 9, 44, tzinfo=timezone.utc)
    session = LoopSession(chat_id=123, episode_date=None)

    telegram_bot._ensure_episode_date(session, now)

    assert session.episode_date == telegram_bot._episode_date_for_now(now)

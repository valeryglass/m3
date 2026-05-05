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


def test_visible_command_menu_excludes_hidden_status():
    tone = ToneEngine.default()

    assert telegram_bot.REGISTERED_COMMANDS == ("start", "status", "cancel", "help")
    assert telegram_bot._visible_command_menu(tone) == (
        {"command": "start", "description": "Начать новый эпизод"},
        {"command": "cancel", "description": "Отменить сессию"},
        {"command": "help", "description": "Показать команды"},
    )


def test_bot_profile_uses_tone_engine_copy():
    tone = ToneEngine.default()

    assert telegram_bot._bot_profile(tone) == {
        "short_description": "Собирает один CBT-эпизод короткими вопросами.",
        "description": (
            "Бот помогает зафиксировать один конкретный эпизод: что произошло, "
            "что ты сделал, что было потом, какая мысль мелькнула, эмоция и тело. "
            "Начни с /start."
        ),
    }


def test_send_help_replies_without_creating_session(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    message = _FakeMessage("/help")
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=123),
        message=message,
    )

    _run(telegram_bot._send_help(update, ToneEngine.default()))

    assert storage.load_session(123) is None
    assert message.replies == [
        "Команды:\n"
        "/start — начать новый эпизод\n"
        "/cancel — отменить сессию\n"
        "/help — показать команды"
    ]


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


def test_plain_text_without_session_requires_start(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("hi")
    update = _fake_update(123, message)

    _run(
        telegram_bot._handle_message_after_authorized(
            update, storage, ux_events, _settings(), ToneEngine.default()
        )
    )

    assert storage.load_session(123) is None
    assert ux_events.read() == []
    assert message.replies == [
        "Активной сессии нет. Отправь /start, чтобы начать.",
    ]


def test_cancel_without_session_reports_no_active_session(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/cancel")
    update = _fake_update(123, message)

    _run(
        telegram_bot._handle_cancel_after_authorized(
            update, storage, ux_events, _settings(), ToneEngine.default()
        )
    )

    assert storage.load_session(123) is None
    assert ux_events.read() == []
    assert message.replies == ["Активной сессии нет."]


def test_accepted_answer_replies_with_bridge_and_next_question(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=0,
        episode_date="2026-05-03",
    )
    storage.save_session(session)
    message = _FakeMessage("situation")

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            storage,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = storage.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 1
    assert message.replies == [
        "Записал. 1/7\n\nЧто ты сделал или чего избежал?",
    ]


def test_empty_answer_retries_without_bridge(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=0,
        episode_date="2026-05-03",
    )
    storage.save_session(session)
    message = _FakeMessage(" ")

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            storage,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = storage.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 0
    assert message.replies == [
        "Нужен непустой ответ.\n\nЧто произошло конкретно? 1-2 предложения.",
    ]
    assert "Записал." not in message.replies[0]


def test_completion_reply_has_no_episode_path_and_requires_restart_after(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=6,
        episode_date="2026-05-03",
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "behavior": {"value": "b", "source_quote": "b"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {"value": "e", "source_quote": "e"},
        },
    )
    storage.save_session(session)
    message = _FakeMessage("body")
    update = _fake_update(123, message)

    _run(
        telegram_bot._handle_message_after_authorized(
            update, storage, ux_events, _settings(), ToneEngine.default()
        )
    )

    assert storage.load_session(123) is None
    assert [path.name for path in (tmp_path / "episodes").glob("*.json")] == [
        "episode-20260503-1.json"
    ]
    assert message.replies == ["Готово. Эпизод собран."]
    assert "data/episodes" not in message.replies[0]
    assert ux_events.read()[-1]["event_type"] == "session_completed"

    followup = _FakeMessage("next")
    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, followup),
            storage,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    assert storage.load_session(123) is None
    assert followup.replies == ["Активной сессии нет. Отправь /start, чтобы начать."]


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


def _fake_update(chat_id: int, message: _FakeMessage):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(id=chat_id),
        message=message,
    )


def _settings():
    return SimpleNamespace(initial_session_ttl_sec=600)

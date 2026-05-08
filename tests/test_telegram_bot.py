import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import app.telegram_bot as telegram_bot
from app.loop_extractor import LoopSession, prompt_for_current_target
from app.storage import JsonStorage
from app.tone_engine import ToneEngine
from app.userlist import APPROVED, PAUSED, WAITLISTED, JsonUserList
from app.ux_events import UxEventLog, format_utc


def test_telegram_bot_module_imports_without_contacting_telegram():
    assert callable(telegram_bot.main)


def test_visible_command_menu_excludes_hidden_status():
    tone = ToneEngine.default()

    assert telegram_bot.REGISTERED_COMMANDS == (
        "start",
        "status",
        "cancel",
        "help",
        "approve",
        "pause",
    )
    assert telegram_bot._visible_command_menu(tone) == (
        {"command": "start", "description": "Начать новый эпизод"},
        {"command": "cancel", "description": "Отменить сессию"},
        {"command": "help", "description": "Показать команды"},
    )


def test_bot_profile_uses_tone_engine_copy():
    tone = ToneEngine.default()

    assert telegram_bot._bot_profile(tone) == {
        "short_description": "МИШа собирает один CBT/ACT-эпизод короткими вопросами",
        "description": (
            "МИШа — машина извлечения шаблонов\n\n"
            "Помогает собрать один конкретный эпизод: факт, действие, последствия, "
            "мысль, эмоцию и тело\n\n"
            "Начни с /start"
        ),
    }


def test_start_session_reply_uses_rich_first_card():
    tone = ToneEngine.default()
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=0,
        episode_date="2026-05-03",
    )

    assert tone.start_session(prompt_for_current_target(session, tone)) == (
        "Соберём один конкретный эпизод. Идём коротко, не спеша, по фактам\n\n"
        "💾 □□□□□□□ 0/7\n\n"
        f"{tone.target_prompt('situation')}"
    )


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
        "МИШа\n"
        "машина извлечения шаблонов\n"
        "(аналитическая)\n\n"
        "Бот не ставит диагнозы и не даёт советов\n"
        "Он помогает аккуратно зафиксировать один эпизод по CBT/ACT-фрейму\n\n"
        "Команды:\n"
        "/start — начать один эпизод\n"
        "/cancel — отменить сессию\n"
        "/help — показать команды\n\n"
        "Связь: @mesto3"
    ]
    assert message.reply_options == [{"parse_mode": "HTML"}]


def test_authorize_logs_unauthorized_attempt_without_session(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/start")
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=456),
        effective_user=SimpleNamespace(id=456),
        message=message,
    )
    settings = _settings(allowed_chat_ids=frozenset({123}), admin_chat_id=123)
    userlist = JsonUserList(tmp_path / "userlist" / "users.json")
    bot = _FakeBot()

    authorized = _run(
        telegram_bot._authorize(
            update, settings, ToneEngine.default(), ux_events, userlist, bot
        )
    )

    assert authorized is False
    assert message.replies == [
        "Спасибо за интерес. Мы добавили тебя в waitlist. "
        "Напишем, когда доступ будет одобрен"
    ]
    assert storage.load_session(456) is None
    assert userlist.load()["456"]["status"] == WAITLISTED
    assert bot.messages == [
        {
            "chat_id": 123,
            "text": (
                "Новый пользователь в waitlist\n"
                "chat_id: 456\n"
                "user_id: 456\n\n"
                "/approve 456\n"
                "/pause 456"
            ),
            "parse_mode": "HTML",
        }
    ]
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


def test_authorize_repeated_waitlist_attempt_does_not_notify_admin(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(allowed_chat_ids=frozenset({123}), admin_chat_id=123)
    userlist = JsonUserList(tmp_path / "userlist" / "users.json")
    userlist.upsert_waitlisted(
        456, "456", now=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc)
    )
    bot = _FakeBot()
    message = _FakeMessage("/start")

    authorized = _run(
        telegram_bot._authorize(
            _fake_update(456, message),
            settings,
            ToneEngine.default(),
            ux_events,
            userlist,
            bot,
        )
    )

    assert authorized is False
    assert bot.messages == []
    assert userlist.load()["456"]["status"] == WAITLISTED


def test_authorize_paused_user_gets_waitlist_copy(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(allowed_chat_ids=frozenset({123}), admin_chat_id=123)
    userlist = JsonUserList(tmp_path / "userlist" / "users.json")
    userlist.pause(
        456,
        decided_by="123",
        now=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
    )
    message = _FakeMessage("/start")

    authorized = _run(
        telegram_bot._authorize(
            _fake_update(456, message),
            settings,
            ToneEngine.default(),
            ux_events,
            userlist,
            _FakeBot(),
        )
    )

    assert authorized is False
    assert userlist.load()["456"]["status"] == PAUSED
    assert message.replies == [
        "Спасибо за интерес. Мы добавили тебя в waitlist. "
        "Напишем, когда доступ будет одобрен"
    ]


def test_authorize_approved_user_passes(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(allowed_chat_ids=frozenset({123}), admin_chat_id=123)
    userlist = JsonUserList(tmp_path / "userlist" / "users.json")
    userlist.approve(
        456,
        decided_by="123",
        now=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
    )
    message = _FakeMessage("/start")

    authorized = _run(
        telegram_bot._authorize(
            _fake_update(456, message),
            settings,
            ToneEngine.default(),
            ux_events,
            userlist,
            _FakeBot(),
        )
    )

    assert authorized is True
    assert message.replies == []
    assert userlist.load()["456"]["status"] == APPROVED


def test_authorize_open_mvp_does_not_use_waitlist(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(allowed_chat_ids=frozenset(), admin_chat_id=None)
    userlist = JsonUserList(tmp_path / "userlist" / "users.json")

    authorized = _run(
        telegram_bot._authorize(
            _fake_update(456, _FakeMessage("/start")),
            settings,
            ToneEngine.default(),
            ux_events,
            userlist,
            _FakeBot(),
        )
    )

    assert authorized is True
    assert userlist.load() == {}


def test_admin_approve_updates_userlist_without_user_notification(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(allowed_chat_ids=frozenset({123}), admin_chat_id=123)
    userlist = JsonUserList(tmp_path / "userlist" / "users.json")
    message = _FakeMessage("/approve 456")

    _run(
        telegram_bot._handle_admin_decision(
            _fake_update(123, message),
            ["456"],
            settings,
            ToneEngine.default(),
            ux_events,
            userlist,
            "approve",
        )
    )

    assert userlist.load()["456"]["status"] == APPROVED
    assert message.replies == ["Доступ одобрен для 456"]


def test_admin_pause_updates_userlist_without_user_notification(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(allowed_chat_ids=frozenset({123}), admin_chat_id=123)
    userlist = JsonUserList(tmp_path / "userlist" / "users.json")
    message = _FakeMessage("/pause 456")

    _run(
        telegram_bot._handle_admin_decision(
            _fake_update(123, message),
            ["456"],
            settings,
            ToneEngine.default(),
            ux_events,
            userlist,
            "pause",
        )
    )

    assert userlist.load()["456"]["status"] == PAUSED
    assert message.replies == ["Заявка поставлена на паузу для 456"]


def test_non_admin_decision_command_is_rejected(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(allowed_chat_ids=frozenset({123}), admin_chat_id=123)
    userlist = JsonUserList(tmp_path / "userlist" / "users.json")
    message = _FakeMessage("/approve 456")

    _run(
        telegram_bot._handle_admin_decision(
            _fake_update(456, message),
            ["456"],
            settings,
            ToneEngine.default(),
            ux_events,
            userlist,
            "approve",
        )
    )

    assert userlist.load() == {}
    assert message.replies == ["Нет доступа"]


def test_admin_decision_requires_chat_id(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(allowed_chat_ids=frozenset({123}), admin_chat_id=123)
    userlist = JsonUserList(tmp_path / "userlist" / "users.json")
    message = _FakeMessage("/approve")

    _run(
        telegram_bot._handle_admin_decision(
            _fake_update(123, message),
            [],
            settings,
            ToneEngine.default(),
            ux_events,
            userlist,
            "approve",
        )
    )

    assert userlist.load() == {}
    assert message.replies == ["Используй /approve &lt;chat_id&gt;"]


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
        "Сейчас активной сессии нет. Отправь /start, чтобы начать новый эпизод",
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
    assert message.replies == ["Активной сессии нет"]


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
        f"💾 ■□□□□□□ 1/7\n\n"
        f"{ToneEngine.default().target_prompt('behavior')}",
    ]
    assert message.reply_options == [{"parse_mode": "HTML"}]


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
        f"Нужен непустой ответ\n\n{ToneEngine.default().target_prompt('situation')}",
    ]
    assert "💾" not in message.replies[0]


def test_final_answer_opens_save_review_without_saving(tmp_path):
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

    loaded = storage.load_session(123)
    assert loaded is not None
    assert loaded.awaiting_save_confirmation is True
    assert loaded.target_index == 7
    assert [path.name for path in (tmp_path / "episodes").glob("*.json")] == []
    assert message.replies == [
        "💯 ■■■■■■■ 7/7\n\n"
        "ситуация: s\n"
        "действие: b\n"
        "сразу после: st\n"
        "потом: lt\n"
        "мысль: at\n"
        "эмоция: e\n"
        "тело: body\n\n"
        "Сохраняем?"
    ]
    assert message.reply_options[0]["reply_markup"] is not None
    assert ux_events.read()[-1]["event_type"] == "step_answered"

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

    loaded = storage.load_session(123)
    assert loaded is not None
    assert loaded.observed["body"]["value"] == "body"
    assert followup.replies[0].endswith("Сохраняем?")


def test_save_callback_writes_episode_and_replies_completion(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = _complete_review_session()
    storage.save_session(session)
    callback = _FakeCallbackQuery("episode:save")

    _run(
        telegram_bot._handle_episode_callback_after_authorized(
            _fake_callback_update(123, callback),
            storage,
            ux_events,
            ToneEngine.default(),
        )
    )

    assert callback.answered is True
    assert storage.load_session(123) is None
    assert [path.name for path in (tmp_path / "episodes").glob("*.json")] == [
        "episode-20260503-1.json"
    ]
    assert callback.message.replies == ["Готово. Эпизод собран"]
    assert callback.message.reply_options == [{"parse_mode": "HTML"}]
    assert ux_events.read()[-1]["event_type"] == "session_completed"


def test_cancel_callback_discards_review_session(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = _complete_review_session()
    storage.save_session(session)
    callback = _FakeCallbackQuery("episode:cancel")

    _run(
        telegram_bot._handle_episode_callback_after_authorized(
            _fake_callback_update(123, callback),
            storage,
            ux_events,
            ToneEngine.default(),
        )
    )

    assert storage.load_session(123) is None
    assert [path.name for path in (tmp_path / "episodes").glob("*.json")] == []
    assert callback.message.replies == ["Сессия отменена"]
    assert ux_events.read()[-1]["cancel_reason"] == "review_cancel"


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
        "Прошлая сессия истекла до первого ответа. Отправь /start заново"
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
        self.reply_options = []

    async def reply_text(self, text: str, **kwargs) -> None:
        self.replies.append(text)
        self.reply_options.append(kwargs)


class _FakeBot:
    def __init__(self) -> None:
        self.messages = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                **kwargs,
            }
        )


class _FakeCallbackQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.answered = False
        self.message = _FakeMessage("callback")

    async def answer(self) -> None:
        self.answered = True


def _run(coro):
    return asyncio.run(coro)


def _fake_update(chat_id: int, message: _FakeMessage):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(id=chat_id),
        message=message,
    )


def _fake_callback_update(chat_id: int, callback_query: _FakeCallbackQuery):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(id=chat_id),
        message=None,
        callback_query=callback_query,
    )


def _complete_review_session() -> LoopSession:
    return LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=7,
        episode_date="2026-05-03",
        awaiting_save_confirmation=True,
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "behavior": {"value": "b", "source_quote": "b"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {"value": "e", "source_quote": "e"},
            "body": {"value": "body", "source_quote": "body"},
        },
    )


def _settings(
    allowed_chat_ids=frozenset({123}),
    admin_chat_id=123,
):
    return SimpleNamespace(
        initial_session_ttl_sec=600,
        telegram_allowed_chat_ids=allowed_chat_ids,
        telegram_admin_chat_id=admin_chat_id,
    )

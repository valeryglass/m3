import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import app.telegram_bot as telegram_bot
from app.loop_extractor import LoopSession, prompt_for_current_target
from app.session_store import LoopSessionStore
from app.storage import JsonStorage
from app.tone_engine import ToneEngine
from app.userlist import APPROVED, PAUSED, WAITLISTED, JsonUserList
from app.input_funnels import voice_input_artifact
from app.ux_events import UxEventLog, format_utc


INTERNAL_PROFILE_TERMS = (
    "payload",
    "graph_ready",
    "profile_eligible",
    "annotation",
    "signature",
)


def test_telegram_bot_module_imports_without_contacting_telegram():
    assert callable(telegram_bot.main)


def test_visible_command_menu_excludes_hidden_status():
    tone = ToneEngine.default()

    assert telegram_bot.REGISTERED_COMMANDS == (
        "start",
        "status",
        "cancel",
        "help",
        "profile",
        "capture",
        "capture3",
        "approve",
        "pause",
        "report_graph",
        "report_ux",
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
            "МИШа — машина извлечения шаблонов аналитическая\n\n"
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
        "□□□□□□□□□□ 0/10\n\n"
        f"{tone.target_prompt('situation')}"
    )


def test_second_admin_is_authorized_for_hidden_commands(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/approve 456")

    authorized = _run(
        telegram_bot._authorize_admin(
            _fake_update(327002663, message),
            _settings(
                admin_chat_ids=frozenset({225672, 327002663}),
                owner_chat_id=225672,
            ),
            ToneEngine.default(),
            ux_events,
        )
    )

    assert authorized is True
    assert message.replies == []


def test_send_help_replies_without_creating_session(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    message = _FakeMessage("/help")
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=123),
        message=message,
    )

    _run(telegram_bot._send_help(update, ToneEngine.default()))

    assert session_store.load_session(123) is None
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


def test_profile_command_replies_with_current_report(tmp_path):
    settings = _settings(episode_dir=tmp_path / "episodes")
    settings.episode_dir.mkdir(parents=True)
    _write_json(settings.episode_dir / "episode-20260503-1.json", _graph_ready_episode())
    message = _FakeMessage("/profile")

    _run(
        telegram_bot._handle_profile_after_authorized(
            _fake_update(123, message),
            settings,
            ToneEngine.default(),
        )
    )

    assert len(message.replies) == 1
    assert message.replies[0].startswith("Короткий отчет")
    assert "В выборке: 1 эпизод" in message.replies[0]
    assert "контакт с людьми" in message.replies[0]
    assert "дистанцироваться" in message.replies[0]
    _assert_no_internal_profile_terms(message.replies[0])
    assert "parse_mode" not in message.reply_options[0]
    reply_markup = message.reply_options[0]["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].text == "Подробнее"
    assert reply_markup.inline_keyboard[0][0].callback_data == "profile:details"


def test_profile_command_uses_latest_annotation_run(tmp_path):
    annotation_run_root = tmp_path / "annotation-runs"
    run_dir = annotation_run_root / "run-20260605"
    settings = _settings(
        episode_dir=tmp_path / "episodes",
        annotation_run_root=annotation_run_root,
    )
    settings.episode_dir.mkdir(parents=True)
    episode = _graph_ready_episode()
    derived = episode.pop("derived")
    _write_json(settings.episode_dir / "episode-20260503-1.json", episode)
    pending = _graph_ready_episode()
    pending["id"] = "episode-20260503-2"
    pending.pop("derived")
    _write_json(settings.episode_dir / "episode-20260503-2.json", pending)
    _write_annotation_run(
        run_dir,
        {"episode_id": "episode-20260503-1", "derived": derived},
    )
    message = _FakeMessage("/profile")

    _run(
        telegram_bot._handle_profile_after_authorized(
            _fake_update(123, message),
            settings,
            ToneEngine.default(),
        )
    )

    assert len(message.replies) == 1
    assert message.replies[0].startswith("Короткий отчет")
    assert "В выборке: 2 эпизода" in message.replies[0]
    assert "Учтено 1 из 2 эпизодов; 1 ждут обработки." in message.replies[0]


def test_profile_details_callback_sends_detailed_report(tmp_path):
    settings = _settings(episode_dir=tmp_path / "episodes")
    settings.episode_dir.mkdir(parents=True)
    _write_json(settings.episode_dir / "episode-20260503-1.json", _graph_ready_episode())
    callback = _FakeCallbackQuery("profile:details")

    _run(
        telegram_bot._handle_profile_callback_after_authorized(
            _fake_callback_update(123, callback),
            settings,
            ToneEngine.default(),
        )
    )

    assert callback.answered is True
    assert callback.edits == []
    assert len(callback.message.replies) == 1
    assert callback.message.replies[0].startswith("Подробный отчет")
    _assert_no_internal_profile_terms(callback.message.replies[0])
    assert callback.message.reply_options == [{}]


def test_profile_command_reports_missing_profile(tmp_path):
    settings = _settings(episode_dir=tmp_path / "episodes")
    settings.episode_dir.mkdir(parents=True)
    episode = _graph_ready_episode()
    episode["derived"] = {
        "nodes": [],
        "trigger_annotations": [],
        "actor_annotations": [],
        "cognition_annotations": [],
        "emotion_annotations": [],
        "behavior_annotations": [],
        "outcome_annotations": [],
        "relations": [],
    }
    _write_json(settings.episode_dir / "episode-20260503-1.json", episode)
    message = _FakeMessage("/profile")

    _run(
        telegram_bot._handle_profile_after_authorized(
            _fake_update(123, message),
            settings,
            ToneEngine.default(),
        )
    )

    assert message.replies == [
        "Профиль пока не собран. Нужны сохранённые и обработанные эпизоды."
    ]
    assert message.reply_options == [{"parse_mode": "HTML"}]


def test_authorize_logs_unauthorized_attempt_without_session(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/start")
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=456),
        effective_user=SimpleNamespace(
            id=456,
            username="tester",
            first_name="Test",
            last_name="User",
            language_code="en",
            is_bot=False,
        ),
        message=message,
    )
    settings = _settings(admin_chat_ids=frozenset({123}), owner_chat_id=123)
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
        "Напишем, как только доступ откроется"
    ]
    assert session_store.load_session(456) is None
    assert userlist.load()["456"]["status"] == WAITLISTED
    assert userlist.load()["456"]["username"] == "tester"
    assert userlist.load()["456"]["first_name"] == "Test"
    assert userlist.load()["456"]["last_name"] == "User"
    assert userlist.load()["456"]["language_code"] == "en"
    assert bot.messages == [
        {
            "chat_id": 123,
            "text": (
                "Новый пользователь в waitlist\n"
                "chat_id: 456\n"
                "user_id: 456\n"
                "username: tester\n"
                "first_name: Test\n"
                "last_name: User\n"
                "language_code: en\n"
                "is_bot: False\n\n"
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
    settings = _settings(admin_chat_ids=frozenset({123}), owner_chat_id=123)
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
    settings = _settings(admin_chat_ids=frozenset({123}), owner_chat_id=123)
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
        "Напишем, как только доступ откроется"
    ]


def test_authorize_approved_user_passes(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(admin_chat_ids=frozenset({123}), owner_chat_id=123)
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


def test_authorize_empty_config_still_uses_waitlist(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(admin_chat_ids=frozenset(), owner_chat_id=None)
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

    assert authorized is False
    assert userlist.load()["456"]["status"] == WAITLISTED


def test_admin_approve_updates_userlist_and_notifies_user(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(admin_chat_ids=frozenset({123}), owner_chat_id=123)
    userlist = JsonUserList(tmp_path / "userlist" / "users.json")
    message = _FakeMessage("/approve 456")
    bot = _FakeBot()

    _run(
        telegram_bot._handle_admin_decision(
            _fake_update(123, message),
            ["456"],
            settings,
            ToneEngine.default(),
            ux_events,
            userlist,
            "approve",
            bot,
        )
    )

    assert userlist.load()["456"]["status"] == APPROVED
    assert message.replies == ["Доступ одобрен для 456"]
    assert bot.messages == [
        {
            "chat_id": 456,
            "text": "Доступ открыт. Отправь /start, чтобы начать.",
            "parse_mode": "HTML",
        }
    ]


def test_admin_pause_updates_userlist_without_user_notification(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(admin_chat_ids=frozenset({123}), owner_chat_id=123)
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
    settings = _settings(admin_chat_ids=frozenset({123}), owner_chat_id=123)
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


def test_report_graph_rejects_non_admin(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/report_graph")

    authorized = _run(
        telegram_bot._authorize_admin(
            _fake_update(456, message),
            _settings(admin_chat_ids=frozenset({123}), owner_chat_id=123),
            ToneEngine.default(),
            ux_events,
        )
    )

    assert authorized is False
    assert message.replies == ["Нет доступа"]


def test_report_graph_builds_summary_without_writing_reports(tmp_path):
    settings = _settings(
        episode_dir=tmp_path / "episodes",
    )
    settings.episode_dir.mkdir(parents=True)
    _write_json(settings.episode_dir / "episode-20260503-1.json", _graph_ready_episode())
    message = _FakeMessage("/report_graph")

    _run(
        telegram_bot._handle_report_graph_after_admin(
            _fake_update(123, message),
            settings,
            ToneEngine.default(),
        )
    )

    assert not (tmp_path / "reports").exists()
    assert message.replies == [
        "Отчёт собран\n"
        "episodes: 1\n"
        "coverage: 1/1 annotated (full); pending: 0\n"
        "invalid: 0\n"
        "empty_derived: 0\n"
        "annotation_ready: 1\n"
        "graph_ready: 1\n"
        "report_ready: 1\n"
        "payload_eligible: 1"
    ]


def test_report_ux_rejects_non_admin(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/report_ux")

    authorized = _run(
        telegram_bot._authorize_admin(
            _fake_update(456, message),
            _settings(admin_chat_ids=frozenset({123}), owner_chat_id=123),
            ToneEngine.default(),
            ux_events,
        )
    )

    assert authorized is False
    assert message.replies == ["Нет доступа"]


def test_report_ux_regenerates_and_replies_markdown(tmp_path):
    settings = _settings(
        ux_event_log=tmp_path / "ux-events" / "events.jsonl",
        userlist_path=tmp_path / "userlist" / "users.json",
    )
    JsonUserList(settings.userlist_path).upsert_waitlisted(
        123,
        "123",
        now=datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc),
        profile={"username": "tester"},
    )
    UxEventLog(settings.ux_event_log).append(
        {
            "event_type": "session_started",
            "session_id": "session-123",
            "user_id": "123",
            "created_at": "2026-05-07T10:00:00Z",
        }
    )
    message = _FakeMessage("/report_ux")

    _run(
        telegram_bot._handle_report_ux_after_admin(
            _fake_update(123, message),
            settings,
            ToneEngine.default(),
        )
    )

    assert not (tmp_path / "reports").exists()
    assert message.replies[0].startswith("# UX Analytics\n")
    assert "- 123 (@tester): 1" in message.replies[0]
    assert message.reply_options == [{}]


def test_admin_decision_requires_chat_id(tmp_path):
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    settings = _settings(admin_chat_ids=frozenset({123}), owner_chat_id=123)
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


def test_plain_text_without_session_starts_one_take_text_capture(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("коллега резко ответил в чате")
    update = _fake_update(123, message)

    _run(
        telegram_bot._handle_message_after_authorized(
            update, session_store, ux_events, _settings(), ToneEngine.default()
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 1
    assert loaded.observed == {
        "situation": {
            "value": "коллега резко ответил в чате",
            "source_quote": "коллега резко ответил в чате",
        }
    }
    assert message.replies == [
        f"■□□□□□□□□□ 1/10\n\n{ToneEngine.default().target_prompt('trigger')}"
    ]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == [
        "input_received",
        "draft_created",
        "session_started",
        "step_answered",
        "step_prompted",
        "gap_question_asked",
    ]
    assert events[0]["funnel"] == "one_take_text"
    assert events[0]["media_kind"] == "text"
    assert events[1]["draft_fields"] == 1


def test_capture_command_without_text_does_not_create_session(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/capture")

    _run(
        telegram_bot._handle_capture_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    assert session_store.load_session(123) is None
    assert ux_events.read() == []
    assert message.replies == ["Используй /capture текст эпизода"]


def test_capture_command_starts_session_from_one_take_text(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/capture коллега резко ответил в чате")

    _run(
        telegram_bot._handle_capture_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 1
    assert loaded.observed == {
        "situation": {
            "value": "коллега резко ответил в чате",
            "source_quote": "коллега резко ответил в чате",
        }
    }
    assert message.replies == [
        f"■□□□□□□□□□ 1/10\n\n{ToneEngine.default().target_prompt('trigger')}"
    ]
    assert [event["event_type"] for event in ux_events.read()] == [
        "input_received",
        "draft_created",
        "session_started",
        "step_answered",
        "step_prompted",
        "gap_question_asked",
    ]


def test_capture_command_restarts_existing_session_with_cancel_event(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    existing = LoopSession(
        chat_id=123,
        session_id="session-old",
        target_index=1,
        episode_date="2026-05-03",
        observed={"situation": {"value": "old", "source_quote": "old"}},
    )
    session_store.save_session(existing)
    message = _FakeMessage("/capture новый эпизод")

    _run(
        telegram_bot._handle_capture_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.observed["situation"] == {
        "value": "новый эпизод",
        "source_quote": "новый эпизод",
    }
    events = ux_events.read()
    assert events[0]["event_type"] == "session_cancelled"
    assert events[0]["cancel_reason"] == "capture_restart"



def test_capture3_command_without_three_blocks_does_not_create_session(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/capture3 only one block")

    _run(
        telegram_bot._handle_capture3_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    assert session_store.load_session(123) is None
    assert ux_events.read() == []
    assert message.replies == [
        "Используй /capture3 что случилось | что внутри | что сделал"
    ]


def test_capture3_command_starts_session_from_three_blocks(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/capture3 факт | мысль внутри | я замолчал")

    _run(
        telegram_bot._handle_capture3_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 1
    assert loaded.observed == {
        "situation": {"value": "факт", "source_quote": "факт"},
        "automatic_thought": {
            "value": "мысль внутри",
            "source_quote": "мысль внутри",
        },
        "behavior": {"value": "я замолчал", "source_quote": "я замолчал"},
    }
    events = ux_events.read()
    assert [event["event_type"] for event in events] == [
        "input_received",
        "draft_created",
        "session_started",
        "step_answered",
        "step_prompted",
        "gap_question_asked",
    ]
    assert events[0]["funnel"] == "three_block"
    assert events[0]["media_kind"] == "three_block"
    assert events[1]["draft_fields"] == 3
    assert message.replies == [
        f"■■■□□□□□□□ 3/10\n\n{ToneEngine.default().target_prompt('trigger')}"
    ]


def test_capture3_command_restarts_existing_session_with_cancel_event(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    existing = LoopSession(
        chat_id=123,
        session_id="session-old",
        target_index=1,
        episode_date="2026-05-03",
        observed={"situation": {"value": "old", "source_quote": "old"}},
    )
    session_store.save_session(existing)
    message = _FakeMessage("/capture3 новый факт | внутри | действие")

    _run(
        telegram_bot._handle_capture3_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.observed["situation"] == {
        "value": "новый факт",
        "source_quote": "новый факт",
    }
    events = ux_events.read()
    assert events[0]["event_type"] == "session_cancelled"
    assert events[0]["cancel_reason"] == "capture3_restart"

def test_voice_input_artifact_from_update_preserves_telegram_metadata():
    voice = SimpleNamespace(
        file_id="voice-file-id",
        duration=9,
        mime_type="audio/ogg",
        file_size=4096,
    )
    message = _FakeMessage("", voice=voice)

    artifact = telegram_bot._voice_input_artifact_from_update(_fake_update(123, message))

    assert artifact is not None
    assert artifact.media_kind == "voice"
    assert artifact.file_id == "voice-file-id"
    assert artifact.duration_seconds == 9
    assert artifact.mime_type == "audio/ogg"
    assert artifact.file_size == 4096
    assert artifact.source_ref == {
        "chat_id": 123,
        "message_kind": "voice",
    }


def test_voice_message_requires_transcription_before_session_creation(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage(
        "",
        voice=SimpleNamespace(
            file_id="voice-file-id",
            duration=9,
            mime_type="audio/ogg",
            file_size=4096,
        ),
    )

    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
        )
    )

    assert session_store.load_session(123) is None
    assert message.replies == [
        "Голос получил, но расшифровка еще не подключена. "
        "Пока пришли этот эпизод текстом."
    ]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == [
        "input_received",
        "transcription_pending",
    ]
    assert events[0]["funnel"] == "voice"
    assert events[0]["media_kind"] == "voice"


def test_transcribed_voice_artifact_can_start_same_draft_session(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    artifact = voice_input_artifact("voice-file-id", transcript="голосовой эпизод")
    message = _FakeMessage("", voice=SimpleNamespace(file_id="voice-file-id"))

    _run(
        telegram_bot._start_input_artifact_capture_session(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            chat_id=123,
            artifact=artifact,
            now=datetime(2026, 5, 3, 9, 44, tzinfo=timezone.utc),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.observed == {
        "situation": {
            "value": "голосовой эпизод",
            "source_quote": "голосовой эпизод",
        }
    }
    assert loaded.target_index == 1
    assert [event["event_type"] for event in ux_events.read()] == [
        "input_received",
        "draft_created",
        "session_started",
        "step_answered",
        "step_prompted",
        "gap_question_asked",
    ]
    assert message.replies == [
        f"■□□□□□□□□□ 1/10\n\n{ToneEngine.default().target_prompt('trigger')}"
    ]

def test_voice_message_without_file_id_is_rejected(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("", voice=SimpleNamespace(file_id=""))

    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
        )
    )

    assert session_store.load_session(123) is None
    assert message.replies == ["Не смог прочитать голосовое сообщение"]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "missing_file_id"


def test_audio_input_artifact_from_update_preserves_metadata():
    audio = SimpleNamespace(
        file_id="audio-file-id",
        duration=33,
        mime_type="audio/mpeg",
        file_size=8192,
        file_name="note.mp3",
    )
    message = _FakeMessage("", audio=audio)

    artifact = telegram_bot._audio_input_artifact_from_update(_fake_update(123, message))

    assert artifact is not None
    assert artifact.media_kind == "audio"
    assert artifact.file_id == "audio-file-id"
    assert artifact.duration_seconds == 33
    assert artifact.mime_type == "audio/mpeg"
    assert artifact.file_size == 8192
    assert artifact.file_name == "note.mp3"
    assert artifact.source_ref == {"chat_id": 123, "message_kind": "audio"}


def test_audio_message_requires_transcription_before_session_creation(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage(
        "",
        audio=SimpleNamespace(
            file_id="audio-file-id",
            duration=33,
            mime_type="audio/mpeg",
            file_size=8192,
            file_name="note.mp3",
        ),
    )

    _run(
        telegram_bot._handle_audio_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
        )
    )

    assert session_store.load_session(123) is None
    assert message.replies == [
        "Аудио получил, но расшифровка еще не подключена. "
        "Пока пришли этот эпизод текстом."
    ]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == [
        "input_received",
        "transcription_pending",
    ]
    assert events[0]["funnel"] == "audio"
    assert events[0]["media_kind"] == "audio"


def test_audio_document_input_artifact_from_update_rejects_non_audio_document():
    document = SimpleNamespace(
        file_id="document-file-id",
        mime_type="application/pdf",
        file_size=4096,
        file_name="doc.pdf",
    )
    message = _FakeMessage("", document=document)

    assert telegram_bot._audio_document_input_artifact_from_update(
        _fake_update(123, message)
    ) is None


def test_audio_document_message_requires_transcription_before_session_creation(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage(
        "",
        document=SimpleNamespace(
            file_id="document-file-id",
            mime_type="audio/ogg",
            file_size=4096,
            file_name="note.ogg",
        ),
    )

    _run(
        telegram_bot._handle_document_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
        )
    )

    assert session_store.load_session(123) is None
    assert message.replies == [
        "Аудио получил, но расшифровка еще не подключена. "
        "Пока пришли этот эпизод текстом."
    ]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == [
        "input_received",
        "transcription_pending",
    ]
    assert events[0]["funnel"] == "audio_document"
    assert events[0]["media_kind"] == "document"


def test_unsupported_document_message_is_rejected(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage(
        "",
        document=SimpleNamespace(
            file_id="document-file-id",
            mime_type="application/pdf",
            file_size=4096,
            file_name="doc.pdf",
        ),
    )

    _run(
        telegram_bot._handle_document_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
        )
    )

    assert session_store.load_session(123) is None
    assert message.replies == ["Поддерживаю только аудиофайлы"]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "unsupported_document"

def test_cancel_without_session_reports_no_active_session(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/cancel")
    update = _fake_update(123, message)

    _run(
        telegram_bot._handle_cancel_after_authorized(
            update, session_store, ux_events, _settings(), ToneEngine.default()
        )
    )

    assert session_store.load_session(123) is None
    assert ux_events.read() == []
    assert message.replies == ["Активной сессии нет"]


def test_accepted_answer_replies_with_bridge_and_next_question(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=0,
        episode_date="2026-05-03",
    )
    session_store.save_session(session)
    message = _FakeMessage("situation")

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 1
    assert message.replies == [
        f"■□□□□□□□□□ 1/10\n\n"
        f"{ToneEngine.default().target_prompt('trigger')}",
    ]
    assert message.reply_options == [{"parse_mode": "HTML"}]


def test_automatic_thought_answer_replies_with_plain_emotion_frame(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=4,
        episode_date="2026-05-03",
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "tr", "source_quote": "tr"},
            "actor": {"value": "ac", "source_quote": "ac"},
            "quote": {"value": "sp", "source_quote": "sp"},
        },
    )
    session_store.save_session(session)
    message = _FakeMessage("thought")

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 5
    assert message.replies == [
        f"■■■■■□□□□□ 5/10\n\n{ToneEngine.default().target_prompt('emotion')}",
    ]
    assert message.reply_options == [{"parse_mode": "HTML"}]


def test_text_during_emotion_step_advances_to_behavior(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = _emotion_step_session()
    session_store.save_session(session)
    message = _FakeMessage("страх")

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 6
    assert loaded.observed["emotion"] == {
        "value": "страх",
        "source_quote": "страх",
    }
    assert message.replies == [
        f"■■■■■■□□□□ 6/10\n\n{ToneEngine.default().target_prompt('behavior')}",
    ]
    assert message.reply_options == [{"parse_mode": "HTML"}]


def test_text_during_emotion_step_stores_plain_emotion(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = _emotion_step_session()
    session_store.save_session(session)
    message = _FakeMessage("смущение")

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 6
    assert loaded.observed["emotion"] == {
        "value": "смущение",
        "source_quote": "смущение",
    }
    assert message.replies == [
        f"■■■■■■□□□□ 6/10\n\n{ToneEngine.default().target_prompt('behavior')}",
    ]


def test_empty_answer_retries_without_bridge(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=0,
        episode_date="2026-05-03",
    )
    session_store.save_session(session)
    message = _FakeMessage(" ")

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 0
    assert message.replies == [
        f"Нужен непустой ответ\n\n{ToneEngine.default().target_prompt('situation')}",
    ]
    assert "■" not in message.replies[0]


def test_final_answer_opens_save_review_with_all_fields(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=9,
        episode_date="2026-05-03",
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "tr", "source_quote": "tr"},
            "actor": {"value": "ac", "source_quote": "ac"},
            "quote": {"value": "sp", "source_quote": "sp"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {"value": "e", "source_quote": "e"},
            "behavior": {"value": "b", "source_quote": "b"},
            "physical": {"value": "physical", "source_quote": "physical"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
        },
    )
    session_store.save_session(session)
    message = _FakeMessage("lt")

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.awaiting_save_confirmation is True
    assert loaded.target_index == 10
    assert message.replies == [
        "■■■■■■■■■■ 10/10 💯\n\n"
        "ситуация: s\n"
        "триггер: tr\n"
        "участник: ac\n"
        "цитата: sp\n"
        "мысль: at\n"
        "эмоция: e\n"
        "действие: b\n"
        "физическое: physical\n"
        "сразу после: st\n"
        "потом: lt\n\n"
        "Сохраняем?"
    ]
    assert message.reply_options[0]["reply_markup"] is not None
    assert ux_events.read()[-1]["event_type"] == "step_answered"

    followup = _FakeMessage("next")
    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, followup),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.observed["long_term_consequence"]["value"] == "lt"
    assert followup.replies[0].endswith("Сохраняем?")


def test_save_callback_writes_episode_and_replies_completion(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = _complete_review_session()
    session_store.save_session(session)
    callback = _FakeCallbackQuery("episode:save")

    _run(
        telegram_bot._handle_episode_callback_after_authorized(
            _fake_callback_update(123, callback),
            storage,
            session_store,
            ux_events,
            ToneEngine.default(),
        )
    )

    assert callback.answered is True
    assert session_store.load_session(123) is None
    assert [path.name for path in (tmp_path / "episodes").glob("*.json")] == [
        "episode-20260503-1.json"
    ]
    assert callback.message.replies == ["Готово. Эпизод собран\n\nВсего эпизодов: 1"]
    assert callback.message.reply_options == [{"parse_mode": "HTML"}]
    assert ux_events.read()[-1]["event_type"] == "session_completed"


def test_save_callback_writes_unified_episode(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = _complete_review_session()
    session_store.save_session(session)
    callback = _FakeCallbackQuery("episode:save")

    _run(
        telegram_bot._handle_episode_callback_after_authorized(
            _fake_callback_update(123, callback),
            storage,
            session_store,
            ux_events,
            ToneEngine.default(),
        )
    )

    saved = (tmp_path / "episodes" / "episode-20260503-1.json").read_text(
        encoding="utf-8"
    )
    assert '"trigger"' in saved
    assert '"actor"' in saved
    assert '"quote"' in saved
    assert session_store.load_session(123) is None


def test_cancel_callback_discards_review_session(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    session = _complete_review_session()
    session_store.save_session(session)
    callback = _FakeCallbackQuery("episode:cancel")

    _run(
        telegram_bot._handle_episode_callback_after_authorized(
            _fake_callback_update(123, callback),
            storage,
            session_store,
            ux_events,
            ToneEngine.default(),
        )
    )

    assert session_store.load_session(123) is None
    assert [path.name for path in (tmp_path / "episodes").glob("*.json")] == []
    assert callback.message.replies == ["Сессия отменена"]
    assert ux_events.read()[-1]["cancel_reason"] == "review_cancel"


def test_stale_initial_session_expires_and_logs_reason(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    now = datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc)
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=0,
        episode_date="2026-05-02",
        last_prompted_at=format_utc(now - timedelta(seconds=601)),
    )
    session_store.save_session(session)

    expired = telegram_bot._expire_initial_session_if_stale(
        session_store, ux_events, session, 123, now, 600
    )

    assert expired is True
    assert session_store.load_session(123) is None
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
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    now = datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc)
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=1,
        episode_date="2026-05-02",
        last_prompted_at=format_utc(now - timedelta(seconds=3600)),
    )
    session_store.save_session(session)

    expired = telegram_bot._expire_initial_session_if_stale(
        session_store, ux_events, session, 123, now, 600
    )

    assert expired is False
    assert session_store.load_session(123) is not None
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
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    now = datetime(2026, 5, 3, 9, 44, tzinfo=timezone.utc)

    session = telegram_bot._start_new_session(session_store, ux_events, 123, now)
    loaded = session_store.load_session(123)

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
        {
            "created_at": "2026-05-03T09:44:00Z",
            "draft_fields": 0,
            "event_type": "gap_question_asked",
            "funnel": "ten_question",
            "media_kind": "text",
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
    assert event["target"] == "trigger"


class _FakeMessage:
    def __init__(self, text: str, *, voice=None, audio=None, document=None) -> None:
        self.text = text
        self.voice = voice
        self.audio = audio
        self.document = document
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
        self.edits = []

    async def answer(self) -> None:
        self.answered = True

    async def edit_message_reply_markup(self, **kwargs) -> None:
        self.edits.append(kwargs)


def _run(coro):
    return asyncio.run(coro)


def _assert_no_internal_profile_terms(text: str) -> None:
    lowered = text.lower()
    for term in INTERNAL_PROFILE_TERMS:
        assert term not in lowered


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


def _emotion_step_session() -> LoopSession:
    return LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=5,
        episode_date="2026-05-03",
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "tr", "source_quote": "tr"},
            "actor": {"value": "ac", "source_quote": "ac"},
            "quote": {"value": "sp", "source_quote": "sp"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
        },
    )


def _complete_review_session() -> LoopSession:
    return LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=10,
        episode_date="2026-05-03",
        awaiting_save_confirmation=True,
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "tr", "source_quote": "tr"},
            "actor": {"value": "ac", "source_quote": "ac"},
            "quote": {"value": "sp", "source_quote": "sp"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {"value": "e", "source_quote": "e"},
            "behavior": {"value": "b", "source_quote": "b"},
            "physical": {"value": "physical", "source_quote": "physical"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
        },
    )


def _write_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_annotation_run(run_dir, row):
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "annotation_run_id": run_dir.name,
                "schema_version": "episode.v1",
                "taxonomy_version": "taxonomy.v1",
                "prompt_version": "prompt.v1",
                "created_at": "2026-05-01T00:00:00Z",
                "source_episode_count": 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "annotations.jsonl").write_text(
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _graph_ready_episode():
    return {
        "id": "episode-20260503-1",
        "date": "2026-05-03",
        "source": "telegram-chat:123",
        "observed": {
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "tr", "source_quote": "tr"},
            "actor": {"value": "ac", "source_quote": "ac"},
            "quote": {"value": "sp", "source_quote": "sp"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {"value": "страх", "source_quote": "страх"},
            "behavior": {"value": "b", "source_quote": "b"},
            "physical": {"value": "physical", "source_quote": "physical"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
        },
        "derived": {
            "nodes": [
                {
                    "id": "node-1",
                    "node_origin": "observed",
                    "kind": "cognition",
                    "text": "at",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "at",
                    "confidence": 0.9,
                },
                {
                    "id": "node-2",
                    "node_origin": "observed",
                    "kind": "emotion",
                    "text": "страх",
                    "source_field": "observed.emotion",
                    "source_quote": "страх",
                    "confidence": 0.9,
                },
                {
                    "id": "node-3",
                    "node_origin": "observed",
                    "kind": "behavior",
                    "text": "b",
                    "source_field": "observed.behavior",
                    "source_quote": "b",
                    "confidence": 0.9,
                },
            ],
            "trigger_annotations": [
                {
                    "id": "trigger-annotation-1",
                    "type": "social",
                    "source_field": "observed.trigger",
                    "source_quote": "tr",
                    "confidence": 0.9,
                }
            ],
            "actor_annotations": [],
            "cognition_annotations": [
                {
                    "id": "cognition-annotation-1",
                    "node_id": "node-1",
                    "text": "at",
                    "kind": "evaluation",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "at",
                    "confidence": 0.9,
                }
            ],
            "emotion_annotations": [
                {
                    "id": "emotion-annotation-1",
                    "node_id": "node-2",
                    "label": "страх",
                    "intensity": 0.5,
                    "valence": -0.7,
                    "arousal": 0.8,
                    "source_field": "observed.emotion",
                    "source_quote": "страх",
                    "confidence": 0.9,
                }
            ],
            "behavior_annotations": [
                {
                    "id": "behavior-annotation-1",
                    "node_id": "node-3",
                    "type": "avoid",
                    "source_field": "observed.behavior",
                    "source_quote": "b",
                    "confidence": 0.9,
                }
            ],
            "relations": [
                {
                    "id": "relation-1",
                    "type": "belongs_to",
                    "from_ref": "node-1",
                    "to_ref": "episode",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "at",
                    "confidence": 0.9,
                }
            ],
        },
    }


def _settings(
    admin_chat_ids=frozenset({123}),
    owner_chat_id=123,
    episode_dir=None,
    userlist_path=None,
    ux_event_log=None,
    annotation_run_dir=None,
    annotation_run_root=None,
):
    return SimpleNamespace(
        initial_session_ttl_sec=600,
        telegram_admin_chat_ids=admin_chat_ids,
        telegram_owner_chat_id=owner_chat_id,
        episode_dir=episode_dir,
        userlist_path=userlist_path,
        ux_event_log=ux_event_log,
        annotation_run_dir=annotation_run_dir,
        annotation_run_root=annotation_run_root,
        ux_idle_after_sec=7200,
        report_min_count=2,
    )

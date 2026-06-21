import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import app.telegram_bot as telegram_bot
from app.audio_flow_store import AudioFlowStore
from app.capture_flow_store import CaptureFlowStore
from app.episode_drafts import observed_text_field
from app.intake_transcripts import (
    build_intake_transcript,
    load_intake_transcript,
    save_intake_transcript,
)
from app.input_funnels import voice_input_artifact
from app.loop_extractor import LoopSession, prompt_for_current_target
from app.messages import TARGETS
from app.session_store import LoopSessionStore
from app.storage import JsonStorage
from app.tone_engine import ToneEngine
from app.transcription import TranscriptResult, TranscriptionFailed
from app.userlist import APPROVED, PAUSED, WAITLISTED, JsonUserList
from app.user_flow_router import FlowKind
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
        "10q",
        "3b",
        "1t",
        "1a",
        "1v",
        "status",
        "cancel",
        "help",
        "profile",
        "capture",
        "capture3",
        "voice",
        "approve",
        "pause",
        "report_graph",
        "report_ux",
        "admin_annotate_gaps",
    )
    assert telegram_bot._visible_command_menu(tone) == (
        {"command": "start", "description": "Начать 10 вопросов"},
        {"command": "10q", "description": "Эпизод через 10 вопросов"},
        {"command": "3b", "description": "Эпизод через 3 блока"},
        {"command": "1t", "description": "Эпизод одним текстом"},
        {"command": "1a", "description": "Эпизод голосом или аудио"},
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


def test_start_session_reply_uses_concise_first_question():
    tone = ToneEngine.default()
    session = LoopSession(
        chat_id=123,
        session_id="session-123",
        target_index=0,
        episode_date="2026-05-03",
    )

    assert tone.start_session(prompt_for_current_target(session, tone)) == (
        "□□□□□□□□□□ 0/10\n\n"
        "Опиши ситуацию несколькими предложениями"
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
        "/start или /10q — десять коротких вопросов\n"
        "/3b — три последовательных блока\n"
        "/1t — один текст, затем только недостающее\n"
        "/1a — одно голосовое или аудио\n"
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
    reply_markup = message.reply_options[0].get("reply_markup")
    if reply_markup is None:
        assert telegram_bot._profile_details_reply_markup() is None
    else:
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


def test_admin_annotate_gaps_writes_missing_annotation_run(tmp_path):
    settings = _settings(
        episode_dir=tmp_path / "episodes",
        annotation_run_root=tmp_path / "annotation-runs",
    )
    settings.episode_dir.mkdir(parents=True)
    episode = _graph_ready_episode()
    episode.pop("derived")
    _write_json(settings.episode_dir / "episode-20260503-1.json", episode)
    message = _FakeMessage("/admin_annotate_gaps")

    _run(
        telegram_bot._handle_admin_annotate_gaps_after_admin(
            _fake_update(123, message),
            settings,
            ToneEngine.default(),
        )
    )

    assert "new_annotations: 1" in message.replies[0]
    assert "coverage: 0/1 -> 1/1 (full)" in message.replies[0]
    assert len(list(settings.annotation_run_root.glob("run-*-deterministic"))) == 1


def test_admin_annotate_gaps_reports_noop_when_full(tmp_path):
    settings = _settings(
        episode_dir=tmp_path / "episodes",
        annotation_run_root=tmp_path / "annotation-runs",
    )
    settings.episode_dir.mkdir(parents=True)
    episode = _graph_ready_episode()
    episode.pop("derived")
    _write_json(settings.episode_dir / "episode-20260503-1.json", episode)
    _run(
        telegram_bot._handle_admin_annotate_gaps_after_admin(
            _fake_update(123, _FakeMessage("/admin_annotate_gaps")),
            settings,
            ToneEngine.default(),
        )
    )
    message = _FakeMessage("/admin_annotate_gaps")

    _run(
        telegram_bot._handle_admin_annotate_gaps_after_admin(
            _fake_update(123, message),
            settings,
            ToneEngine.default(),
        )
    )

    assert "new_annotations: 0" in message.replies[0]
    assert "pending: 0" in message.replies[0]


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


def test_plain_text_without_session_requires_start(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    private_text = "коллега резко ответил в чате"
    message = _FakeMessage(private_text)
    update = _fake_update(123, message)

    _run(
        telegram_bot._handle_message_after_authorized(
            update, session_store, ux_events, _settings(), ToneEngine.default()
        )
    )

    assert session_store.load_session(123) is None
    assert message.replies == [ToneEngine.default().no_active_loop_start()]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["funnel"] == "one_take_text"
    assert events[0]["media_kind"] == "text"
    assert events[0]["reject_reason"] == "idle_requires_start"
    assert private_text not in json.dumps(events, ensure_ascii=False)


@pytest.mark.parametrize(
    ("mode", "expected_status", "expected_reply"),
    [
        (
            FlowKind.ONE_TAKE_TEXT,
            "awaiting_text",
            telegram_bot._one_take_text_guidance(),
        ),
        (
            FlowKind.THREE_BLOCK,
            "awaiting_three_block",
            telegram_bot._three_block_prompt(0),
        ),
    ],
)
def test_first_class_text_commands_arm_capture_flow(
    tmp_path, mode, expected_status, expected_reply
):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    capture_flow_store = CaptureFlowStore(tmp_path / "runtime-flows")
    message = _FakeMessage(f"/{mode.value}")

    _run(
        telegram_bot._handle_capture_mode_command_after_authorized(
            _fake_update(123, message),
            session_store,
            capture_flow_store,
            _settings(),
            mode=mode,
        )
    )

    flow = capture_flow_store.load_flow(123)
    assert flow is not None
    assert flow.mode == mode.value
    assert flow.status == expected_status
    assert session_store.load_session(123) is None
    assert message.replies == [expected_reply]


def test_first_class_capture_command_does_not_replace_active_session(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    original = _emotion_step_session()
    session_store.save_session(original)
    capture_flow_store = CaptureFlowStore(tmp_path / "runtime-flows")
    message = _FakeMessage("/1t")

    _run(
        telegram_bot._handle_capture_mode_command_after_authorized(
            _fake_update(123, message),
            session_store,
            capture_flow_store,
            _settings(),
            mode=FlowKind.ONE_TAKE_TEXT,
        )
    )

    assert session_store.load_session(123) == original
    assert capture_flow_store.load_flow(123) is None
    assert message.replies == [telegram_bot._cancel_active_flow_first()]


def test_one_take_text_enters_shared_draft_hydration(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    capture_flow_store = CaptureFlowStore(tmp_path / "runtime-flows")
    capture_flow_store.arm_flow(
        123,
        mode="one_take_text",
        now=datetime.now(timezone.utc),
        ttl_sec=600,
    )
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    text = "коллега резко ответил в чате"
    message = _FakeMessage(text)

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
            audio_flow_store=capture_flow_store,
        )
    )

    session = session_store.load_session(123)
    assert capture_flow_store.load_flow(123) is None
    assert session is not None
    assert session.flow_mode == "one_take_text"
    assert session.capture_funnel == "one_take_text"
    assert session.observed == {"situation": observed_text_field(text)}
    assert session.awaiting_save_confirmation is False


def test_three_block_collects_sequential_answers_then_hydrates(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    capture_flow_store = CaptureFlowStore(tmp_path / "runtime-flows")
    capture_flow_store.arm_flow(
        123,
        mode="three_block",
        now=datetime.now(timezone.utc),
        ttl_sec=600,
    )
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")

    first = _FakeMessage("факт")
    second = _FakeMessage("мысль")
    third = _FakeMessage("замолчал")
    for message in (first, second, third):
        _run(
            telegram_bot._handle_message_after_authorized(
                _fake_update(123, message),
                session_store,
                ux_events,
                _settings(),
                ToneEngine.default(),
                audio_flow_store=capture_flow_store,
            )
        )

    session = session_store.load_session(123)
    assert capture_flow_store.load_flow(123) is None
    assert session is not None
    assert session.flow_mode == "three_block"
    assert session.capture_funnel == "three_block"
    assert session.observed == {
        "situation": observed_text_field("факт"),
        "automatic_thought": observed_text_field("мысль"),
        "behavior": observed_text_field("замолчал"),
    }
    assert first.replies == [telegram_bot._three_block_prompt(1)]
    assert second.replies == [telegram_bot._three_block_prompt(2)]
    assert third.replies == [
        f"■■■□□□□□□□ 3/10\n\n{ToneEngine.default().target_prompt('trigger')}"
    ]


def test_voice_command_arms_audio_flow_without_creating_classic_session(
    tmp_path, monkeypatch
):
    now = datetime(2026, 6, 18, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(telegram_bot, "utc_now", lambda: now)
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    message = _FakeMessage("/voice")

    _run(
        telegram_bot._handle_voice_command_after_authorized(
            _fake_update(123, message),
            session_store,
            audio_flow_store,
            _settings(),
        )
    )

    flow = audio_flow_store.load_flow(123, now=now)
    assert flow is not None
    assert flow.created_at == now
    assert flow.expires_at == now + timedelta(seconds=600)
    assert session_store.load_session(123) is None
    assert message.replies == [telegram_bot._audio_media_guidance()]


def test_repeated_voice_command_does_not_extend_audio_flow_expiry(
    tmp_path, monkeypatch
):
    armed_at = datetime(2026, 6, 18, 9, 0, tzinfo=timezone.utc)
    retried_at = armed_at + timedelta(seconds=30)
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    original = audio_flow_store.arm_flow(123, now=armed_at, ttl_sec=600)
    monkeypatch.setattr(telegram_bot, "utc_now", lambda: retried_at)
    message = _FakeMessage("/voice")

    _run(
        telegram_bot._handle_voice_command_after_authorized(
            _fake_update(123, message),
            session_store,
            audio_flow_store,
            _settings(),
        )
    )

    assert audio_flow_store.load_flow(123, now=retried_at) == original
    assert message.replies == [telegram_bot._audio_media_guidance()]


def test_voice_command_during_classic_session_requires_cancel(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session_store.save_session(_emotion_step_session())
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    message = _FakeMessage("/voice")

    _run(
        telegram_bot._handle_voice_command_after_authorized(
            _fake_update(123, message),
            session_store,
            audio_flow_store,
            _settings(),
        )
    )

    assert session_store.load_session(123) is not None
    assert audio_flow_store.load_flow(123) is None
    assert message.replies == [telegram_bot._cancel_active_flow_first()]


def test_start_during_audio_flow_requires_cancel(tmp_path):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    original = audio_flow_store.arm_flow(123, now=now, ttl_sec=600)
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/start")

    _run(
        telegram_bot._handle_start_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            audio_flow_store=audio_flow_store,
        )
    )

    assert session_store.load_session(123) is None
    assert audio_flow_store.load_flow(123) == original
    assert ux_events.read() == []
    assert message.replies == [telegram_bot._cancel_active_flow_first()]


def test_start_during_classic_session_requires_cancel(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session_store.save_session(_emotion_step_session())
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/start")

    _run(
        telegram_bot._handle_start_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            audio_flow_store=audio_flow_store,
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == 5
    assert loaded.observed == _emotion_step_session().observed
    assert ux_events.read() == []
    assert message.replies == [telegram_bot._cancel_active_flow_first()]


def test_text_during_audio_flow_keeps_flow_armed(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    audio_flow_store.arm_flow(
        123,
        now=datetime.now(timezone.utc),
        ttl_sec=600,
    )
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("private text")

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
            audio_flow_store=audio_flow_store,
        )
    )

    assert audio_flow_store.load_flow(123) is not None
    assert session_store.load_session(123) is None
    assert message.replies == [telegram_bot._audio_media_guidance()]
    events = ux_events.read()
    assert events[0]["reject_reason"] == "audio_flow_expects_media"
    assert "private text" not in json.dumps(events)


def test_cancel_clears_audio_flow_without_classic_session(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    audio_flow_store.arm_flow(
        123,
        now=datetime.now(timezone.utc),
        ttl_sec=600,
    )
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/cancel")

    _run(
        telegram_bot._handle_cancel_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
            audio_flow_store=audio_flow_store,
        )
    )

    assert audio_flow_store.load_flow(123) is None
    assert session_store.load_session(123) is None
    assert message.replies == [ToneEngine.default().cancel()]


def test_cancel_clears_classic_session_without_audio_flow(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session_store.save_session(_emotion_step_session())
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/cancel")

    _run(
        telegram_bot._handle_cancel_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
            audio_flow_store=audio_flow_store,
        )
    )

    assert session_store.load_session(123) is None
    assert audio_flow_store.load_flow(123) is None
    assert ux_events.read()[-1]["event_type"] == "session_cancelled"
    assert message.replies == [ToneEngine.default().cancel()]


def test_cancel_clears_inconsistent_classic_and_audio_state(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session_store.save_session(_emotion_step_session())
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    audio_flow_store.arm_flow(
        123,
        now=datetime.now(timezone.utc),
        ttl_sec=600,
    )
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("/cancel")

    _run(
        telegram_bot._handle_cancel_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
            audio_flow_store=audio_flow_store,
        )
    )

    assert session_store.load_session(123) is None
    assert audio_flow_store.load_flow(123) is None
    assert ux_events.read()[-1]["event_type"] == "session_cancelled"
    assert message.replies == [ToneEngine.default().cancel()]


def test_text_with_inconsistent_classic_and_audio_state_requires_cancel(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    original_session = _emotion_step_session()
    session_store.save_session(original_session)
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    original_flow = audio_flow_store.arm_flow(
        123,
        now=datetime.now(timezone.utc).replace(microsecond=0),
        ttl_sec=600,
    )
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("private text")

    _run(
        telegram_bot._handle_message_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            _settings(),
            ToneEngine.default(),
            audio_flow_store=audio_flow_store,
        )
    )

    assert session_store.load_session(123) == original_session
    assert audio_flow_store.load_flow(123) == original_flow
    assert message.replies == [telegram_bot._cancel_active_flow_first()]
    events = ux_events.read()
    assert events[-1]["reject_reason"] == "active_flow_requires_cancel"
    assert "private text" not in json.dumps(events)


def test_help_does_not_change_classic_or_audio_state(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    original_session = _emotion_step_session()
    session_store.save_session(original_session)
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    original_flow = audio_flow_store.arm_flow(
        123,
        now=datetime.now(timezone.utc).replace(microsecond=0),
        ttl_sec=600,
    )
    message = _FakeMessage("/help")

    _run(telegram_bot._send_help(_fake_update(123, message), ToneEngine.default()))

    assert session_store.load_session(123) == original_session
    assert audio_flow_store.load_flow(123) == original_flow


def test_profile_does_not_change_classic_or_audio_state(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    original_session = _emotion_step_session()
    session_store.save_session(original_session)
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    original_flow = audio_flow_store.arm_flow(
        123,
        now=datetime.now(timezone.utc).replace(microsecond=0),
        ttl_sec=600,
    )
    settings = _settings(episode_dir=tmp_path / "episodes")
    settings.episode_dir.mkdir(parents=True)
    message = _FakeMessage("/profile")

    _run(
        telegram_bot._handle_profile_after_authorized(
            _fake_update(123, message),
            settings,
            ToneEngine.default(),
        )
    )

    assert session_store.load_session(123) == original_session
    assert audio_flow_store.load_flow(123) == original_flow
    assert message.replies == [
        "Профиль пока не собран. Нужны сохранённые и обработанные эпизоды."
    ]


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


def test_capture_command_requires_cancel_for_existing_session(tmp_path):
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
        "value": "old",
        "source_quote": "old",
    }
    assert ux_events.read() == []
    assert message.replies == [telegram_bot._cancel_active_flow_first()]



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


def test_capture3_command_requires_cancel_for_existing_session(tmp_path):
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
        "value": "old",
        "source_quote": "old",
    }
    assert ux_events.read() == []
    assert message.replies == [telegram_bot._cancel_active_flow_first()]

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


def test_idle_voice_requires_start_without_transcription(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage(
        "",
        message_id=42,
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
    assert message.replies == [ToneEngine.default().no_active_loop_start()]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["funnel"] == "one_take_audio"
    assert events[0]["media_kind"] == "voice"
    assert events[0]["reject_reason"] == "idle_requires_start"


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

def test_idle_voice_without_file_id_still_requires_start(tmp_path):
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
    assert message.replies == [ToneEngine.default().no_active_loop_start()]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "idle_requires_start"


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


def test_idle_audio_requires_start_without_transcription(tmp_path):
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
    assert message.replies == [ToneEngine.default().no_active_loop_start()]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["funnel"] == "one_take_audio"
    assert events[0]["media_kind"] == "audio"
    assert events[0]["reject_reason"] == "idle_requires_start"


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


def test_idle_audio_document_requires_start_without_transcription(tmp_path):
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
    assert message.replies == [ToneEngine.default().no_active_loop_start()]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["funnel"] == "one_take_audio"
    assert events[0]["media_kind"] == "document"
    assert events[0]["reject_reason"] == "idle_requires_start"


def test_idle_unsupported_document_uses_same_start_guidance(tmp_path):
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
    assert message.replies == [ToneEngine.default().no_active_loop_start()]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "idle_requires_start"

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
    reply_markup = message.reply_options[0].get("reply_markup")
    if reply_markup is None:
        assert telegram_bot._review_reply_markup() is None
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
    assert loaded.flow_mode == "classic_10q"
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
            "funnel": "classic_10q",
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
    def __init__(self, text: str, *, voice=None, audio=None, document=None, message_id=None) -> None:
        self.text = text
        self.message_id = message_id
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


class _FakeTelegramFile:
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def download_to_drive(self, custom_path):
        custom_path.write_bytes(self.content)


class _FakeDownloadBot:
    def __init__(self) -> None:
        self.file_ids = []

    async def get_file(self, file_id: str):
        self.file_ids.append(file_id)
        return _FakeTelegramFile(b"voice")


class _StaticTranscriptionProvider:
    _m3_run_inline_for_tests = True

    def transcribe(self, media):
        assert media.path.exists()
        return TranscriptResult("голосовой эпизод", language="ru", provider="fake")


class _FailingDownloadBot:
    async def get_file(self, file_id: str):
        raise RuntimeError("download failed")


class _FailingTranscriptionProvider:
    _m3_run_inline_for_tests = True

    def transcribe(self, media):
        raise TranscriptionFailed("transcription failed")


@pytest.mark.parametrize(
    ("handler_name", "message_kwargs"),
    [
        (
            "_handle_voice_after_authorized",
            {
                "voice": SimpleNamespace(
                    file_id="voice-file-id",
                    duration=9,
                    mime_type="audio/ogg",
                    file_size=4096,
                )
            },
        ),
        (
            "_handle_audio_after_authorized",
            {
                "audio": SimpleNamespace(
                    file_id="audio-file-id",
                    duration=33,
                    mime_type="audio/mpeg",
                    file_size=8192,
                    file_name="note.mp3",
                )
            },
        ),
        (
            "_handle_document_after_authorized",
            {
                "document": SimpleNamespace(
                    file_id="document-file-id",
                    mime_type="audio/ogg",
                    file_size=8192,
                    file_name="voice.ogg",
                )
            },
        ),
    ],
)
def test_armed_audio_flow_accepts_supported_media_and_completes(
    tmp_path, handler_name, message_kwargs
):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session_store.save_session = lambda session: pytest.fail(
        "audio intake must not create a LoopSession"
    )
    session_store.delete_session = lambda chat_id: pytest.fail(
        "audio intake must not delete a LoopSession"
    )
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    audio_flow_store.arm_flow(
        123,
        now=datetime.now(timezone.utc),
        ttl_sec=600,
    )
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage("", message_id=42, **message_kwargs)
    settings = _settings()
    settings.audio_temp_dir = tmp_path / "audio"
    settings.intake_transcript_dir = tmp_path / "intake-transcripts"
    settings.audio_max_duration_sec = 300
    settings.audio_max_file_size_bytes = 20 * 1024 * 1024

    _run(
        getattr(telegram_bot, handler_name)(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=_FakeDownloadBot(),
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
            audio_flow_store=audio_flow_store,
        )
    )

    flow = audio_flow_store.load_flow(123)
    assert flow is not None
    assert flow.status == "awaiting_transcript_confirmation"
    assert session_store.load_session(123) is None
    transcript_path = (
        settings.intake_transcript_dir / "telegram-chat-123" / "message-42.json"
    )
    assert transcript_path.exists()
    assert "голосовой эпизод" in transcript_path.read_text(encoding="utf-8")
    assert message.replies[-3:] == [
        "Готово, расшифровал. Проверь текст:",
        "голосовой эпизод",
        "Продолжить с этой расшифровкой?",
    ]
    assert [event["event_type"] for event in ux_events.read()][-1] == (
        "transcript_created"
    )


def test_transcript_continue_enters_shared_draft_hydration(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    capture_flow_store = CaptureFlowStore(tmp_path / "runtime-flows")
    now = datetime.now(timezone.utc)
    capture_flow_store.arm_flow(
        123,
        mode="one_take_audio",
        now=now,
        ttl_sec=600,
    )
    transcript = build_intake_transcript(
        voice_input_artifact(
            "file-id",
            transcript="точная расшифровка",
            source_ref={"chat_id": 123, "message_id": 42},
        ),
        created_at=now,
    )
    transcript_path = save_intake_transcript(
        tmp_path / "intake-transcripts", transcript
    )
    capture_flow_store.await_transcript_confirmation(
        123,
        transcript_path,
        now=now,
        ttl_sec=600,
    )
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    query = _FakeCallbackQuery("transcript:continue")

    _run(
        telegram_bot._handle_transcript_callback_after_authorized(
            _fake_callback_update(123, query),
            session_store,
            capture_flow_store,
            ux_events,
            ToneEngine.default(),
        )
    )

    session = session_store.load_session(123)
    assert query.answered is True
    assert capture_flow_store.load_flow(123) is None
    assert session is not None
    assert session.flow_mode == "one_take_audio"
    assert session.capture_funnel == "one_take_audio"
    assert session.media_kind == "voice"
    assert session.intake_transcript_path == str(transcript_path)
    assert session.observed == {
        "situation": observed_text_field("точная расшифровка")
    }


def test_transcript_reject_keeps_source_without_creating_draft(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    capture_flow_store = CaptureFlowStore(tmp_path / "runtime-flows")
    now = datetime.now(timezone.utc)
    capture_flow_store.arm_flow(
        123,
        mode="one_take_audio",
        now=now,
        ttl_sec=600,
    )
    transcript_path = save_intake_transcript(
        tmp_path / "intake-transcripts",
        build_intake_transcript(
            voice_input_artifact(
                "file-id",
                transcript="не использовать",
                source_ref={"chat_id": 123, "message_id": 42},
            ),
            created_at=now,
        ),
    )
    capture_flow_store.await_transcript_confirmation(
        123,
        transcript_path,
        now=now,
        ttl_sec=600,
    )
    query = _FakeCallbackQuery("transcript:reject")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")

    _run(
        telegram_bot._handle_transcript_callback_after_authorized(
            _fake_callback_update(123, query),
            session_store,
            capture_flow_store,
            ux_events,
            ToneEngine.default(),
        )
    )

    assert capture_flow_store.load_flow(123) is None
    assert session_store.load_session(123) is None
    assert transcript_path.exists()
    assert load_intake_transcript(transcript_path).episode_id is None
    assert ux_events.read()[0]["event_type"] == "transcript_rejected"


def test_saved_audio_draft_links_transcript_to_episode(tmp_path):
    transcript_path = save_intake_transcript(
        tmp_path / "intake-transcripts",
        build_intake_transcript(
            voice_input_artifact(
                "file-id",
                transcript="голосовой эпизод",
                source_ref={"chat_id": 123, "message_id": 42},
            )
        ),
    )
    observed = {
        target: observed_text_field(f"value-{target}")
        for target in TARGETS
    }
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session_store.save_session(
        LoopSession(
            chat_id=123,
            session_id="session-audio",
            episode_date="2026-06-21",
            observed=observed,
            awaiting_save_confirmation=True,
            capture_funnel="one_take_audio",
            media_kind="voice",
            intake_transcript_path=str(transcript_path),
        )
    )
    query = _FakeCallbackQuery("episode:save")

    _run(
        telegram_bot._handle_episode_callback_after_authorized(
            _fake_callback_update(123, query),
            JsonStorage(tmp_path / "episodes"),
            session_store,
            UxEventLog(tmp_path / "ux" / "events.jsonl"),
            ToneEngine.default(),
        )
    )

    assert load_intake_transcript(transcript_path).episode_id == "episode-20260621-1"


def test_transcript_chunks_preserve_complete_text():
    text = "a" * 8001

    chunks = telegram_bot._split_telegram_text(text)

    assert "".join(chunks) == text
    assert all(len(chunk) <= telegram_bot.TELEGRAM_TEXT_LIMIT for chunk in chunks)


def test_unsupported_document_while_audio_armed_keeps_flow(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    audio_flow_store.arm_flow(
        123,
        now=datetime.now(timezone.utc),
        ttl_sec=600,
    )
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
            audio_flow_store=audio_flow_store,
        )
    )

    assert audio_flow_store.load_flow(123) is not None
    assert session_store.load_session(123) is None
    assert message.replies == [telegram_bot._audio_media_guidance()]
    assert ux_events.read()[0]["reject_reason"] == "unsupported_document"


def test_audio_validation_failure_keeps_flow_armed(tmp_path):
    session_store, audio_flow_store, ux_events, message, settings = (
        _armed_voice_test_context(tmp_path, duration=301)
    )

    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=_FakeDownloadBot(),
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
            audio_flow_store=audio_flow_store,
        )
    )

    assert audio_flow_store.load_flow(123) is not None
    assert ux_events.read()[-1]["reject_reason"] == "over_duration"


def test_audio_download_failure_keeps_flow_armed(tmp_path):
    session_store, audio_flow_store, ux_events, message, settings = (
        _armed_voice_test_context(tmp_path)
    )

    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=_FailingDownloadBot(),
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
            audio_flow_store=audio_flow_store,
        )
    )

    assert audio_flow_store.load_flow(123) is not None
    assert ux_events.read()[-1]["event_type"] == "media_download_failed"


def test_audio_transcription_failure_keeps_flow_armed(tmp_path):
    session_store, audio_flow_store, ux_events, message, settings = (
        _armed_voice_test_context(tmp_path)
    )

    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=_FakeDownloadBot(),
            settings=settings,
            transcription_provider=_FailingTranscriptionProvider(),
            audio_flow_store=audio_flow_store,
        )
    )

    assert audio_flow_store.load_flow(123) is not None
    assert ux_events.read()[-1]["event_type"] == "transcription_failed"


def test_audio_storage_failure_keeps_flow_armed(tmp_path, monkeypatch):
    session_store, audio_flow_store, ux_events, message, settings = (
        _armed_voice_test_context(tmp_path)
    )

    def fail_save(*args, **kwargs):
        raise OSError("storage failed")

    monkeypatch.setattr(telegram_bot, "save_intake_transcript", fail_save)
    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=_FakeDownloadBot(),
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
            audio_flow_store=audio_flow_store,
        )
    )

    assert audio_flow_store.load_flow(123) is not None
    assert session_store.load_session(123) is None
    assert "Не смог сохранить расшифровку" in message.replies[-1]


def _armed_voice_test_context(tmp_path, *, duration=9):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    audio_flow_store = AudioFlowStore(tmp_path / "runtime-flows")
    audio_flow_store.arm_flow(
        123,
        now=datetime.now(timezone.utc),
        ttl_sec=600,
    )
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage(
        "",
        message_id=42,
        voice=SimpleNamespace(
            file_id="voice-file-id",
            duration=duration,
            mime_type="audio/ogg",
            file_size=4096,
        ),
    )
    settings = _settings()
    settings.audio_temp_dir = tmp_path / "audio"
    settings.intake_transcript_dir = tmp_path / "intake-transcripts"
    settings.audio_max_duration_sec = 300
    settings.audio_max_file_size_bytes = 20 * 1024 * 1024
    return session_store, audio_flow_store, ux_events, message, settings


def test_idle_voice_with_provider_does_not_download_or_transcribe(tmp_path):
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
        message_id=42,
    )
    settings = _settings()
    settings.audio_temp_dir = tmp_path / "audio"
    settings.intake_transcript_dir = tmp_path / "intake-transcripts"
    settings.audio_max_duration_sec = 300
    settings.audio_max_file_size_bytes = 20 * 1024 * 1024
    bot = _FakeDownloadBot()

    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=bot,
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
        )
    )

    assert session_store.load_session(123) is None
    transcript_path = (
        settings.intake_transcript_dir / "telegram-chat-123" / "message-42.json"
    )
    assert not transcript_path.exists()
    assert bot.file_ids == []
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "idle_requires_start"
    assert message.replies == [ToneEngine.default().no_active_loop_start()]

def test_idle_voice_is_rejected_before_media_validation(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage(
        "",
        voice=SimpleNamespace(
            file_id="voice-file-id",
            duration=301,
            mime_type="audio/ogg",
            file_size=4096,
        ),
    )
    settings = _settings()
    settings.audio_temp_dir = tmp_path / "audio"
    settings.intake_transcript_dir = tmp_path / "intake-transcripts"
    settings.audio_max_duration_sec = 300
    settings.audio_max_file_size_bytes = 20 * 1024 * 1024

    bot = _FakeDownloadBot()
    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=bot,
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
        )
    )

    assert session_store.load_session(123) is None
    assert bot.file_ids == []
    assert message.replies == [ToneEngine.default().no_active_loop_start()]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "idle_requires_start"


def test_idle_audio_with_provider_does_not_download_or_transcribe(tmp_path):
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
    settings = _settings()
    settings.audio_temp_dir = tmp_path / "audio"
    settings.intake_transcript_dir = tmp_path / "intake-transcripts"
    settings.audio_max_duration_sec = 300
    settings.audio_max_file_size_bytes = 20 * 1024 * 1024

    bot = _FakeDownloadBot()
    _run(
        telegram_bot._handle_audio_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=bot,
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
        )
    )

    assert session_store.load_session(123) is None
    assert bot.file_ids == []
    assert message.replies == [ToneEngine.default().no_active_loop_start()]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "idle_requires_start"

def test_idle_audio_document_with_provider_does_not_download_or_transcribe(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage(
        "",
        document=SimpleNamespace(
            file_id="doc-file-id",
            mime_type="audio/ogg",
            file_size=8192,
            file_name="voice.ogg",
        ),
    )
    settings = _settings()
    settings.audio_temp_dir = tmp_path / "audio"
    settings.intake_transcript_dir = tmp_path / "intake-transcripts"
    settings.audio_max_duration_sec = 300
    settings.audio_max_file_size_bytes = 20 * 1024 * 1024

    bot = _FakeDownloadBot()
    _run(
        telegram_bot._handle_document_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=bot,
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
        )
    )

    assert session_store.load_session(123) is None
    assert bot.file_ids == []
    assert message.replies == [ToneEngine.default().no_active_loop_start()]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "idle_requires_start"

def test_voice_during_active_session_asks_for_text_without_transcription(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session = _emotion_step_session()
    session_store.save_session(session)
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
    settings = _settings()
    settings.audio_temp_dir = tmp_path / "audio"
    settings.audio_max_duration_sec = 300
    settings.audio_max_file_size_bytes = 20 * 1024 * 1024
    bot = _FakeDownloadBot()

    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=bot,
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == session.target_index
    assert loaded.observed == session.observed
    assert bot.file_ids == []
    assert message.replies == ["Ответь, пожалуйста, текстом на текущий вопрос."]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "active_session"


def test_audio_during_active_session_asks_for_text_without_transcription(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session = _emotion_step_session()
    session_store.save_session(session)
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
    settings = _settings()
    settings.audio_temp_dir = tmp_path / "audio"
    settings.audio_max_duration_sec = 300
    settings.audio_max_file_size_bytes = 20 * 1024 * 1024
    bot = _FakeDownloadBot()

    _run(
        telegram_bot._handle_audio_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=bot,
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == session.target_index
    assert loaded.observed == session.observed
    assert bot.file_ids == []
    assert message.replies == ["Ответь, пожалуйста, текстом на текущий вопрос."]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "active_session"


def test_audio_document_during_active_session_asks_for_text_without_download(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session = _emotion_step_session()
    session_store.save_session(session)
    ux_events = UxEventLog(tmp_path / "ux" / "events.jsonl")
    message = _FakeMessage(
        "",
        document=SimpleNamespace(
            file_id="document-file-id",
            mime_type="audio/ogg",
            file_size=8192,
            file_name="voice.ogg",
        ),
    )
    bot = _FakeDownloadBot()

    _run(
        telegram_bot._handle_document_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=bot,
            settings=_settings(),
            transcription_provider=_StaticTranscriptionProvider(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.target_index == session.target_index
    assert loaded.observed == session.observed
    assert bot.file_ids == []
    assert message.replies == ["Ответь, пожалуйста, текстом на текущий вопрос."]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "active_session"


def test_voice_at_initial_first_step_requires_text(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session_store.save_session(
        LoopSession(
            chat_id=123,
            session_id="initial-session",
            target_index=0,
            episode_date="2026-05-03",
        )
    )
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
    settings = _settings()
    settings.audio_temp_dir = tmp_path / "audio"
    settings.audio_max_duration_sec = 300
    settings.audio_max_file_size_bytes = 20 * 1024 * 1024
    bot = _FakeDownloadBot()

    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=bot,
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
        )
    )

    loaded = session_store.load_session(123)
    assert loaded is not None
    assert loaded.session_id == "initial-session"
    assert loaded.target_index == 0
    assert bot.file_ids == []
    assert message.replies == ["Ответь, пожалуйста, текстом на текущий вопрос."]
    events = ux_events.read()
    assert [event["event_type"] for event in events] == ["input_rejected"]
    assert events[0]["reject_reason"] == "active_session"

def test_idle_media_logs_do_not_include_private_content(tmp_path, capsys):
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
    settings = _settings()
    settings.audio_temp_dir = tmp_path / "audio"
    settings.audio_max_duration_sec = 300
    settings.audio_max_file_size_bytes = 20 * 1024 * 1024

    bot = _FakeDownloadBot()
    _run(
        telegram_bot._handle_voice_after_authorized(
            _fake_update(123, message),
            session_store,
            ux_events,
            ToneEngine.default(),
            bot=bot,
            settings=settings,
            transcription_provider=_StaticTranscriptionProvider(),
        )
    )

    output = capsys.readouterr().out
    assert output == ""
    assert "голосовой эпизод" not in output
    assert "voice-file-id" not in json.dumps(ux_events.read(), ensure_ascii=False)
    assert bot.file_ids == []


def test_audio_intake_preview_is_capped():
    preview = telegram_bot._audio_intake_preview("a" * 250, limit=20)

    assert preview == "aaaaaaaaaaaaaaaaaaa…"

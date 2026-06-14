from datetime import datetime, timezone

import json

from app.ux_analytics import (
    load_user_records,
    main,
    render_markdown,
    summarize_events,
    write_reports,
)
from app.ux_events import base_event, telegram_event


def test_summarize_events_counts_completion_retries_and_lengths():
    events = [
        telegram_event(
            "update_received",
            "456",
            created_at=_dt(11, 58),
            chat_id=456,
            message_kind="command",
            command="/start",
        ),
        telegram_event(
            "unauthorized_attempt",
            "456",
            created_at=_dt(11, 58),
            chat_id=456,
            message_kind="command",
            command="/start",
        ),
        base_event(
            "input_received",
            "session-1",
            "123",
            created_at=_dt(12, 0),
            funnel="one_take_text",
            media_kind="text",
        ),
        base_event(
            "draft_created",
            "session-1",
            "123",
            created_at=_dt(12, 0),
            funnel="one_take_text",
            media_kind="text",
            draft_fields=1,
        ),
        telegram_event(
            "input_received",
            "123",
            created_at=_dt(12, 3),
            chat_id=123,
            message_kind="voice",
            funnel="voice",
            media_kind="voice",
        ),
        telegram_event(
            "transcription_pending",
            "123",
            created_at=_dt(12, 3),
            chat_id=123,
            message_kind="voice",
            funnel="voice",
            media_kind="voice",
        ),
        telegram_event(
            "input_rejected",
            "123",
            created_at=_dt(12, 4),
            chat_id=123,
            message_kind="document",
            funnel="audio_document",
            media_kind="document",
            reject_reason="unsupported_document",
        ),
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
            "gap_question_asked",
            "session-1",
            "123",
            created_at=_dt(12, 0),
            target="episode_date",
            target_index=0,
            funnel="one_take_text",
            media_kind="text",
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
            "gap_question_asked",
            "session-1",
            "123",
            created_at=_dt(12, 1),
            target="episode_date",
            target_index=0,
            funnel="one_take_text",
            media_kind="text",
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

    summary = summarize_events(
        events,
        now=_dt(12, 11),
        idle_after_sec=7200,
        user_records={"123": {"username": "test_user"}, "456": {"first_name": "Guest"}},
    )

    assert summary["sessions_started"] == 1
    assert summary["sessions_completed"] == 1
    assert summary["completion_rate"] == 1.0
    assert summary["updates_received"] == 1
    assert summary["unauthorized_attempts"] == 1
    assert summary["unauthorized_users"] == 1
    assert summary["updates_by_message_kind"] == {"command": 1}
    assert summary["inputs_by_funnel"] == {"one_take_text": 1, "voice": 1}
    assert summary["inputs_by_media_kind"] == {"text": 1, "voice": 1}
    assert summary["drafts_created_by_funnel"] == {"one_take_text": 1}
    assert summary["avg_draft_fields_by_funnel"] == {"one_take_text": 1.0}
    assert summary["transcription_pending_by_funnel"] == {"voice": 1}
    assert summary["input_rejections_by_reason"] == {"unsupported_document": 1}
    assert summary["unauthorized_by_user"] == {"456": 1}
    assert summary["user_labels"] == {"123": "123 (@test_user)", "456": "456 (Guest)"}
    assert summary["avg_session_duration_sec"] == 600.0
    assert summary["retry_count_by_target"] == {"episode_date": 1}
    assert summary["answer_chars_avg_by_target"] == {"episode_date": 6.5}
    assert summary["steps_prompted_by_target"] == {"episode_date": 2}
    assert summary["steps_answered_by_target"] == {"episode_date": 2}
    assert summary["gap_questions_by_funnel"] == {"one_take_text": 2}
    assert summary["gap_questions_by_target"] == {"episode_date": 2}
    assert summary["avg_gap_questions_by_funnel"] == {"one_take_text": 2.0}


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


def test_ux_analytics_renders_and_writes_markdown_and_json(tmp_path):
    summary = {
        "sessions_started": 2,
        "sessions_completed": 1,
        "sessions_cancelled": 1,
        "completion_rate": 0.5,
        "updates_received": 4,
        "unauthorized_attempts": 1,
        "unauthorized_users": 1,
        "repeat_users": 0,
        "abandoned_count": 1,
        "avg_session_duration_sec": 42.5,
        "inputs_by_funnel": {"one_take_text": 2, "voice": 1},
        "inputs_by_media_kind": {"text": 2, "voice": 1},
        "drafts_created_by_funnel": {"one_take_text": 2},
        "avg_draft_fields_by_funnel": {"one_take_text": 1.0},
        "transcription_pending_by_funnel": {"voice": 1},
        "input_rejections_by_reason": {"unsupported_document": 1},
        "sessions_per_user": {"123": 2, "456": 1},
        "user_labels": {"123": "123 (@test_user)", "456": "456 (Guest)"},
        "steps_prompted_by_target": {"situation": 2, "behavior": 5},
        "steps_answered_by_target": {"situation": 1},
        "gap_questions_by_funnel": {"one_take_text": 2, "voice": 1},
        "gap_questions_by_target": {"trigger": 2, "emotion": 1},
        "avg_gap_questions_by_funnel": {"one_take_text": 2.0, "voice": 1.0},
        "avg_step_duration_sec_by_target": {"situation": 3.5},
        "answer_chars_avg_by_target": {"situation": 12.0},
        "retry_count_by_target": {},
        "cancel_deadends_by_target": {"situation": 1},
        "idle_deadends_by_target": {"emotion": 1},
    }

    text = render_markdown(summary)
    paths = write_reports(summary, tmp_path / "ux")

    assert "# UX Analytics" in text
    assert "- completion_rate: 50.00%" in text
    assert "## Inputs By Funnel" in text
    assert "- one_take_text: 2" in text
    assert "- voice: 1" in text
    assert "## Input Rejections By Reason" in text
    assert "- unsupported_document: 1" in text
    assert "## Gap Questions By Funnel" in text
    assert "- one_take_text: 2" in text
    assert "## Average Gap Questions By Funnel" in text
    assert "- 123 (@test_user): 2" in text
    assert "- 456 (Guest): 1" in text
    assert text.index("- behavior: 5") < text.index("- situation: 2")
    assert "- situation: 3.50" in text
    assert [path.name for path in paths] == ["all.md", "all.json"]
    assert (tmp_path / "ux" / "all.md").read_text(encoding="utf-8").startswith(
        "# UX Analytics"
    )
    saved = json.loads((tmp_path / "ux" / "all.json").read_text(encoding="utf-8"))
    assert saved["sessions_started"] == 2


def test_load_user_records_reads_userlist_labels(tmp_path):
    path = tmp_path / "users.json"
    path.write_text(
        json.dumps({"users": {"123": {"user_id": "123", "username": "test_user"}}}),
        encoding="utf-8",
    )

    assert load_user_records(path)["123"]["username"] == "test_user"


def test_ux_analytics_cli_without_output_dir_prints_without_writing(
    tmp_path,
    monkeypatch,
    capsys,
):
    event_log = tmp_path / "events.jsonl"
    userlist = tmp_path / "users.json"
    event_log.write_text(
        json.dumps(
            base_event(
                "session_started",
                "session-1",
                "123",
                created_at=_dt(12, 0),
            ),
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    userlist.write_text('{"users": {}}', encoding="utf-8")
    monkeypatch.setenv("M3_UX_EVENT_LOG", str(event_log))
    monkeypatch.setattr("sys.argv", ["ux_analytics", "--userlist", str(userlist)])

    main()

    assert json.loads(capsys.readouterr().out)["sessions_started"] == 1
    assert not (tmp_path / "reports").exists()


def test_ux_analytics_cli_writes_only_with_explicit_output_dir(
    tmp_path,
    monkeypatch,
    capsys,
):
    event_log = tmp_path / "events.jsonl"
    userlist = tmp_path / "users.json"
    output_dir = tmp_path / "reports" / "ux"
    event_log.write_text("", encoding="utf-8")
    userlist.write_text('{"users": {}}', encoding="utf-8")
    monkeypatch.setenv("M3_UX_EVENT_LOG", str(event_log))
    monkeypatch.setattr(
        "sys.argv",
        [
            "ux_analytics",
            "--userlist",
            str(userlist),
            "--output-dir",
            str(output_dir),
        ],
    )

    main()

    assert capsys.readouterr().out.splitlines() == [
        str(output_dir / "all.md"),
        str(output_dir / "all.json"),
    ]
    assert (output_dir / "all.md").exists()
    assert (output_dir / "all.json").exists()


def _dt(hour: int, minute: int) -> datetime:
    return datetime(2026, 5, 1, hour, minute, tzinfo=timezone.utc)

from __future__ import annotations

import json
import os
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from app.ux_events import UxEventLog, parse_utc, utc_now


DEFAULT_EVENT_LOG = Path("data/ux-events/events.jsonl")
DEFAULT_USERLIST = Path("data/userlist/users.json")
DEFAULT_IDLE_AFTER_SEC = 7200


def summarize_events(
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    idle_after_sec: int = DEFAULT_IDLE_AFTER_SEC,
    user_records: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current_time = now or utc_now()
    sessions_started = [e for e in events if e.get("event_type") == "session_started"]
    sessions_completed = [
        e for e in events if e.get("event_type") == "session_completed"
    ]
    sessions_cancelled = [
        e for e in events if e.get("event_type") == "session_cancelled"
    ]
    updates_received = [e for e in events if e.get("event_type") == "update_received"]
    unauthorized_attempts = [
        e for e in events if e.get("event_type") == "unauthorized_attempt"
    ]
    step_prompted = [e for e in events if e.get("event_type") == "step_prompted"]
    step_answered = [e for e in events if e.get("event_type") == "step_answered"]

    started_count = len(sessions_started)
    completed_count = len(sessions_completed)
    cancelled_count = len(sessions_cancelled)
    completion_rate = completed_count / started_count if started_count else 0.0

    session_duration_by_id = _session_durations(events)
    finished_session_ids = {
        e["session_id"] for e in sessions_completed + sessions_cancelled
    }
    finished_durations = [
        duration
        for session_id, duration in session_duration_by_id.items()
        if session_id in finished_session_ids
    ]

    sessions_per_user = Counter(e["user_id"] for e in sessions_started)
    user_labels = _user_labels(
        set(sessions_per_user)
        | {e["user_id"] for e in unauthorized_attempts if "user_id" in e},
        user_records or {},
    )
    repeat_users = sum(1 for count in sessions_per_user.values() if count > 1)

    idle_deadends = _idle_deadends(
        events, now=current_time, idle_after_sec=idle_after_sec
    )

    return {
        "sessions_started": started_count,
        "sessions_completed": completed_count,
        "sessions_cancelled": cancelled_count,
        "updates_received": len(updates_received),
        "unauthorized_attempts": len(unauthorized_attempts),
        "unauthorized_users": len(
            {e["user_id"] for e in unauthorized_attempts if "user_id" in e}
        ),
        "updates_by_message_kind": dict(
            Counter(e["message_kind"] for e in updates_received if "message_kind" in e)
        ),
        "unauthorized_by_user": dict(
            Counter(e["user_id"] for e in unauthorized_attempts if "user_id" in e)
        ),
        "completion_rate": completion_rate,
        "avg_session_duration_sec": _avg(finished_durations),
        "steps_prompted_by_target": dict(
            Counter(e["target"] for e in step_prompted if "target" in e)
        ),
        "steps_answered_by_target": dict(
            Counter(e["target"] for e in step_answered if "target" in e)
        ),
        "avg_step_duration_sec_by_target": _avg_by_target(
            step_answered, "duration_sec"
        ),
        "retry_count_by_target": dict(
            Counter(
                e["target"]
                for e in step_answered
                if e.get("target") and e.get("advanced") is False
            )
        ),
        "cancel_deadends_by_target": dict(
            Counter(e["target"] for e in sessions_cancelled if "target" in e)
        ),
        "idle_deadends_by_target": dict(Counter(e["target"] for e in idle_deadends)),
        "answer_chars_avg_by_target": _avg_by_target(step_answered, "answer_chars"),
        "sessions_per_user": dict(sessions_per_user),
        "user_labels": user_labels,
        "repeat_users": repeat_users,
        "abandoned_count": len(idle_deadends),
        "abandoned_candidates": idle_deadends,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print or write Telegram UX analytics reports."
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for saved UX report files. Prints JSON when omitted.",
    )
    parser.add_argument(
        "--userlist",
        default=str(DEFAULT_USERLIST),
        help="Userlist JSON used to label Telegram user ids.",
    )
    args = parser.parse_args()

    event_log = Path(os.environ.get("M3_UX_EVENT_LOG", DEFAULT_EVENT_LOG))
    idle_after_sec = int(os.environ.get("M3_UX_IDLE_AFTER_SEC", DEFAULT_IDLE_AFTER_SEC))
    summary = summarize_events(
        UxEventLog(event_log).read(),
        idle_after_sec=idle_after_sec,
        user_records=load_user_records(Path(args.userlist)),
    )
    if args.output_dir:
        for path in write_reports(summary, Path(args.output_dir)):
            print(path.as_posix())
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# UX Analytics",
        "",
        "## Summary",
        f"- sessions_started: {summary.get('sessions_started', 0)}",
        f"- sessions_completed: {summary.get('sessions_completed', 0)}",
        f"- sessions_cancelled: {summary.get('sessions_cancelled', 0)}",
        f"- completion_rate: {_format_percent(summary.get('completion_rate', 0.0))}",
        f"- updates_received: {summary.get('updates_received', 0)}",
        f"- unauthorized_attempts: {summary.get('unauthorized_attempts', 0)}",
        f"- unauthorized_users: {summary.get('unauthorized_users', 0)}",
        f"- repeat_users: {summary.get('repeat_users', 0)}",
        f"- abandoned_count: {summary.get('abandoned_count', 0)}",
        "",
        "## Timing",
        f"- avg_session_duration_sec: {_format_float(summary.get('avg_session_duration_sec', 0.0))}",
        "",
    ]
    lines.extend(
        _render_mapping(
            "## Sessions Per User",
            summary.get("sessions_per_user", {}),
            labels=summary.get("user_labels", {}),
        )
    )
    lines.extend(
        _render_mapping(
            "## Steps Prompted By Target",
            summary.get("steps_prompted_by_target", {}),
        )
    )
    lines.extend(
        _render_mapping(
            "## Steps Answered By Target",
            summary.get("steps_answered_by_target", {}),
        )
    )
    lines.extend(
        _render_mapping(
            "## Average Step Duration By Target",
            summary.get("avg_step_duration_sec_by_target", {}),
        )
    )
    lines.extend(
        _render_mapping(
            "## Average Answer Chars By Target",
            summary.get("answer_chars_avg_by_target", {}),
        )
    )
    lines.extend(
        _render_mapping(
            "## Retry Count By Target",
            summary.get("retry_count_by_target", {}),
        )
    )
    lines.extend(
        _render_mapping(
            "## Cancel Deadends By Target",
            summary.get("cancel_deadends_by_target", {}),
        )
    )
    lines.extend(
        _render_mapping(
            "## Idle Deadends By Target",
            summary.get("idle_deadends_by_target", {}),
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def write_reports(summary: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "all.md"
    json_path = output_dir / "all.json"
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return markdown_path, json_path


def load_user_records(path: Path = DEFAULT_USERLIST) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    users = data.get("users", {})
    if not isinstance(users, dict):
        return {}
    return {
        str(user_id): dict(record)
        for user_id, record in users.items()
        if isinstance(record, dict)
    }


def _avg(values: list[int]) -> float:
    return float(mean(values)) if values else 0.0


def _render_mapping(
    title: str,
    values: Any,
    *,
    labels: Any | None = None,
) -> list[str]:
    lines = [title]
    if not isinstance(values, dict) or not values:
        lines.extend(["- none", ""])
        return lines
    labels = labels if isinstance(labels, dict) else {}
    for key, value in sorted(values.items(), key=_mapping_sort_key):
        label = labels.get(str(key), str(key))
        lines.append(f"- {label}: {_format_value(value)}")
    lines.append("")
    return lines


def _mapping_sort_key(item: tuple[Any, Any]) -> tuple[int, float, str]:
    key, value = item
    if isinstance(value, int | float):
        return (0, -float(value), str(key))
    return (1, 0.0, str(key))


def _user_labels(
    user_ids: set[str],
    user_records: dict[str, dict[str, Any]],
) -> dict[str, str]:
    return {
        user_id: _user_label(user_id, user_records.get(user_id, {}))
        for user_id in sorted(user_ids)
    }


def _user_label(user_id: str, record: dict[str, Any]) -> str:
    username = str(record.get("username") or "").strip()
    if username:
        return f"{user_id} (@{username})"
    full_name = " ".join(
        part
        for part in (
            str(record.get("first_name") or "").strip(),
            str(record.get("last_name") or "").strip(),
        )
        if part
    )
    if full_name:
        return f"{user_id} ({full_name})"
    return user_id


def _format_percent(value: Any) -> str:
    if isinstance(value, int | float):
        return f"{value:.2%}"
    return str(value)


def _format_float(value: Any) -> str:
    if isinstance(value, int | float):
        return f"{float(value):.2f}"
    return str(value)


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _avg_by_target(events: list[dict[str, Any]], key: str) -> dict[str, float]:
    values_by_target: dict[str, list[int]] = defaultdict(list)
    for event in events:
        target = event.get("target")
        value = event.get(key)
        if target and isinstance(value, int):
            values_by_target[target].append(value)
    return {
        target: _avg(values)
        for target, values in sorted(values_by_target.items(), key=lambda item: item[0])
    }


def _session_durations(events: list[dict[str, Any]]) -> dict[str, int]:
    starts: dict[str, datetime] = {}
    ends: dict[str, datetime] = {}
    for event in events:
        session_id = event.get("session_id")
        if not session_id:
            continue
        if event.get("event_type") == "session_started":
            starts[session_id] = parse_utc(event["created_at"])
        elif event.get("event_type") in {"session_completed", "session_cancelled"}:
            ends[session_id] = parse_utc(event["created_at"])

    return {
        session_id: max(0, int((ends[session_id] - started_at).total_seconds()))
        for session_id, started_at in starts.items()
        if session_id in ends
    }


def _idle_deadends(
    events: list[dict[str, Any]], *, now: datetime, idle_after_sec: int
) -> list[dict[str, Any]]:
    active_sessions = {
        e["session_id"]: e
        for e in events
        if e.get("event_type") == "session_started" and "session_id" in e
    }
    for event in events:
        if event.get("event_type") in {"session_completed", "session_cancelled"}:
            active_sessions.pop(event.get("session_id"), None)

    latest_prompt_by_session: dict[str, dict[str, Any]] = {}
    latest_answer_by_session: dict[str, dict[str, Any]] = {}
    for event in events:
        session_id = event.get("session_id")
        if not session_id or session_id not in active_sessions:
            continue
        if event.get("event_type") == "step_prompted":
            latest_prompt_by_session[session_id] = event
        elif event.get("event_type") == "step_answered":
            latest_answer_by_session[session_id] = event

    candidates = []
    for session_id, prompt in latest_prompt_by_session.items():
        answer = latest_answer_by_session.get(session_id)
        if answer and parse_utc(answer["created_at"]) >= parse_utc(prompt["created_at"]):
            continue
        idle_sec = int((now - parse_utc(prompt["created_at"])).total_seconds())
        if idle_sec >= idle_after_sec:
            candidates.append(
                {
                    "session_id": session_id,
                    "user_id": prompt["user_id"],
                    "target": prompt["target"],
                    "target_index": prompt.get("target_index"),
                    "idle_sec": idle_sec,
                }
            )
    return candidates


if __name__ == "__main__":
    main()

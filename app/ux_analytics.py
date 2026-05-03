from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from app.ux_events import UxEventLog, parse_utc, utc_now


DEFAULT_EVENT_LOG = Path("data/ux-events/events.jsonl")
DEFAULT_IDLE_AFTER_SEC = 7200


def summarize_events(
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    idle_after_sec: int = DEFAULT_IDLE_AFTER_SEC,
) -> dict[str, Any]:
    current_time = now or utc_now()
    sessions_started = [e for e in events if e.get("event_type") == "session_started"]
    sessions_completed = [
        e for e in events if e.get("event_type") == "session_completed"
    ]
    sessions_cancelled = [
        e for e in events if e.get("event_type") == "session_cancelled"
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
    repeat_users = sum(1 for count in sessions_per_user.values() if count > 1)

    idle_deadends = _idle_deadends(
        events, now=current_time, idle_after_sec=idle_after_sec
    )

    return {
        "sessions_started": started_count,
        "sessions_completed": completed_count,
        "sessions_cancelled": cancelled_count,
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
        "repeat_users": repeat_users,
        "abandoned_count": len(idle_deadends),
        "abandoned_candidates": idle_deadends,
    }


def main() -> None:
    event_log = Path(os.environ.get("M3_UX_EVENT_LOG", DEFAULT_EVENT_LOG))
    idle_after_sec = int(os.environ.get("M3_UX_IDLE_AFTER_SEC", DEFAULT_IDLE_AFTER_SEC))
    summary = summarize_events(
        UxEventLog(event_log).read(), idle_after_sec=idle_after_sec
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def _avg(values: list[int]) -> float:
    return float(mean(values)) if values else 0.0


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

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def new_session_id(user_id: str, now: datetime | None = None) -> str:
    timestamp = format_utc(now or utc_now()).replace("-", "").replace(":", "")
    timestamp = timestamp.replace("Z", "Z")
    return f"session-{user_id}-{timestamp}"


@dataclass(frozen=True)
class UxEventLog:
    path: Path

    def append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.open("a", encoding="utf-8").write(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
        )

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events


def base_event(
    event_type: str,
    session_id: str,
    user_id: str,
    *,
    created_at: datetime | None = None,
    target: str | None = None,
    target_index: int | None = None,
    duration_sec: int | None = None,
    advanced: bool | None = None,
    answer_chars: int | None = None,
    cancel_reason: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_type": event_type,
        "session_id": session_id,
        "user_id": user_id,
        "created_at": format_utc(created_at or utc_now()),
    }
    optional = {
        "target": target,
        "target_index": target_index,
        "duration_sec": duration_sec,
        "advanced": advanced,
        "answer_chars": answer_chars,
        "cancel_reason": cancel_reason,
    }
    event.update({key: value for key, value in optional.items() if value is not None})
    return event

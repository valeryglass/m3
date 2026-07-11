from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.runtime_storage import atomic_write_json, locked_path
from app.ux_events import format_utc


WAITLISTED = "waitlisted"
APPROVED = "approved"
PAUSED = "paused"


@dataclass(frozen=True)
class UserListResult:
    record: dict[str, Any]
    created: bool


class JsonUserList:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, dict[str, Any]]:
        with locked_path(self.path):
            return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        users = data.get("users", {})
        if not isinstance(users, dict):
            return {}
        return {str(chat_id): dict(record) for chat_id, record in users.items()}

    def upsert_waitlisted(
        self,
        chat_id: int,
        user_id: str,
        *,
        now: datetime,
        profile: dict[str, Any] | None = None,
    ) -> UserListResult:
        with locked_path(self.path):
            users = self._load_unlocked()
            key = str(chat_id)
            created = key not in users
            timestamp = format_utc(now)
            profile = {
                field: value
                for field, value in (profile or {}).items()
                if value is not None and value != ""
            }
            if created:
                users[key] = {
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "status": WAITLISTED,
                    "first_seen_at": timestamp,
                    "last_seen_at": timestamp,
                }
            else:
                users[key]["last_seen_at"] = timestamp
                users[key]["user_id"] = user_id
            users[key].update(profile)
            self._save_unlocked(users)
            return UserListResult(record=dict(users[key]), created=created)

    def approve(self, chat_id: int, *, decided_by: str, now: datetime) -> dict[str, Any]:
        return self._decide(
            chat_id,
            status=APPROVED,
            decided_by=decided_by,
            timestamp_key="approved_at",
            now=now,
        )

    def pause(self, chat_id: int, *, decided_by: str, now: datetime) -> dict[str, Any]:
        return self._decide(
            chat_id,
            status=PAUSED,
            decided_by=decided_by,
            timestamp_key="paused_at",
            now=now,
        )

    def status_for_chat(self, chat_id: int) -> str | None:
        record = self.load().get(str(chat_id))
        if record is None:
            return None
        status = record.get("status")
        return str(status) if status is not None else None

    def is_approved(self, chat_id: int) -> bool:
        return self.status_for_chat(chat_id) == APPROVED

    def _decide(
        self,
        chat_id: int,
        *,
        status: str,
        decided_by: str,
        timestamp_key: str,
        now: datetime,
    ) -> dict[str, Any]:
        with locked_path(self.path):
            users = self._load_unlocked()
            key = str(chat_id)
            timestamp = format_utc(now)
            record = users.get(
                key,
                {
                    "chat_id": chat_id,
                    "user_id": str(chat_id),
                    "first_seen_at": timestamp,
                    "last_seen_at": timestamp,
                },
            )
            record.update(
                {
                    "status": status,
                    timestamp_key: timestamp,
                    "decided_by": decided_by,
                }
            )
            users[key] = record
            self._save_unlocked(users)
            return dict(record)

    def _save_unlocked(self, users: dict[str, dict[str, Any]]) -> None:
        atomic_write_json(
            self.path,
            {"users": users},
            sort_keys=True,
            lock=False,
        )

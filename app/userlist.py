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

    def has_current_consent(self, chat_id: int, notice_version: str) -> bool:
        record = self.load().get(str(chat_id), {})
        consent = record.get("consent")
        return bool(
            isinstance(consent, dict)
            and consent.get("status") == "accepted"
            and consent.get("notice_version") == notice_version
            and consent.get("adult_confirmed") is True
            and consent.get("accepted_at")
        )

    def accept_consent(
        self,
        chat_id: int,
        *,
        notice_version: str,
        now: datetime,
    ) -> dict[str, Any]:
        return self._record_consent(
            chat_id,
            {
                "status": "accepted",
                "notice_version": notice_version,
                "adult_confirmed": True,
                "accepted_at": format_utc(now),
            },
        )

    def decline_consent(
        self,
        chat_id: int,
        *,
        notice_version: str,
        now: datetime,
    ) -> dict[str, Any]:
        return self._record_consent(
            chat_id,
            {
                "status": "declined",
                "notice_version": notice_version,
                "adult_confirmed": False,
                "declined_at": format_utc(now),
            },
        )

    def delete_identity(self, user_id: str) -> int:
        with locked_path(self.path):
            users = self._load_unlocked()
            keys = [
                key
                for key, record in users.items()
                if key == str(user_id) or str(record.get("user_id")) == str(user_id)
            ]
            for key in keys:
                users.pop(key, None)
            self._save_unlocked(users)
            return len(keys)

    def records_for_identity(self, user_id: str) -> dict[str, dict[str, Any]]:
        return {
            key: record
            for key, record in self.load().items()
            if key == str(user_id) or str(record.get("user_id")) == str(user_id)
        }

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

    def _record_consent(
        self,
        chat_id: int,
        consent: dict[str, Any],
    ) -> dict[str, Any]:
        with locked_path(self.path):
            users = self._load_unlocked()
            key = str(chat_id)
            if key not in users:
                raise KeyError(f"unknown user: {chat_id}")
            users[key]["consent"] = consent
            self._save_unlocked(users)
            return dict(users[key])

    def _save_unlocked(self, users: dict[str, dict[str, Any]]) -> None:
        atomic_write_json(
            self.path,
            {"users": users},
            sort_keys=True,
            lock=False,
        )

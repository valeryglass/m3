from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class AudioOneTakeFlow:
    chat_id: int
    created_at: datetime
    expires_at: datetime
    flow: str = "audio_one_take"
    status: str = "awaiting_media"

    def __post_init__(self) -> None:
        if self.flow != "audio_one_take":
            raise ValueError("unsupported audio flow")
        if self.status != "awaiting_media":
            raise ValueError("unsupported audio flow status")
        if self.expires_at <= self.created_at:
            raise ValueError("audio flow expiry must follow creation")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["created_at"] = _format_utc(self.created_at)
        payload["expires_at"] = _format_utc(self.expires_at)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AudioOneTakeFlow:
        return cls(
            chat_id=int(payload["chat_id"]),
            created_at=_parse_utc(str(payload["created_at"])),
            expires_at=_parse_utc(str(payload["expires_at"])),
            flow=str(payload.get("flow", "")),
            status=str(payload.get("status", "")),
        )


class AudioFlowStore:
    def __init__(self, root: Path) -> None:
        self.flow_dir = root / "audio-one-take"
        self.flow_dir.mkdir(parents=True, exist_ok=True)

    def arm_flow(
        self,
        chat_id: int,
        *,
        now: datetime,
        ttl_sec: int,
    ) -> AudioOneTakeFlow:
        if ttl_sec <= 0:
            raise ValueError("audio flow ttl must be positive")
        flow = AudioOneTakeFlow(
            chat_id=chat_id,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_sec),
        )
        self._flow_path(chat_id).write_text(
            json.dumps(flow.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return flow

    def load_flow(
        self,
        chat_id: int,
        *,
        now: datetime | None = None,
    ) -> AudioOneTakeFlow | None:
        path = self._flow_path(chat_id)
        if not path.exists():
            return None
        flow = AudioOneTakeFlow.from_dict(
            json.loads(path.read_text(encoding="utf-8"))
        )
        if flow.chat_id != chat_id:
            raise ValueError("audio flow chat id does not match path")
        if flow.expires_at <= (now or datetime.now(timezone.utc)):
            path.unlink(missing_ok=True)
            return None
        return flow

    def delete_flow(self, chat_id: int) -> None:
        self._flow_path(chat_id).unlink(missing_ok=True)

    def _flow_path(self, chat_id: int) -> Path:
        return self.flow_dir / f"chat-{chat_id}.json"


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )

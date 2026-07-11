from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal


CaptureMode = Literal[
    "one_take_text",
    "three_block",
    "one_take_audio",
]
CaptureStatus = Literal[
    "awaiting_text",
    "awaiting_three_block",
    "awaiting_media",
    "awaiting_transcript_confirmation",
]


@dataclass(frozen=True)
class CaptureFlow:
    chat_id: int
    mode: CaptureMode
    status: CaptureStatus
    created_at: datetime
    expires_at: datetime
    blocks: tuple[str, ...] = field(default_factory=tuple)
    transcript_path: str | None = None

    def __post_init__(self) -> None:
        allowed_statuses = {
            "one_take_text": {"awaiting_text"},
            "three_block": {"awaiting_three_block"},
            "one_take_audio": {
                "awaiting_media",
                "awaiting_transcript_confirmation",
            },
        }
        if self.status not in allowed_statuses[self.mode]:
            raise ValueError("capture flow status does not match mode")
        if self.expires_at <= self.created_at:
            raise ValueError("capture flow expiry must follow creation")
        if self.mode != "three_block" and self.blocks:
            raise ValueError("only three-block flows may store blocks")
        if len(self.blocks) > 2:
            raise ValueError("three-block flow cannot store more than two blocks")
        if self.status == "awaiting_transcript_confirmation" and not self.transcript_path:
            raise ValueError("transcript confirmation requires a transcript path")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["created_at"] = _format_utc(self.created_at)
        payload["expires_at"] = _format_utc(self.expires_at)
        payload["blocks"] = list(self.blocks)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> CaptureFlow:
        return cls(
            chat_id=int(payload["chat_id"]),
            mode=str(payload["mode"]),
            status=str(payload["status"]),
            created_at=_parse_utc(str(payload["created_at"])),
            expires_at=_parse_utc(str(payload["expires_at"])),
            blocks=tuple(str(value) for value in payload.get("blocks", ())),
            transcript_path=(
                str(payload["transcript_path"])
                if payload.get("transcript_path")
                else None
            ),
        )


class CaptureFlowStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.flow_dir = root / "capture"
        self.flow_dir.mkdir(parents=True, exist_ok=True)

    def arm_flow(
        self,
        chat_id: int,
        *,
        mode: CaptureMode,
        now: datetime,
        ttl_sec: int,
    ) -> CaptureFlow:
        status: CaptureStatus = {
            "one_take_text": "awaiting_text",
            "three_block": "awaiting_three_block",
            "one_take_audio": "awaiting_media",
        }[mode]
        return self.save_flow(
            CaptureFlow(
                chat_id=chat_id,
                mode=mode,
                status=status,
                created_at=now,
                expires_at=_expiry(now, ttl_sec),
            )
        )

    def save_flow(self, flow: CaptureFlow) -> CaptureFlow:
        path = self._flow_path(flow.chat_id)
        path.write_text(
            json.dumps(flow.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return flow

    def append_three_block(
        self,
        chat_id: int,
        text: str,
        *,
        now: datetime,
    ) -> CaptureFlow:
        flow = self.load_flow(chat_id, now=now)
        if flow is None or flow.mode != "three_block":
            raise ValueError("active three-block flow is required")
        value = text.strip()
        if not value:
            raise ValueError("three-block answer is required")
        return self.save_flow(
            CaptureFlow(
                chat_id=flow.chat_id,
                mode=flow.mode,
                status=flow.status,
                created_at=flow.created_at,
                expires_at=flow.expires_at,
                blocks=flow.blocks + (value,),
            )
        )

    def await_transcript_confirmation(
        self,
        chat_id: int,
        transcript_path: Path,
        *,
        now: datetime,
        ttl_sec: int | None = None,
    ) -> CaptureFlow:
        flow = self.load_flow(chat_id, now=now)
        if flow is None or flow.mode != "one_take_audio":
            raise ValueError("active audio flow is required")
        return self.save_flow(
            CaptureFlow(
                chat_id=flow.chat_id,
                mode=flow.mode,
                status="awaiting_transcript_confirmation",
                created_at=flow.created_at,
                expires_at=(
                    _expiry(now, ttl_sec)
                    if ttl_sec is not None
                    else flow.expires_at
                ),
                transcript_path=str(transcript_path),
            )
        )

    def load_flow(
        self,
        chat_id: int,
        *,
        now: datetime | None = None,
    ) -> CaptureFlow | None:
        path = self._flow_path(chat_id)
        if not path.exists():
            return None
        flow = CaptureFlow.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if flow.chat_id != chat_id:
            raise ValueError("capture flow chat id does not match path")
        if flow.expires_at <= (now or datetime.now(timezone.utc)):
            path.unlink(missing_ok=True)
            return None
        return flow

    def delete_flow(self, chat_id: int) -> None:
        self._flow_path(chat_id).unlink(missing_ok=True)

    def _flow_path(self, chat_id: int) -> Path:
        return self.flow_dir / f"chat-{chat_id}.json"


def _expiry(now: datetime, ttl_sec: int) -> datetime:
    if ttl_sec <= 0:
        raise ValueError("capture flow ttl must be positive")
    return now + timedelta(seconds=ttl_sec)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )

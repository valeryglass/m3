from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.input_funnels import InputArtifact, artifact_text
from app.schemas.intake_transcript import IntakeTranscript


SCHEMA_VERSION = "m3.intake_transcript.v1"


def transcript_text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def transcript_id_for_source(chat_id: int, message_id: int | None) -> str:
    if message_id is None:
        return f"transcript-telegram-chat-{chat_id}-message-unknown"
    return f"transcript-telegram-chat-{chat_id}-message-{message_id}"


def transcript_path(root: Path, chat_id: int, message_id: int | None) -> Path:
    message_part = "unknown" if message_id is None else str(message_id)
    return root / f"telegram-chat-{chat_id}" / f"message-{message_part}.json"


def build_intake_transcript(
    artifact: InputArtifact,
    *,
    created_at: datetime | None = None,
) -> IntakeTranscript:
    metadata: dict[str, Any] = artifact.source_ref
    chat_id = _required_int(metadata, "chat_id")
    message_id = _optional_int(metadata.get("message_id"))
    text = artifact_text(artifact).strip()
    if not text:
        raise ValueError("transcript text is required")
    provider = str(metadata.get("transcription_provider") or "unknown")
    language_value = metadata.get("transcription_language")
    language = str(language_value) if language_value else None
    timestamp = created_at or datetime.now(timezone.utc)
    return IntakeTranscript(
        schema_version=SCHEMA_VERSION,
        transcript_id=transcript_id_for_source(chat_id, message_id),
        created_at=timestamp,
        source=f"telegram-chat:{chat_id}",
        chat_id=chat_id,
        message_id=message_id,
        media_kind=artifact.media_kind,
        duration_seconds=artifact.duration_seconds,
        file_size=artifact.file_size,
        mime_type=artifact.mime_type,
        file_name=artifact.file_name,
        provider=provider,
        language=language,
        text=text,
        text_sha256=transcript_text_sha256(text),
    )


def save_intake_transcript(root: Path, transcript: IntakeTranscript) -> Path:
    path = transcript_path(root, transcript.chat_id, transcript.message_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = transcript.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_intake_transcript(path: Path) -> IntakeTranscript:
    return IntakeTranscript.model_validate_json(path.read_text(encoding="utf-8"))


def link_intake_transcript_to_episode(path: Path, episode_id: str) -> IntakeTranscript:
    transcript = load_intake_transcript(path)
    linked = transcript.model_copy(update={"episode_id": episode_id})
    save_intake_transcript(path.parents[1], linked)
    return linked


def _required_int(metadata: dict[str, Any], key: str) -> int:
    value = metadata.get(key)
    if value is None:
        raise ValueError(f"{key} is required")
    return int(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)

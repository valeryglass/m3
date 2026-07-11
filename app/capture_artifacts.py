from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.schemas.capture import (
    CaptureArtifact,
    CaptureMode,
    CapturePiece,
    CapturePieceRole,
)
from app.runtime_storage import atomic_write_json


def capture_text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def capture_id_for(
    *,
    chat_id: int,
    mode: CaptureMode,
    created_at: datetime,
    message_id: int | None = None,
) -> str:
    timestamp = (
        created_at.astimezone(timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y%m%dT%H%M%SZ")
        .lower()
    )
    suffix = str(message_id) if message_id is not None else "nomessage"
    return f"capture-{mode.replace('_', '-')}-{chat_id}-{timestamp}-{suffix}"


def build_capture_artifact(
    *,
    chat_id: int,
    mode: CaptureMode,
    media_kind: str,
    pieces: Iterable[tuple[CapturePieceRole, str]],
    created_at: datetime,
    message_id: int | None = None,
    source_metadata: dict[str, str | int | None] | None = None,
    intake_transcript_path: str | None = None,
) -> CaptureArtifact:
    normalized_pieces = tuple(
        CapturePiece(
            role=role,
            text=text,
            text_sha256=capture_text_sha256(text),
        )
        for role, text in pieces
    )
    metadata = dict(source_metadata or {})
    if message_id is not None:
        metadata.setdefault("message_id", message_id)
    return CaptureArtifact(
        capture_id=capture_id_for(
            chat_id=chat_id,
            mode=mode,
            created_at=created_at,
            message_id=message_id,
        ),
        created_at=created_at,
        source=f"telegram-chat:{chat_id}",
        chat_id=chat_id,
        mode=mode,
        media_kind=media_kind,
        pieces=normalized_pieces,
        source_metadata=metadata,
        intake_transcript_path=intake_transcript_path,
    )


def capture_artifact_path(root: Path, artifact: CaptureArtifact) -> Path:
    return root / f"telegram-chat-{artifact.chat_id}" / f"{artifact.capture_id}.json"


def save_capture_artifact(root: Path, artifact: CaptureArtifact) -> Path:
    path = capture_artifact_path(root, artifact)
    atomic_write_json(
        path,
        artifact.model_dump(mode="json"),
        sort_keys=True,
    )
    return path


def load_capture_artifact(path: Path) -> CaptureArtifact:
    return CaptureArtifact.model_validate_json(path.read_text(encoding="utf-8"))

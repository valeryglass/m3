from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MEDIA_KIND_TEXT = "text"
MEDIA_KIND_VOICE = "voice"
MEDIA_KIND_AUDIO = "audio"
MEDIA_KIND_DOCUMENT = "document"

SUPPORTED_MEDIA_KINDS = frozenset(
    {
        MEDIA_KIND_TEXT,
        MEDIA_KIND_VOICE,
        MEDIA_KIND_AUDIO,
        MEDIA_KIND_DOCUMENT,
    }
)


@dataclass(frozen=True)
class InputArtifact:
    source: str
    media_kind: str
    raw_text: str | None = None
    transcript: str | None = None
    source_ref: dict[str, Any] = field(default_factory=dict)
    file_id: str | None = None
    duration_seconds: int | None = None
    mime_type: str | None = None
    file_size: int | None = None
    file_name: str | None = None

    def __post_init__(self) -> None:
        if self.media_kind not in SUPPORTED_MEDIA_KINDS:
            raise ValueError(f"Unsupported media kind: {self.media_kind}")


def text_input_artifact(
    text: str,
    *,
    source: str = "telegram",
    source_ref: dict[str, Any] | None = None,
) -> InputArtifact:
    return InputArtifact(
        source=source,
        media_kind=MEDIA_KIND_TEXT,
        raw_text=text,
        source_ref=dict(source_ref or {}),
    )


def voice_input_artifact(
    file_id: str,
    *,
    source: str = "telegram",
    source_ref: dict[str, Any] | None = None,
    transcript: str | None = None,
    duration_seconds: int | None = None,
    mime_type: str | None = None,
    file_size: int | None = None,
) -> InputArtifact:
    if not file_id:
        raise ValueError("voice file_id is required")
    return InputArtifact(
        source=source,
        media_kind=MEDIA_KIND_VOICE,
        transcript=transcript,
        source_ref=dict(source_ref or {}),
        file_id=file_id,
        duration_seconds=duration_seconds,
        mime_type=mime_type,
        file_size=file_size,
    )



def audio_input_artifact(
    file_id: str,
    *,
    source: str = "telegram",
    source_ref: dict[str, Any] | None = None,
    transcript: str | None = None,
    duration_seconds: int | None = None,
    mime_type: str | None = None,
    file_size: int | None = None,
    file_name: str | None = None,
) -> InputArtifact:
    if not file_id:
        raise ValueError("audio file_id is required")
    return InputArtifact(
        source=source,
        media_kind=MEDIA_KIND_AUDIO,
        transcript=transcript,
        source_ref=dict(source_ref or {}),
        file_id=file_id,
        duration_seconds=duration_seconds,
        mime_type=mime_type,
        file_size=file_size,
        file_name=file_name,
    )


def audio_document_input_artifact(
    file_id: str,
    *,
    source: str = "telegram",
    source_ref: dict[str, Any] | None = None,
    transcript: str | None = None,
    mime_type: str | None = None,
    file_size: int | None = None,
    file_name: str | None = None,
) -> InputArtifact:
    if not file_id:
        raise ValueError("document file_id is required")
    if not (mime_type or "").startswith("audio/"):
        raise ValueError("audio document mime_type is required")
    return InputArtifact(
        source=source,
        media_kind=MEDIA_KIND_DOCUMENT,
        transcript=transcript,
        source_ref=dict(source_ref or {}),
        file_id=file_id,
        mime_type=mime_type,
        file_size=file_size,
        file_name=file_name,
    )

def artifact_text(artifact: InputArtifact) -> str:
    if artifact.transcript is not None:
        return artifact.transcript
    if artifact.raw_text is not None:
        return artifact.raw_text
    return ""

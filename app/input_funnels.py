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
    duration_seconds: int | None = None
    mime_type: str | None = None
    file_size: int | None = None

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


def artifact_text(artifact: InputArtifact) -> str:
    if artifact.transcript is not None:
        return artifact.transcript
    if artifact.raw_text is not None:
        return artifact.raw_text
    return ""

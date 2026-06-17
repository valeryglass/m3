from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MediaKind = Literal["voice", "audio", "document"]
TranscriptStatus = Literal["transcribed"]


class IntakeTranscript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="m3.intake_transcript.v1")
    transcript_id: str = Field(min_length=1)
    created_at: datetime
    source: str = Field(min_length=1)
    chat_id: int
    message_id: int | None = None
    media_kind: MediaKind
    duration_seconds: int | None = Field(default=None, ge=0)
    file_size: int | None = Field(default=None, ge=0)
    mime_type: str | None = None
    file_name: str | None = None
    provider: str = Field(min_length=1)
    language: str | None = None
    text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: TranscriptStatus = "transcribed"
    episode_id: str | None = None

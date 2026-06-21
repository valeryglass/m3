from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.episode import ObservedField


CaptureMode = Literal[
    "classic_10q",
    "three_block",
    "one_take_text",
    "one_take_audio",
]
ObservedFieldName = Literal[
    "situation",
    "trigger",
    "actor",
    "quote",
    "automatic_thought",
    "emotion",
    "behavior",
    "physical",
    "short_term_consequence",
    "long_term_consequence",
]
CapturePieceRole = Literal[
    "situation",
    "trigger",
    "actor",
    "quote",
    "automatic_thought",
    "emotion",
    "behavior",
    "physical",
    "short_term_consequence",
    "long_term_consequence",
    "outside_context",
    "inner_context",
    "response_outcome",
    "one_take_text",
    "transcript",
]
ExtractionStatus = Literal["succeeded", "failed"]
ExtractionFailureCode = Literal[
    "provider_unavailable",
    "provider_error",
    "provider_timeout",
    "refusal",
    "incomplete",
    "content_filtered",
    "missing_output",
    "invalid_schema",
    "insufficient_evidence",
    "invalid_source_quote",
    "invalid_piece_role",
]


class CapturePiece(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: CapturePieceRole
    text: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_text(self):
        if not self.text.strip():
            raise ValueError("capture piece text is required")
        return self


class CaptureArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["m3.capture_artifact.v1"] = "m3.capture_artifact.v1"
    capture_id: str = Field(pattern=r"^capture-[a-z0-9-]+$")
    created_at: datetime
    source: str = Field(min_length=1)
    chat_id: int
    mode: CaptureMode
    media_kind: str = Field(min_length=1)
    pieces: tuple[CapturePiece, ...]
    source_metadata: dict[str, str | int | None] = Field(default_factory=dict)
    intake_transcript_path: str | None = None

    @model_validator(mode="after")
    def validate_mode_pieces(self):
        if not self.pieces:
            raise ValueError("capture artifact requires evidence pieces")
        roles = tuple(piece.role for piece in self.pieces)
        expected = {
            "three_block": (
                "outside_context",
                "inner_context",
                "response_outcome",
            ),
            "one_take_text": ("one_take_text",),
            "one_take_audio": ("transcript",),
        }
        if self.mode in expected and roles != expected[self.mode]:
            raise ValueError("capture piece roles do not match mode")
        if self.mode == "classic_10q":
            required = {
                "situation",
                "automatic_thought",
                "emotion",
                "behavior",
                "physical",
                "short_term_consequence",
                "long_term_consequence",
            }
            if not required <= set(roles) or len(roles) != len(set(roles)):
                raise ValueError("classic capture requires unique observed field roles")
        forbidden = {"file_id", "raw_audio_path", "raw_audio"}
        if forbidden & set(self.source_metadata):
            raise ValueError("capture metadata contains prohibited media references")
        return self


class ExtractedObservedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)
    source_piece_role: CapturePieceRole
    confidence: float = Field(ge=0.0, le=1.0)

    def observed_field(self) -> ObservedField:
        return ObservedField(value=self.value, source_quote=self.source_quote)


class CaptureExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    situation: ExtractedObservedField
    trigger: ExtractedObservedField | None
    actor: ExtractedObservedField | None
    quote: ExtractedObservedField | None
    automatic_thought: ExtractedObservedField
    emotion: ExtractedObservedField
    behavior: ExtractedObservedField
    physical: ExtractedObservedField
    short_term_consequence: ExtractedObservedField
    long_term_consequence: ExtractedObservedField

    def observed_dict(self) -> dict[str, dict[str, str]]:
        observed: dict[str, dict[str, str]] = {}
        for field_name, field_value in self:
            if field_value is not None:
                observed[field_name] = field_value.observed_field().model_dump()
        return observed


class CaptureExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["m3.capture_extraction.v1"] = "m3.capture_extraction.v1"
    extraction_id: str = Field(pattern=r"^extraction-capture-[a-z0-9-]+$")
    capture_id: str = Field(pattern=r"^capture-[a-z0-9-]+$")
    created_at: datetime
    status: ExtractionStatus
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    result: CaptureExtractionResult | None = None
    failure_code: ExtractionFailureCode | None = None
    episode_id: str | None = Field(
        default=None,
        pattern=r"^episode-[0-9]{8}-[0-9]+$",
    )

    @model_validator(mode="after")
    def validate_status_payload(self):
        if self.status == "succeeded":
            if self.result is None or self.failure_code is not None:
                raise ValueError("successful extraction requires only a result")
        elif self.result is not None or self.failure_code is None:
            raise ValueError("failed extraction requires only a failure code")
        return self

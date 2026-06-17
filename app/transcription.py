from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from app.input_funnels import InputArtifact, artifact_text
from app.telegram_media import DownloadedTelegramMedia


class TranscriptionUnavailable(RuntimeError):
    """Raised when no transcription provider is available for an audio artifact."""


class TranscriptionFailed(RuntimeError):
    """Raised when a configured provider fails to produce usable transcript text."""


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str | None = None
    provider: str | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("transcript text is required")


class TranscriptionProvider(Protocol):
    def transcribe(self, media: DownloadedTelegramMedia) -> TranscriptResult:
        """Return transcript text for a temporary media download."""


def attach_transcript(
    artifact: InputArtifact,
    transcript: TranscriptResult,
) -> InputArtifact:
    source_ref = dict(artifact.source_ref)
    if transcript.provider:
        source_ref["transcription_provider"] = transcript.provider
    if transcript.language:
        source_ref["transcription_language"] = transcript.language
    return replace(artifact, transcript=transcript.text.strip(), source_ref=source_ref)


def transcribe_and_attach(
    provider: TranscriptionProvider,
    artifact: InputArtifact,
    media: DownloadedTelegramMedia,
) -> InputArtifact:
    if not requires_transcription(artifact):
        return artifact
    return attach_transcript(artifact, provider.transcribe(media))


def requires_transcription(artifact: InputArtifact) -> bool:
    return artifact_text(artifact).strip() == "" and artifact.file_id is not None


class MissingTranscriptionProvider:
    def transcribe(self, media: DownloadedTelegramMedia | InputArtifact) -> TranscriptResult:
        raise TranscriptionUnavailable("No transcription provider is configured")

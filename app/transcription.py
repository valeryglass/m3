from __future__ import annotations

from dataclasses import dataclass, replace

from app.input_funnels import InputArtifact, artifact_text


class TranscriptionUnavailable(RuntimeError):
    """Raised when no transcription provider is available for an audio artifact."""


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str | None = None
    provider: str | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("transcript text is required")


def attach_transcript(
    artifact: InputArtifact,
    transcript: TranscriptResult,
) -> InputArtifact:
    return replace(artifact, transcript=transcript.text.strip())


def requires_transcription(artifact: InputArtifact) -> bool:
    return artifact_text(artifact).strip() == "" and artifact.file_id is not None


class MissingTranscriptionProvider:
    def transcribe(self, artifact: InputArtifact) -> TranscriptResult:
        raise TranscriptionUnavailable("No transcription provider is configured")

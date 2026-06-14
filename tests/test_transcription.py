import pytest

from app.input_funnels import text_input_artifact, voice_input_artifact
from app.transcription import (
    MissingTranscriptionProvider,
    TranscriptResult,
    TranscriptionUnavailable,
    attach_transcript,
    requires_transcription,
)


def test_transcript_result_requires_text():
    with pytest.raises(ValueError, match="transcript text is required"):
        TranscriptResult("   ")


def test_attach_transcript_returns_artifact_with_support_text():
    artifact = voice_input_artifact("voice-file-id", duration_seconds=5)

    transcribed = attach_transcript(
        artifact,
        TranscriptResult("  spoken episode  ", language="ru", provider="manual"),
    )

    assert transcribed.file_id == "voice-file-id"
    assert transcribed.duration_seconds == 5
    assert transcribed.transcript == "spoken episode"
    assert artifact.transcript is None


def test_requires_transcription_only_for_file_artifacts_without_text():
    assert requires_transcription(voice_input_artifact("voice-file-id")) is True
    assert (
        requires_transcription(
            voice_input_artifact("voice-file-id", transcript="spoken episode")
        )
        is False
    )
    assert requires_transcription(text_input_artifact("typed episode")) is False


def test_missing_transcription_provider_fails_explicitly():
    provider = MissingTranscriptionProvider()

    with pytest.raises(TranscriptionUnavailable, match="No transcription provider"):
        provider.transcribe(voice_input_artifact("voice-file-id"))

import pytest

from app.input_funnels import text_input_artifact, voice_input_artifact
from app.telegram_media import DownloadedTelegramMedia, TelegramMediaRequest
from app.transcription import (
    MissingTranscriptionProvider,
    TranscriptResult,
    TranscriptionUnavailable,
    attach_transcript,
    requires_transcription,
    transcribe_and_attach,
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


class _StaticProvider:
    def transcribe(self, media: DownloadedTelegramMedia) -> TranscriptResult:
        assert media.path.name == "voice.ogg"
        return TranscriptResult("spoken from media", language="ru", provider="fake")


def test_transcribe_and_attach_uses_provider_result(tmp_path):
    media_path = tmp_path / "voice.ogg"
    media_path.write_bytes(b"voice")
    media = DownloadedTelegramMedia(
        path=media_path,
        request=TelegramMediaRequest(file_id="voice-file-id", media_kind="voice"),
        file_size=5,
    )
    artifact = voice_input_artifact("voice-file-id")

    transcribed = transcribe_and_attach(_StaticProvider(), artifact, media)

    assert transcribed.transcript == "spoken from media"


def test_transcribe_and_attach_leaves_existing_transcript_unchanged(tmp_path):
    media_path = tmp_path / "voice.ogg"
    media_path.write_bytes(b"voice")
    media = DownloadedTelegramMedia(
        path=media_path,
        request=TelegramMediaRequest(file_id="voice-file-id", media_kind="voice"),
        file_size=5,
    )
    artifact = voice_input_artifact("voice-file-id", transcript="already done")

    transcribed = transcribe_and_attach(_StaticProvider(), artifact, media)

    assert transcribed is artifact

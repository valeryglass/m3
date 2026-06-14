import pytest

from app.input_funnels import (
    MEDIA_KIND_AUDIO,
    MEDIA_KIND_DOCUMENT,
    MEDIA_KIND_TEXT,
    MEDIA_KIND_VOICE,
    SUPPORTED_MEDIA_KINDS,
    InputArtifact,
    artifact_text,
    audio_document_input_artifact,
    audio_input_artifact,
    text_input_artifact,
    voice_input_artifact,
)


def test_text_input_artifact_preserves_text_and_source_metadata():
    artifact = text_input_artifact(
        "hello",
        source_ref={"chat_id": 123, "message_id": 456},
    )

    assert artifact.source == "telegram"
    assert artifact.media_kind == MEDIA_KIND_TEXT
    assert artifact.raw_text == "hello"
    assert artifact.transcript is None
    assert artifact.source_ref == {"chat_id": 123, "message_id": 456}


def test_text_input_artifact_copies_source_ref():
    source_ref = {"chat_id": 123}
    artifact = text_input_artifact("hello", source_ref=source_ref)
    source_ref["chat_id"] = 456

    assert artifact.source_ref == {"chat_id": 123}


def test_voice_input_artifact_preserves_file_metadata_without_raw_audio():
    artifact = voice_input_artifact(
        "voice-file-id",
        source_ref={"chat_id": 123, "message_id": 456},
        duration_seconds=7,
        mime_type="audio/ogg",
        file_size=2048,
    )

    assert artifact.source == "telegram"
    assert artifact.media_kind == MEDIA_KIND_VOICE
    assert artifact.file_id == "voice-file-id"
    assert artifact.duration_seconds == 7
    assert artifact.mime_type == "audio/ogg"
    assert artifact.file_size == 2048
    assert artifact.raw_text is None
    assert artifact.transcript is None
    assert artifact.source_ref == {"chat_id": 123, "message_id": 456}


def test_voice_input_artifact_can_hold_transcript_as_support_text():
    artifact = voice_input_artifact("voice-file-id", transcript="voice transcript")

    assert artifact_text(artifact) == "voice transcript"


def test_voice_input_artifact_requires_file_id():
    with pytest.raises(ValueError, match="voice file_id is required"):
        voice_input_artifact("")


def test_audio_input_artifact_preserves_uploaded_audio_metadata():
    artifact = audio_input_artifact(
        "audio-file-id",
        source_ref={"chat_id": 123},
        duration_seconds=42,
        mime_type="audio/mpeg",
        file_size=8192,
        file_name="note.mp3",
    )

    assert artifact.media_kind == MEDIA_KIND_AUDIO
    assert artifact.file_id == "audio-file-id"
    assert artifact.duration_seconds == 42
    assert artifact.mime_type == "audio/mpeg"
    assert artifact.file_size == 8192
    assert artifact.file_name == "note.mp3"
    assert artifact.source_ref == {"chat_id": 123}


def test_audio_input_artifact_requires_file_id():
    with pytest.raises(ValueError, match="audio file_id is required"):
        audio_input_artifact("")


def test_audio_document_input_artifact_requires_audio_mime_type():
    artifact = audio_document_input_artifact(
        "document-file-id",
        mime_type="audio/ogg",
        file_name="voice.ogg",
        file_size=4096,
    )

    assert artifact.media_kind == MEDIA_KIND_DOCUMENT
    assert artifact.file_id == "document-file-id"
    assert artifact.mime_type == "audio/ogg"
    assert artifact.file_name == "voice.ogg"
    assert artifact.file_size == 4096

    with pytest.raises(ValueError, match="audio document mime_type is required"):
        audio_document_input_artifact("document-file-id", mime_type="application/pdf")


def test_audio_document_input_artifact_requires_file_id():
    with pytest.raises(ValueError, match="document file_id is required"):
        audio_document_input_artifact("", mime_type="audio/ogg")

def test_artifact_text_prefers_transcript_over_raw_text():
    artifact = InputArtifact(
        source="telegram",
        media_kind=MEDIA_KIND_VOICE,
        raw_text="caption",
        transcript="voice transcript",
    )

    assert artifact_text(artifact) == "voice transcript"


def test_artifact_text_falls_back_to_raw_text_or_empty_string():
    assert artifact_text(text_input_artifact("hello")) == "hello"
    assert artifact_text(InputArtifact(source="telegram", media_kind=MEDIA_KIND_AUDIO)) == ""


def test_supported_media_kinds_cover_planned_audio_funnels():
    assert SUPPORTED_MEDIA_KINDS == {
        MEDIA_KIND_TEXT,
        MEDIA_KIND_VOICE,
        MEDIA_KIND_AUDIO,
        MEDIA_KIND_DOCUMENT,
    }


def test_input_artifact_rejects_unknown_media_kind():
    with pytest.raises(ValueError, match="Unsupported media kind"):
        InputArtifact(source="telegram", media_kind="photo")

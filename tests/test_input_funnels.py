import pytest

from app.input_funnels import (
    MEDIA_KIND_AUDIO,
    MEDIA_KIND_DOCUMENT,
    MEDIA_KIND_TEXT,
    MEDIA_KIND_VOICE,
    SUPPORTED_MEDIA_KINDS,
    InputArtifact,
    artifact_text,
    text_input_artifact,
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

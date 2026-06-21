from datetime import datetime, timezone

from app.input_funnels import voice_input_artifact
from app.intake_transcripts import (
    build_intake_transcript,
    link_intake_transcript_to_episode,
    load_intake_transcript,
    save_intake_transcript,
    transcript_path,
    transcript_text_sha256,
)


def _artifact():
    return voice_input_artifact(
        "telegram-file-id",
        source_ref={
            "chat_id": 225672,
            "message_id": 42,
            "message_kind": "voice",
            "transcription_provider": "whisper-cli",
            "transcription_language": "ru",
        },
        transcript="расшифрованный голос",
        duration_seconds=5,
        mime_type="audio/ogg",
        file_size=12345,
    )


def test_build_intake_transcript_excludes_raw_audio_references():
    created_at = datetime(2026, 6, 17, tzinfo=timezone.utc)
    transcript = build_intake_transcript(_artifact(), created_at=created_at)
    payload = transcript.model_dump(mode="json")

    assert transcript.schema_version == "m3.intake_transcript.v1"
    assert transcript.transcript_id == "transcript-telegram-chat-225672-message-42"
    assert transcript.created_at == created_at
    assert transcript.source == "telegram-chat:225672"
    assert transcript.chat_id == 225672
    assert transcript.message_id == 42
    assert transcript.media_kind == "voice"
    assert transcript.duration_seconds == 5
    assert transcript.file_size == 12345
    assert transcript.mime_type == "audio/ogg"
    assert transcript.provider == "whisper-cli"
    assert transcript.language == "ru"
    assert transcript.text == "расшифрованный голос"
    assert transcript.text_sha256 == transcript_text_sha256("расшифрованный голос")
    assert "file_id" not in payload
    assert "raw_audio_path" not in payload


def test_save_and_load_intake_transcript_uses_deterministic_path(tmp_path):
    transcript = build_intake_transcript(_artifact())
    path = save_intake_transcript(tmp_path, transcript)

    assert path == tmp_path / "telegram-chat-225672" / "message-42.json"
    assert path == transcript_path(tmp_path, 225672, 42)
    assert load_intake_transcript(path) == transcript


def test_save_intake_transcript_overwrites_same_source_without_duplicate(tmp_path):
    transcript = build_intake_transcript(_artifact())

    first = save_intake_transcript(tmp_path, transcript)
    second = save_intake_transcript(tmp_path, transcript)

    assert first == second
    assert list((tmp_path / "telegram-chat-225672").glob("*.json")) == [first]


def test_link_intake_transcript_to_episode_updates_existing_artifact(tmp_path):
    path = save_intake_transcript(tmp_path, build_intake_transcript(_artifact()))

    linked = link_intake_transcript_to_episode(path, "episode-20260621-1")

    assert linked.episode_id == "episode-20260621-1"
    assert load_intake_transcript(path).episode_id == "episode-20260621-1"

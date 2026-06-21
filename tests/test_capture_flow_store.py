import json
from datetime import datetime, timedelta, timezone

import pytest

from app.capture_flow_store import CaptureFlowStore


NOW = datetime(2026, 6, 21, 9, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("mode", "status"),
    [
        ("one_take_text", "awaiting_text"),
        ("three_block", "awaiting_three_block"),
        ("one_take_audio", "awaiting_media"),
    ],
)
def test_arm_and_reload_capture_modes(tmp_path, mode, status):
    store = CaptureFlowStore(tmp_path)

    flow = store.arm_flow(123, mode=mode, now=NOW, ttl_sec=600)

    assert flow.mode == mode
    assert flow.status == status
    assert store.load_flow(123, now=NOW) == flow


def test_three_block_progress_survives_reload(tmp_path):
    store = CaptureFlowStore(tmp_path)
    store.arm_flow(123, mode="three_block", now=NOW, ttl_sec=600)

    first = store.append_three_block(123, "что случилось", now=NOW)
    second = store.append_three_block(123, "что было внутри", now=NOW)

    assert first.blocks == ("что случилось",)
    assert second.blocks == ("что случилось", "что было внутри")
    assert store.load_flow(123, now=NOW) == second


def test_audio_flow_can_wait_for_transcript_confirmation(tmp_path):
    store = CaptureFlowStore(tmp_path)
    store.arm_flow(123, mode="one_take_audio", now=NOW, ttl_sec=600)
    transcript_path = tmp_path / "intake-transcripts" / "message-1.json"

    flow = store.await_transcript_confirmation(
        123, transcript_path, now=NOW
    )

    assert flow.status == "awaiting_transcript_confirmation"
    assert flow.transcript_path == str(transcript_path)


def test_expired_capture_flow_is_removed(tmp_path):
    store = CaptureFlowStore(tmp_path)
    store.arm_flow(123, mode="one_take_text", now=NOW, ttl_sec=600)

    assert store.load_flow(123, now=NOW + timedelta(seconds=601)) is None
    assert not (store.flow_dir / "chat-123.json").exists()


def test_legacy_audio_flow_file_remains_readable(tmp_path):
    legacy_dir = tmp_path / "audio-one-take"
    legacy_dir.mkdir()
    (legacy_dir / "chat-123.json").write_text(
        json.dumps(
            {
                "chat_id": 123,
                "created_at": "2026-06-21T09:00:00Z",
                "expires_at": "2026-06-21T09:10:00Z",
                "flow": "audio_one_take",
                "status": "awaiting_media",
            }
        ),
        encoding="utf-8",
    )

    flow = CaptureFlowStore(tmp_path).load_flow(123, now=NOW)

    assert flow is not None
    assert flow.mode == "one_take_audio"
    assert flow.status == "awaiting_media"

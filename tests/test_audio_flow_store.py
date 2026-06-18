from datetime import datetime, timedelta, timezone

import pytest

from app.audio_flow_store import AudioFlowStore


NOW = datetime(2026, 6, 18, 9, 0, tzinfo=timezone.utc)


def test_arm_load_and_delete_audio_flow(tmp_path):
    store = AudioFlowStore(tmp_path / "runtime-flows")

    armed = store.arm_flow(123, now=NOW, ttl_sec=600)

    assert armed.flow == "audio_one_take"
    assert armed.status == "awaiting_media"
    assert armed.expires_at == NOW + timedelta(seconds=600)
    assert store.load_flow(123, now=NOW) == armed

    store.delete_flow(123)
    assert store.load_flow(123, now=NOW) is None


def test_expired_audio_flow_is_deleted(tmp_path):
    store = AudioFlowStore(tmp_path / "runtime-flows")
    store.arm_flow(123, now=NOW, ttl_sec=600)

    assert store.load_flow(123, now=NOW + timedelta(seconds=601)) is None
    assert not (store.flow_dir / "chat-123.json").exists()


def test_audio_flow_ttl_must_be_positive(tmp_path):
    store = AudioFlowStore(tmp_path / "runtime-flows")

    with pytest.raises(ValueError, match="ttl"):
        store.arm_flow(123, now=NOW, ttl_sec=0)

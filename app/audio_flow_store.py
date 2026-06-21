from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.capture_flow_store import CaptureFlow, CaptureFlowStore


AudioOneTakeFlow = CaptureFlow


class AudioFlowStore(CaptureFlowStore):
    """Compatibility facade for callers that still use the audio-only name."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.flow_dir = self.legacy_audio_flow_dir
        self.flow_dir.mkdir(parents=True, exist_ok=True)

    def arm_flow(
        self,
        chat_id: int,
        *,
        mode: str = "one_take_audio",
        now: datetime,
        ttl_sec: int,
    ) -> CaptureFlow:
        if mode != "one_take_audio":
            raise ValueError("AudioFlowStore only supports one_take_audio")
        flow = super().arm_flow(
            chat_id,
            mode=mode,
            now=now,
            ttl_sec=ttl_sec,
        )
        return flow

    def _flow_path(self, chat_id: int) -> Path:
        return self.legacy_audio_flow_dir / f"chat-{chat_id}.json"

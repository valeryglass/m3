from __future__ import annotations

import json
from pathlib import Path

from app.loop_extractor import LoopSession
from app.runtime_storage import atomic_write_json, locked_unlink


class LoopSessionStore:
    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def load_session(self, chat_id: int) -> LoopSession | None:
        path = self._session_path(chat_id)
        if not path.exists():
            return None
        return LoopSession.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_session(self, session: LoopSession) -> None:
        atomic_write_json(self._session_path(session.chat_id), session.to_dict())

    def delete_session(self, chat_id: int) -> None:
        locked_unlink(self._session_path(chat_id))

    def _session_path(self, chat_id: int) -> Path:
        return self.session_dir / f"chat-{chat_id}.json"

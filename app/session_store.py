from __future__ import annotations

import json
from pathlib import Path

from app.loop_extractor import LoopSession


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
        self._session_path(session.chat_id).write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def delete_session(self, chat_id: int) -> None:
        self._session_path(chat_id).unlink(missing_ok=True)

    def _session_path(self, chat_id: int) -> Path:
        return self.session_dir / f"chat-{chat_id}.json"

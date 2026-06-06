from __future__ import annotations

import json
import re
from pathlib import Path

from app.derived_normalizer import normalize_episode
from app.loop_extractor import LoopSession
from app.schemas.episode import Episode, Observed


EPISODE_RE = re.compile(r"^episode-(?P<date>[0-9]{8})-(?P<n>[0-9]+)\.json$")


class JsonStorage:
    def __init__(self, episode_dir: Path, state_dir: Path) -> None:
        self.episode_dir = episode_dir
        self.state_dir = state_dir
        self.episode_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

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

    def save_episode(self, session: LoopSession) -> Path:
        if session.episode_date is None:
            raise ValueError("Cannot save episode without episode date")

        episode_date = session.episode_date
        episode_id = self.next_episode_id(episode_date)
        data, _ = normalize_episode(
            {
                "id": episode_id,
                "date": episode_date,
                "source": f"telegram-chat:{session.chat_id}",
                "observed": session.observed,
            }
        )
        episode = Episode(
            id=episode_id,
            date=episode_date,
            source=f"telegram-chat:{session.chat_id}",
            observed=Observed.model_validate(data["observed"]),
        )
        persisted = episode.model_dump(mode="json", exclude={"derived"})
        path = self.episode_dir / f"{episode_id}.json"
        path.write_text(
            json.dumps(persisted, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        session.saved_episode_path = str(path)
        return path

    def episode_count_for_chat(self, chat_id: int) -> int:
        source = f"telegram-chat:{chat_id}"
        count = 0
        for path in self.episode_dir.glob("episode-*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("source") == source:
                count += 1
        return count

    def next_episode_id(self, episode_date: str) -> str:
        compact_date = episode_date.replace("-", "")
        max_n = 0
        for path in self.episode_dir.glob(f"episode-{compact_date}-*.json"):
            match = EPISODE_RE.match(path.name)
            if match:
                max_n = max(max_n, int(match.group("n")))
        return f"episode-{compact_date}-{max_n + 1}"

    def _session_path(self, chat_id: int) -> Path:
        return self.state_dir / f"chat-{chat_id}.json"

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only before deps install
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_allowed_chat_ids: frozenset[int]
    telegram_admin_chat_id: int | None
    episode_dir: Path
    state_dir: Path
    userlist_path: Path
    ux_event_log: Path
    ux_idle_after_sec: int
    initial_session_ttl_sec: int
    tone_config: Path


def parse_allowed_chat_ids(value: str) -> frozenset[int]:
    ids: set[int] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        ids.add(int(item))
    return frozenset(ids)


def parse_optional_chat_id(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value.strip())


def admin_chat_id_for_settings(settings: Settings) -> int | None:
    if settings.telegram_admin_chat_id is not None:
        return settings.telegram_admin_chat_id
    if not settings.telegram_allowed_chat_ids:
        return None
    return sorted(
        settings.telegram_allowed_chat_ids,
        key=lambda item: (len(str(abs(item))), item),
    )[0]


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None and load_dotenv is not None:
        load_dotenv()

    source = env if env is not None else os.environ
    token = source.get("TELEGRAM_BOT_TOKEN", "").strip()
    allowed_chat_ids = parse_allowed_chat_ids(
        source.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
    )

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    return Settings(
        telegram_bot_token=token,
        telegram_allowed_chat_ids=allowed_chat_ids,
        telegram_admin_chat_id=parse_optional_chat_id(
            source.get("M3_TELEGRAM_ADMIN_CHAT_ID")
        ),
        episode_dir=Path(source.get("M3_EPISODE_DIR", "data/episodes")),
        state_dir=Path(source.get("M3_STATE_DIR", "data/state")),
        userlist_path=Path(source.get("M3_USERLIST_PATH", "data/userlist/users.json")),
        ux_event_log=Path(source.get("M3_UX_EVENT_LOG", "data/ux-events/events.jsonl")),
        ux_idle_after_sec=int(source.get("M3_UX_IDLE_AFTER_SEC", "7200")),
        initial_session_ttl_sec=int(source.get("M3_INITIAL_SESSION_TTL_SEC", "600")),
        tone_config=Path(source.get("M3_TONE_CONFIG", "config/tone.yaml")),
    )

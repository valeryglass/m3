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
    episode_dir: Path
    state_dir: Path
    ux_event_log: Path
    ux_idle_after_sec: int
    initial_session_ttl_sec: int


def parse_allowed_chat_ids(value: str) -> frozenset[int]:
    ids: set[int] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        ids.add(int(item))
    return frozenset(ids)


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
        episode_dir=Path(source.get("M3_EPISODE_DIR", "data/episodes")),
        state_dir=Path(source.get("M3_STATE_DIR", "data/state")),
        ux_event_log=Path(source.get("M3_UX_EVENT_LOG", "data/ux-events/events.jsonl")),
        ux_idle_after_sec=int(source.get("M3_UX_IDLE_AFTER_SEC", "7200")),
        initial_session_ttl_sec=int(source.get("M3_INITIAL_SESSION_TTL_SEC", "600")),
    )

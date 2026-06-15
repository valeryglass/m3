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
    telegram_admin_chat_ids: frozenset[int]
    telegram_owner_chat_id: int | None
    episode_dir: Path
    runtime_session_dir: Path
    userlist_path: Path
    ux_event_log: Path
    annotation_run_dir: Path | None
    annotation_run_root: Path
    report_min_count: int
    ux_idle_after_sec: int
    initial_session_ttl_sec: int
    tone_config: Path
    audio_temp_dir: Path
    audio_max_duration_sec: int
    audio_max_file_size_bytes: int
    transcription_provider: str
    whisper_command: str
    whisper_model: str | None
    whisper_language: str | None


def parse_chat_ids(value: str) -> frozenset[int]:
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


def admin_chat_ids_for_settings(settings: Settings) -> frozenset[int]:
    return settings.telegram_admin_chat_ids


def owner_chat_id_for_settings(settings: Settings) -> int | None:
    return settings.telegram_owner_chat_id


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None and load_dotenv is not None:
        load_dotenv()

    source = env if env is not None else os.environ
    token = source.get("TELEGRAM_BOT_TOKEN", "").strip()

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    return Settings(
        telegram_bot_token=token,
        telegram_admin_chat_ids=parse_chat_ids(
            source.get("M3_TELEGRAM_ADMIN_CHAT_IDS", "")
        ),
        telegram_owner_chat_id=parse_optional_chat_id(
            source.get("M3_TELEGRAM_OWNER_CHAT_ID")
        ),
        episode_dir=Path(source.get("M3_EPISODE_DIR", "data/episodes")),
        runtime_session_dir=Path(
            source.get("M3_RUNTIME_SESSION_DIR", "data/runtime-sessions")
        ),
        userlist_path=Path(source.get("M3_USERLIST_PATH", "data/userlist/users.json")),
        ux_event_log=Path(source.get("M3_UX_EVENT_LOG", "data/ux-events/events.jsonl")),
        annotation_run_dir=(
            Path(source["M3_ANNOTATION_RUN_DIR"])
            if source.get("M3_ANNOTATION_RUN_DIR", "").strip()
            else None
        ),
        annotation_run_root=Path(
            source.get("M3_ANNOTATION_RUN_ROOT", "data/annotation-runs")
        ),
        report_min_count=int(source.get("M3_REPORT_MIN_COUNT", "2")),
        ux_idle_after_sec=int(source.get("M3_UX_IDLE_AFTER_SEC", "7200")),
        initial_session_ttl_sec=int(source.get("M3_INITIAL_SESSION_TTL_SEC", "600")),
        tone_config=Path(source.get("M3_TONE_CONFIG", "config/tone.yaml")),
        audio_temp_dir=Path(source.get("M3_AUDIO_TEMP_DIR", "data/runtime-audio")),
        audio_max_duration_sec=int(source.get("M3_AUDIO_MAX_DURATION_SEC", "300")),
        audio_max_file_size_bytes=int(
            source.get("M3_AUDIO_MAX_FILE_SIZE_BYTES", str(20 * 1024 * 1024))
        ),
        transcription_provider=source.get("M3_TRANSCRIPTION_PROVIDER", "whisper").strip().lower(),
        whisper_command=source.get("M3_WHISPER_COMMAND", "whisper").strip() or "whisper",
        whisper_model=(
            source.get("M3_WHISPER_MODEL", "").strip() or None
        ),
        whisper_language=(
            source.get("M3_WHISPER_LANGUAGE", "").strip() or None
        ),
    )

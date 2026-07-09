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
    app_mode: str
    episode_dir: Path
    runtime_session_dir: Path
    runtime_flow_dir: Path
    userlist_path: Path
    ux_event_log: Path
    journal_log: Path
    annotation_run_dir: Path | None
    annotation_run_root: Path
    report_min_count: int
    profile_report_mode: str
    profile_llm_provider: str
    profile_llm_model: str
    ux_idle_after_sec: int
    initial_session_ttl_sec: int
    tone_config: Path
    audio_temp_dir: Path
    intake_transcript_dir: Path
    capture_artifact_dir: Path
    capture_extraction_dir: Path
    capture_debug_dir: Path
    capture_debug_raw_provider_output: bool
    capture_extraction_provider: str
    openai_api_key: str
    deepseek_api_key: str
    deepseek_base_url: str
    capture_extraction_model: str
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


def parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("boolean values must be one of: 1, 0, true, false, yes, no, on, off")


def admin_chat_ids_for_settings(settings: Settings) -> frozenset[int]:
    return settings.telegram_admin_chat_ids


def owner_chat_id_for_settings(settings: Settings) -> int | None:
    return settings.telegram_owner_chat_id


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None and load_dotenv is not None:
        load_dotenv()

    source = env if env is not None else os.environ
    token = source.get("TELEGRAM_BOT_TOKEN", "").strip()
    app_mode = source.get("M3_APP_MODE", "ml").strip().lower() or "ml"
    if app_mode not in {"ml", "production"}:
        raise ValueError("M3_APP_MODE must be one of: ml, production")
    capture_extraction_provider = source.get(
        "M3_CAPTURE_EXTRACTION_PROVIDER",
        "deepseek" if app_mode == "production" else "unavailable",
    ).strip().lower()
    if capture_extraction_provider not in {"unavailable", "deepseek", "openai"}:
        raise ValueError(
            "M3_CAPTURE_EXTRACTION_PROVIDER must be one of: "
            "unavailable, deepseek, openai"
        )
    profile_report_mode = source.get("M3_PROFILE_REPORT_MODE", "auto").strip().lower()
    if profile_report_mode not in {"auto", "deterministic", "llm"}:
        raise ValueError(
            "M3_PROFILE_REPORT_MODE must be one of: auto, deterministic, llm"
        )
    profile_llm_provider = source.get(
        "M3_PROFILE_LLM_PROVIDER",
        "deepseek" if app_mode == "production" else "unavailable",
    ).strip().lower()
    if profile_llm_provider not in {"unavailable", "deepseek", "openai"}:
        raise ValueError(
            "M3_PROFILE_LLM_PROVIDER must be one of: unavailable, deepseek, openai"
        )

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
        app_mode=app_mode,
        episode_dir=Path(source.get("M3_EPISODE_DIR", "data/episodes")),
        runtime_session_dir=Path(
            source.get("M3_RUNTIME_SESSION_DIR", "data/runtime-sessions")
        ),
        runtime_flow_dir=Path(
            source.get("M3_RUNTIME_FLOW_DIR", "data/runtime-flows")
        ),
        userlist_path=Path(source.get("M3_USERLIST_PATH", "data/userlist/users.json")),
        ux_event_log=Path(source.get("M3_UX_EVENT_LOG", "data/ux-events/events.jsonl")),
        journal_log=Path(source.get("M3_JOURNAL_LOG", "data/journal/events.jsonl")),
        annotation_run_dir=(
            Path(source["M3_ANNOTATION_RUN_DIR"])
            if source.get("M3_ANNOTATION_RUN_DIR", "").strip()
            else None
        ),
        annotation_run_root=Path(
            source.get("M3_ANNOTATION_RUN_ROOT", "data/annotation-runs")
        ),
        report_min_count=int(source.get("M3_REPORT_MIN_COUNT", "2")),
        profile_report_mode=profile_report_mode,
        profile_llm_provider=profile_llm_provider,
        profile_llm_model=source.get("M3_PROFILE_LLM_MODEL", "").strip(),
        ux_idle_after_sec=int(source.get("M3_UX_IDLE_AFTER_SEC", "7200")),
        initial_session_ttl_sec=int(source.get("M3_INITIAL_SESSION_TTL_SEC", "600")),
        tone_config=Path(source.get("M3_TONE_CONFIG", "config/tone.yaml")),
        audio_temp_dir=Path(source.get("M3_AUDIO_TEMP_DIR", "data/runtime-audio")),
        intake_transcript_dir=Path(source.get("M3_INTAKE_TRANSCRIPT_DIR", "data/intake-transcripts")),
        capture_artifact_dir=Path(
            source.get("M3_CAPTURE_ARTIFACT_DIR", "data/capture-artifacts")
        ),
        capture_extraction_dir=Path(
            source.get("M3_CAPTURE_EXTRACTION_DIR", "data/capture-extractions")
        ),
        capture_debug_dir=Path(source.get("M3_CAPTURE_DEBUG_DIR", "data/capture-debug")),
        capture_debug_raw_provider_output=parse_bool(
            source.get("M3_CAPTURE_DEBUG_RAW_PROVIDER_OUTPUT"),
            default=False,
        ),
        capture_extraction_provider=capture_extraction_provider,
        openai_api_key=source.get("OPENAI_API_KEY", "").strip(),
        deepseek_api_key=source.get("DEEPSEEK_API_KEY", "").strip(),
        deepseek_base_url=source.get(
            "M3_DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        ).strip() or "https://api.deepseek.com",
        capture_extraction_model=source.get(
            "M3_CAPTURE_EXTRACTION_MODEL", ""
        ).strip(),
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
            source.get("M3_WHISPER_LANGUAGE", "ru").strip() or None
        ),
    )

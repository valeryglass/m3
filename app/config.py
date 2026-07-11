from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import re
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
    consent_version: str
    data_retention_days: int | None
    app_mode: str
    episode_dir: Path
    runtime_session_dir: Path
    runtime_flow_dir: Path
    userlist_path: Path
    ux_event_log: Path
    journal_log: Path
    provider_usage_state: Path
    provider_capture_daily_limit: int
    provider_profile_daily_limit: int
    provider_daily_token_budget: int
    provider_max_in_flight: int
    provider_queue_timeout_sec: float
    provider_circuit_failure_threshold: int
    provider_circuit_cooldown_sec: int
    provider_max_retries: int
    provider_retry_backoff_sec: float
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


def parse_consent_version(value: str | None) -> str:
    version = (value or "beta-1").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", version):
        raise ValueError(
            "M3_CONSENT_VERSION must contain 1-32 letters, digits, dots, dashes, or underscores"
        )
    return version


def parse_optional_positive_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("optional positive integer must be greater than zero")
    return parsed


def parse_positive_int(value: str, *, name: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def parse_positive_float(value: str, *, name: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def parse_nonnegative_int(value: str, *, name: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{name} cannot be negative")
    return parsed


def parse_nonnegative_float(value: str, *, name: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise ValueError(f"{name} cannot be negative")
    return parsed


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
        consent_version=parse_consent_version(source.get("M3_CONSENT_VERSION")),
        data_retention_days=parse_optional_positive_int(
            source.get("M3_DATA_RETENTION_DAYS")
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
        provider_usage_state=Path(
            source.get("M3_PROVIDER_USAGE_STATE", "data/provider-usage/state.json")
        ),
        provider_capture_daily_limit=parse_positive_int(
            source.get("M3_PROVIDER_CAPTURE_DAILY_LIMIT", "20"),
            name="M3_PROVIDER_CAPTURE_DAILY_LIMIT",
        ),
        provider_profile_daily_limit=parse_positive_int(
            source.get("M3_PROVIDER_PROFILE_DAILY_LIMIT", "20"),
            name="M3_PROVIDER_PROFILE_DAILY_LIMIT",
        ),
        provider_daily_token_budget=parse_positive_int(
            source.get("M3_PROVIDER_DAILY_TOKEN_BUDGET", "200000"),
            name="M3_PROVIDER_DAILY_TOKEN_BUDGET",
        ),
        provider_max_in_flight=parse_positive_int(
            source.get("M3_PROVIDER_MAX_IN_FLIGHT", "2"),
            name="M3_PROVIDER_MAX_IN_FLIGHT",
        ),
        provider_queue_timeout_sec=parse_positive_float(
            source.get("M3_PROVIDER_QUEUE_TIMEOUT_SEC", "10"),
            name="M3_PROVIDER_QUEUE_TIMEOUT_SEC",
        ),
        provider_circuit_failure_threshold=parse_positive_int(
            source.get("M3_PROVIDER_CIRCUIT_FAILURE_THRESHOLD", "3"),
            name="M3_PROVIDER_CIRCUIT_FAILURE_THRESHOLD",
        ),
        provider_circuit_cooldown_sec=parse_positive_int(
            source.get("M3_PROVIDER_CIRCUIT_COOLDOWN_SEC", "300"),
            name="M3_PROVIDER_CIRCUIT_COOLDOWN_SEC",
        ),
        provider_max_retries=parse_nonnegative_int(
            source.get("M3_PROVIDER_MAX_RETRIES", "1"),
            name="M3_PROVIDER_MAX_RETRIES",
        ),
        provider_retry_backoff_sec=parse_nonnegative_float(
            source.get("M3_PROVIDER_RETRY_BACKOFF_SEC", "0.5"),
            name="M3_PROVIDER_RETRY_BACKOFF_SEC",
        ),
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
        tone_config=Path(source.get("M3_TONE_CONFIG", "app/tone.yaml")),
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

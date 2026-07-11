import pytest

from app.config import (
    admin_chat_ids_for_settings,
    load_settings,
    owner_chat_id_for_settings,
    parse_chat_ids,
    parse_bool,
    parse_consent_version,
    parse_optional_positive_int,
)


def test_parse_chat_ids_trims_and_ignores_empty_items():
    assert parse_chat_ids("123, -456, ,789") == frozenset({123, -456, 789})


def test_load_settings_uses_default_data_paths():
    settings = load_settings({"TELEGRAM_BOT_TOKEN": "token"})

    assert settings.telegram_bot_token == "token"
    assert settings.telegram_admin_chat_ids == frozenset()
    assert settings.telegram_owner_chat_id is None
    assert settings.consent_version == "beta-1"
    assert settings.data_retention_days is None
    assert settings.app_mode == "ml"
    assert str(settings.episode_dir) == "data/episodes"
    assert str(settings.runtime_session_dir) == "data/runtime-sessions"
    assert str(settings.runtime_flow_dir) == "data/runtime-flows"
    assert str(settings.userlist_path) == "data/userlist/users.json"
    assert str(settings.ux_event_log) == "data/ux-events/events.jsonl"
    assert str(settings.journal_log) == "data/journal/events.jsonl"
    assert str(settings.provider_usage_state) == "data/provider-usage/state.json"
    assert settings.provider_capture_daily_limit == 20
    assert settings.provider_profile_daily_limit == 20
    assert settings.provider_daily_token_budget == 200000
    assert settings.provider_max_in_flight == 2
    assert settings.provider_queue_timeout_sec == 10.0
    assert settings.provider_circuit_failure_threshold == 3
    assert settings.provider_circuit_cooldown_sec == 300
    assert settings.provider_max_retries == 1
    assert settings.provider_retry_backoff_sec == 0.5
    assert settings.annotation_run_dir is None
    assert str(settings.annotation_run_root) == "data/annotation-runs"
    assert settings.report_min_count == 2
    assert settings.profile_report_mode == "auto"
    assert settings.profile_llm_provider == "unavailable"
    assert settings.profile_llm_model == ""
    assert settings.ux_idle_after_sec == 7200
    assert settings.initial_session_ttl_sec == 600
    assert str(settings.tone_config) == "app/tone.yaml"
    assert str(settings.audio_temp_dir) == "data/runtime-audio"
    assert str(settings.intake_transcript_dir) == "data/intake-transcripts"
    assert str(settings.capture_artifact_dir) == "data/capture-artifacts"
    assert str(settings.capture_extraction_dir) == "data/capture-extractions"
    assert str(settings.capture_debug_dir) == "data/capture-debug"
    assert settings.capture_debug_raw_provider_output is False
    assert settings.capture_extraction_provider == "unavailable"
    assert settings.openai_api_key == ""
    assert settings.deepseek_api_key == ""
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.capture_extraction_model == ""
    assert settings.audio_max_duration_sec == 300
    assert settings.audio_max_file_size_bytes == 20 * 1024 * 1024
    assert settings.transcription_provider == "whisper"
    assert settings.whisper_command == "whisper"
    assert settings.whisper_model is None
    assert settings.whisper_language == "ru"


def test_old_allowed_chat_ids_no_longer_grant_access():
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ALLOWED_CHAT_IDS": "123",
        }
    )

    assert not hasattr(settings, "telegram_allowed_chat_ids")
    assert settings.telegram_admin_chat_ids == frozenset()


def test_load_settings_allows_overrides():
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_UX_EVENT_LOG": "/tmp/events.jsonl",
            "M3_JOURNAL_LOG": "/tmp/journal.jsonl",
            "M3_PROVIDER_USAGE_STATE": "/tmp/provider-usage.json",
            "M3_PROVIDER_CAPTURE_DAILY_LIMIT": "7",
            "M3_PROVIDER_PROFILE_DAILY_LIMIT": "8",
            "M3_PROVIDER_DAILY_TOKEN_BUDGET": "9000",
            "M3_PROVIDER_MAX_IN_FLIGHT": "3",
            "M3_PROVIDER_QUEUE_TIMEOUT_SEC": "2.5",
            "M3_PROVIDER_CIRCUIT_FAILURE_THRESHOLD": "4",
            "M3_PROVIDER_CIRCUIT_COOLDOWN_SEC": "60",
            "M3_PROVIDER_MAX_RETRIES": "2",
            "M3_PROVIDER_RETRY_BACKOFF_SEC": "0.25",
            "M3_RUNTIME_SESSION_DIR": "/tmp/runtime-sessions",
            "M3_RUNTIME_FLOW_DIR": "/tmp/runtime-flows",
            "M3_UX_IDLE_AFTER_SEC": "60",
            "M3_INITIAL_SESSION_TTL_SEC": "30",
            "M3_TONE_CONFIG": "/tmp/tone.yaml",
            "M3_USERLIST_PATH": "/tmp/users.json",
            "M3_ANNOTATION_RUN_DIR": "/tmp/run-selected",
            "M3_ANNOTATION_RUN_ROOT": "/tmp/runs",
            "M3_REPORT_MIN_COUNT": "3",
            "M3_PROFILE_REPORT_MODE": "llm",
            "M3_PROFILE_LLM_PROVIDER": "deepseek",
            "M3_PROFILE_LLM_MODEL": "profile-model",
            "M3_TELEGRAM_ADMIN_CHAT_IDS": "225672,327002663",
            "M3_TELEGRAM_OWNER_CHAT_ID": "225672",
            "M3_CONSENT_VERSION": "public-beta-v2",
            "M3_DATA_RETENTION_DAYS": "90",
            "M3_APP_MODE": "production",
            "M3_AUDIO_TEMP_DIR": "/tmp/audio",
            "M3_INTAKE_TRANSCRIPT_DIR": "/tmp/transcripts",
            "M3_CAPTURE_ARTIFACT_DIR": "/tmp/captures",
            "M3_CAPTURE_EXTRACTION_DIR": "/tmp/extractions",
            "M3_CAPTURE_DEBUG_DIR": "/tmp/capture-debug",
            "M3_CAPTURE_DEBUG_RAW_PROVIDER_OUTPUT": "1",
            "M3_CAPTURE_EXTRACTION_PROVIDER": "deepseek",
            "OPENAI_API_KEY": "test-key",
            "DEEPSEEK_API_KEY": "deepseek-key",
            "M3_DEEPSEEK_BASE_URL": "https://deepseek.test",
            "M3_CAPTURE_EXTRACTION_MODEL": "test-model",
            "M3_AUDIO_MAX_DURATION_SEC": "180",
            "M3_AUDIO_MAX_FILE_SIZE_BYTES": "1048576",
            "M3_TRANSCRIPTION_PROVIDER": "whisper",
            "M3_WHISPER_COMMAND": "/usr/local/bin/whisper",
            "M3_WHISPER_MODEL": "base",
            "M3_WHISPER_LANGUAGE": "ru",
        }
    )

    assert str(settings.ux_event_log) == "/tmp/events.jsonl"
    assert str(settings.journal_log) == "/tmp/journal.jsonl"
    assert str(settings.provider_usage_state) == "/tmp/provider-usage.json"
    assert settings.provider_capture_daily_limit == 7
    assert settings.provider_profile_daily_limit == 8
    assert settings.provider_daily_token_budget == 9000
    assert settings.provider_max_in_flight == 3
    assert settings.provider_queue_timeout_sec == 2.5
    assert settings.provider_circuit_failure_threshold == 4
    assert settings.provider_circuit_cooldown_sec == 60
    assert settings.provider_max_retries == 2
    assert settings.provider_retry_backoff_sec == 0.25
    assert str(settings.runtime_session_dir) == "/tmp/runtime-sessions"
    assert str(settings.runtime_flow_dir) == "/tmp/runtime-flows"
    assert settings.ux_idle_after_sec == 60
    assert settings.initial_session_ttl_sec == 30
    assert str(settings.tone_config) == "/tmp/tone.yaml"
    assert str(settings.userlist_path) == "/tmp/users.json"
    assert str(settings.annotation_run_dir) == "/tmp/run-selected"
    assert str(settings.annotation_run_root) == "/tmp/runs"
    assert settings.report_min_count == 3
    assert settings.profile_report_mode == "llm"
    assert settings.profile_llm_provider == "deepseek"
    assert settings.profile_llm_model == "profile-model"
    assert settings.telegram_admin_chat_ids == frozenset({225672, 327002663})
    assert settings.telegram_owner_chat_id == 225672
    assert settings.consent_version == "public-beta-v2"
    assert settings.data_retention_days == 90
    assert settings.app_mode == "production"
    assert str(settings.audio_temp_dir) == "/tmp/audio"
    assert str(settings.intake_transcript_dir) == "/tmp/transcripts"
    assert str(settings.capture_artifact_dir) == "/tmp/captures"
    assert str(settings.capture_extraction_dir) == "/tmp/extractions"
    assert str(settings.capture_debug_dir) == "/tmp/capture-debug"
    assert settings.capture_debug_raw_provider_output is True
    assert settings.capture_extraction_provider == "deepseek"
    assert settings.openai_api_key == "test-key"
    assert settings.deepseek_api_key == "deepseek-key"
    assert settings.deepseek_base_url == "https://deepseek.test"
    assert settings.capture_extraction_model == "test-model"
    assert settings.audio_max_duration_sec == 180
    assert settings.audio_max_file_size_bytes == 1048576
    assert settings.transcription_provider == "whisper"
    assert settings.whisper_command == "/usr/local/bin/whisper"
    assert settings.whisper_model == "base"
    assert settings.whisper_language == "ru"


def test_admin_and_owner_accessors_return_configured_ids():
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_TELEGRAM_ADMIN_CHAT_IDS": "225672,327002663",
            "M3_TELEGRAM_OWNER_CHAT_ID": "225672",
            "M3_AUDIO_TEMP_DIR": "/tmp/audio",
            "M3_INTAKE_TRANSCRIPT_DIR": "/tmp/transcripts",
            "M3_AUDIO_MAX_DURATION_SEC": "180",
            "M3_AUDIO_MAX_FILE_SIZE_BYTES": "1048576",
            "M3_TRANSCRIPTION_PROVIDER": "whisper",
            "M3_WHISPER_COMMAND": "/usr/local/bin/whisper",
            "M3_WHISPER_MODEL": "base",
            "M3_WHISPER_LANGUAGE": "ru",
        }
    )

    assert admin_chat_ids_for_settings(settings) == frozenset({225672, 327002663})
    assert owner_chat_id_for_settings(settings) == 225672


def test_production_mode_defaults_capture_extraction_provider_to_deepseek():
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_APP_MODE": "production",
        }
    )

    assert settings.app_mode == "production"
    assert settings.capture_extraction_provider == "deepseek"
    assert settings.profile_llm_provider == "deepseek"


def test_explicit_capture_extraction_provider_override_is_allowed():
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_APP_MODE": "production",
            "M3_CAPTURE_EXTRACTION_PROVIDER": "openai",
        }
    )

    assert settings.capture_extraction_provider == "openai"


def test_invalid_runtime_mode_and_provider_are_rejected():
    with pytest.raises(ValueError, match="M3_APP_MODE"):
        load_settings({"TELEGRAM_BOT_TOKEN": "token", "M3_APP_MODE": "prod"})
    with pytest.raises(ValueError, match="M3_CAPTURE_EXTRACTION_PROVIDER"):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "M3_CAPTURE_EXTRACTION_PROVIDER": "unknown",
            }
        )
    with pytest.raises(ValueError, match="M3_PROFILE_REPORT_MODE"):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "M3_PROFILE_REPORT_MODE": "ai",
            }
        )
    with pytest.raises(ValueError, match="M3_PROFILE_LLM_PROVIDER"):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "M3_PROFILE_LLM_PROVIDER": "unknown",
            }
        )


def test_parse_bool_accepts_runtime_env_forms():
    assert parse_bool("1") is True
    assert parse_bool("true") is True
    assert parse_bool("on") is True
    assert parse_bool("0") is False
    assert parse_bool("false") is False
    assert parse_bool("", default=True) is True
    with pytest.raises(ValueError, match="boolean values"):
        parse_bool("maybe")


def test_consent_and_retention_config_validation():
    assert parse_consent_version(None) == "beta-1"
    assert parse_consent_version("beta_2.1") == "beta_2.1"
    assert parse_optional_positive_int("") is None
    assert parse_optional_positive_int("30") == 30
    with pytest.raises(ValueError, match="M3_CONSENT_VERSION"):
        parse_consent_version("bad version")
    with pytest.raises(ValueError, match="greater than zero"):
        parse_optional_positive_int("0")


def test_provider_guard_config_rejects_invalid_limits():
    with pytest.raises(ValueError, match="M3_PROVIDER_MAX_IN_FLIGHT"):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "M3_PROVIDER_MAX_IN_FLIGHT": "0",
            }
        )
    with pytest.raises(ValueError, match="M3_PROVIDER_MAX_RETRIES"):
        load_settings(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "M3_PROVIDER_MAX_RETRIES": "-1",
            }
        )

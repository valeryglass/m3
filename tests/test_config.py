from app.config import admin_chat_id_for_settings, load_settings, parse_allowed_chat_ids


def test_parse_allowed_chat_ids_trims_and_ignores_empty_items():
    assert parse_allowed_chat_ids("123, -456, ,789") == frozenset(
        {123, -456, 789}
    )


def test_load_settings_uses_default_data_paths():
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ALLOWED_CHAT_IDS": "123",
        }
    )

    assert settings.telegram_bot_token == "token"
    assert settings.telegram_allowed_chat_ids == frozenset({123})
    assert settings.telegram_admin_chat_id is None
    assert str(settings.episode_dir) == "data/episodes"
    assert str(settings.state_dir) == "data/state"
    assert str(settings.userlist_path) == "data/userlist/users.json"
    assert str(settings.ux_event_log) == "data/ux-events/events.jsonl"
    assert settings.ux_idle_after_sec == 7200
    assert settings.initial_session_ttl_sec == 600
    assert str(settings.tone_config) == "config/tone.yaml"


def test_load_settings_allows_empty_chat_allowlist_for_open_mvp():
    settings = load_settings({"TELEGRAM_BOT_TOKEN": "token"})

    assert settings.telegram_allowed_chat_ids == frozenset()


def test_load_settings_allows_ux_overrides():
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_UX_EVENT_LOG": "/tmp/events.jsonl",
            "M3_UX_IDLE_AFTER_SEC": "60",
            "M3_INITIAL_SESSION_TTL_SEC": "30",
            "M3_TONE_CONFIG": "/tmp/tone.yaml",
            "M3_USERLIST_PATH": "/tmp/users.json",
            "M3_TELEGRAM_ADMIN_CHAT_ID": "999",
        }
    )

    assert str(settings.ux_event_log) == "/tmp/events.jsonl"
    assert settings.ux_idle_after_sec == 60
    assert settings.initial_session_ttl_sec == 30
    assert str(settings.tone_config) == "/tmp/tone.yaml"
    assert str(settings.userlist_path) == "/tmp/users.json"
    assert settings.telegram_admin_chat_id == 999


def test_admin_chat_id_uses_override_before_allowlist():
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ALLOWED_CHAT_IDS": "123, 7",
            "M3_TELEGRAM_ADMIN_CHAT_ID": "999",
        }
    )

    assert admin_chat_id_for_settings(settings) == 999


def test_admin_chat_id_falls_back_to_shortest_allowed_id():
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ALLOWED_CHAT_IDS": "12345, 77, 8, -9",
        }
    )

    assert admin_chat_id_for_settings(settings) == -9

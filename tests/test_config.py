from app.config import (
    admin_chat_ids_for_settings,
    load_settings,
    owner_chat_id_for_settings,
    parse_chat_ids,
)


def test_parse_chat_ids_trims_and_ignores_empty_items():
    assert parse_chat_ids("123, -456, ,789") == frozenset({123, -456, 789})


def test_load_settings_uses_default_data_paths():
    settings = load_settings({"TELEGRAM_BOT_TOKEN": "token"})

    assert settings.telegram_bot_token == "token"
    assert settings.telegram_admin_chat_ids == frozenset()
    assert settings.telegram_owner_chat_id is None
    assert str(settings.episode_dir) == "data/episodes"
    assert str(settings.state_dir) == "data/state"
    assert str(settings.userlist_path) == "data/userlist/users.json"
    assert str(settings.ux_event_log) == "data/ux-events/events.jsonl"
    assert settings.ux_idle_after_sec == 7200
    assert settings.initial_session_ttl_sec == 600
    assert str(settings.tone_config) == "config/tone.yaml"


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
            "M3_UX_IDLE_AFTER_SEC": "60",
            "M3_INITIAL_SESSION_TTL_SEC": "30",
            "M3_TONE_CONFIG": "/tmp/tone.yaml",
            "M3_USERLIST_PATH": "/tmp/users.json",
            "M3_TELEGRAM_ADMIN_CHAT_IDS": "225672,327002663",
            "M3_TELEGRAM_OWNER_CHAT_ID": "225672",
        }
    )

    assert str(settings.ux_event_log) == "/tmp/events.jsonl"
    assert settings.ux_idle_after_sec == 60
    assert settings.initial_session_ttl_sec == 30
    assert str(settings.tone_config) == "/tmp/tone.yaml"
    assert str(settings.userlist_path) == "/tmp/users.json"
    assert settings.telegram_admin_chat_ids == frozenset({225672, 327002663})
    assert settings.telegram_owner_chat_id == 225672


def test_admin_and_owner_accessors_return_configured_ids():
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "token",
            "M3_TELEGRAM_ADMIN_CHAT_IDS": "225672,327002663",
            "M3_TELEGRAM_OWNER_CHAT_ID": "225672",
        }
    )

    assert admin_chat_ids_for_settings(settings) == frozenset({225672, 327002663})
    assert owner_chat_id_for_settings(settings) == 225672

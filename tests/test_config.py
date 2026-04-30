from app.config import load_settings, parse_allowed_chat_ids


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
    assert str(settings.episode_dir) == "data/episodes"
    assert str(settings.state_dir) == "data/state"


def test_load_settings_allows_empty_chat_allowlist_for_open_mvp():
    settings = load_settings({"TELEGRAM_BOT_TOKEN": "token"})

    assert settings.telegram_allowed_chat_ids == frozenset()

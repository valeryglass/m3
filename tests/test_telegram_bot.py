import app.telegram_bot as telegram_bot


def test_telegram_bot_module_imports_without_contacting_telegram():
    assert callable(telegram_bot.main)

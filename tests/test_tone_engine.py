from app.loop_extractor import OBSERVED_FIELDS
from app.messages import COMMAND_DESCRIPTIONS, SESSION_MESSAGES, TARGET_PROMPTS
from app.tone_engine import ToneEngine, load_tone_engine


def test_load_tone_engine_loads_valid_yaml(tmp_path):
    path = tmp_path / "tone.yaml"
    path.write_text(
        """
tone:
  name: custom
  question_style:
    max_length: 80
""",
        encoding="utf-8",
    )

    tone = load_tone_engine(path)

    assert tone.config["tone"]["name"] == "custom"
    assert tone.max_question_length == 80
    assert tone.target_prompt("situation") == "Что произошло конкретно? 1-2 предложения."


def test_load_tone_engine_falls_back_when_missing():
    tone = load_tone_engine("/tmp/does-not-exist/tone.yaml")

    assert tone.config["tone"]["name"] == "pragmatic_cbt_guide"


def test_default_target_prompts_are_russian_and_short():
    tone = ToneEngine.default()

    assert tone.target_prompt("situation") == "Что произошло конкретно? 1-2 предложения."
    for target in tone.prompts:
        assert len(tone.target_prompt(target)) <= tone.max_question_length


def test_message_catalog_covers_every_observed_target():
    assert set(TARGET_PROMPTS) == set(OBSERVED_FIELDS)


def test_session_messages_render_unchanged():
    tone = ToneEngine.default()

    assert tone.empty_answer("situation") == (
        "Нужен непустой ответ.\n\nЧто произошло конкретно? 1-2 предложения."
    )
    assert tone.complete() == "Готово. Эпизод собран."
    assert tone.already_complete() == "Эпизод уже собран."
    assert tone.status("situation", 1, 7) == "Текущий шаг: situation\nЗаполнено: 1/7"
    assert tone.help() == (
        "Команды:\n"
        "/start — начать новый эпизод\n"
        "/cancel — отменить сессию\n"
        "/help — показать команды"
    )
    assert tone.no_active_loop() == "Активной сессии нет."
    assert tone.no_active_loop_start() == (
        "Активной сессии нет. Отправь /start, чтобы начать."
    )
    assert tone.cancel() == "Сессия отменена."
    assert tone.unauthorized() == "Нет доступа."
    assert tone.expired_initial_session() == (
        "Прошлая сессия истекла до первого ответа. Отправь /start заново."
    )
    assert tone.saved_episode("Готово. Эпизод собран.") == "Готово. Эпизод собран."
    assert set(SESSION_MESSAGES) == {
        "empty_answer",
        "complete",
        "already_complete",
        "status",
        "help",
        "no_active_loop",
        "no_active_loop_start",
        "cancel",
        "unauthorized",
        "expired_initial_session",
        "saved_episode",
    }


def test_command_descriptions_render_unchanged():
    tone = ToneEngine.default()

    assert tone.command_description("start") == "Начать новый эпизод"
    assert tone.command_description("cancel") == "Отменить сессию"
    assert tone.command_description("help") == "Показать команды"
    assert COMMAND_DESCRIPTIONS == {
        "start": "Начать новый эпизод",
        "cancel": "Отменить сессию",
        "help": "Показать команды",
    }


def test_default_prompts_avoid_forbidden_style_terms():
    tone = ToneEngine.default()
    prompt_text = "\n".join(tone.prompts.values()).lower()

    for forbidden in tone.forbidden:
        assert forbidden.lower() not in prompt_text

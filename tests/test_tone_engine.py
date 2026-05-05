from pathlib import Path

from app.loop_extractor import OBSERVED_FIELDS
from app.messages import SESSION_MESSAGES, TARGET_PROMPTS
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
    assert tone.no_active_loop() == "Активной сессии нет."
    assert tone.cancel() == "Сессия отменена."
    assert tone.unauthorized() == "Нет доступа."
    assert tone.expired_initial_session() == (
        "Прошлая сессия истекла до первого ответа. Отправь /start заново."
    )
    assert tone.saved_episode("Готово. Эпизод собран.", Path("data/episodes/e.json")) == (
        "Готово. Эпизод собран.\nСохранено: data/episodes/e.json"
    )
    assert set(SESSION_MESSAGES) == {
        "empty_answer",
        "complete",
        "already_complete",
        "status",
        "no_active_loop",
        "cancel",
        "unauthorized",
        "expired_initial_session",
        "saved_episode",
    }


def test_default_prompts_avoid_forbidden_style_terms():
    tone = ToneEngine.default()
    prompt_text = "\n".join(tone.prompts.values()).lower()

    for forbidden in tone.forbidden:
        assert forbidden.lower() not in prompt_text

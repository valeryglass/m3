from app.loop_extractor import OBSERVED_FIELDS
from app.messages import (
    BOT_PROFILE,
    COMMAND_DESCRIPTIONS,
    FIELD_GUIDES,
    SESSION_MESSAGES,
    TARGET_PROMPTS,
)
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
    assert tone.prompts["situation"] == "Что произошло конкретно? 1-2 предложения"


def test_load_tone_engine_falls_back_when_missing():
    tone = load_tone_engine("/tmp/does-not-exist/tone.yaml")

    assert tone.config["tone"]["name"] == "pragmatic_cbt_guide"


def test_default_target_prompts_are_russian_and_short():
    tone = ToneEngine.default()

    assert tone.prompts["situation"] == "Что произошло конкретно? 1-2 предложения"
    for prompt in tone.prompts.values():
        assert len(prompt) <= tone.max_question_length


def test_message_catalog_covers_every_observed_target():
    assert set(TARGET_PROMPTS) == set(OBSERVED_FIELDS)
    assert set(FIELD_GUIDES) == set(OBSERVED_FIELDS)


def test_field_guide_card_renders_source_copy():
    tone = ToneEngine.default()

    assert tone.field_guide("situation")["source_field"] == (
        "situation.event_description"
    )
    assert tone.target_prompt("situation") == (
        "📝 Описание\n"
        "Что произошло фактически. Без анализа и выводов\n\n"
        "🧬 Формула\n"
        "[кто] → [действие] → [контекст]\n\n"
        "🎯 Пример\n"
        "• <i>коллега раскритиковал мой текст в чате</i>\n"
        "• <i>партнёр не ответил на сообщение вечером</i>\n"
        "• <i>я увидел дедлайн в календаре утром</i>\n\n"
        "💡 Подсказки\n"
        "• <i>камера, не интерпретация</i>\n"
        "• <i>один конкретный момент</i>\n"
        "• <i>кто → что сделал</i>\n\n"
        "Что произошло конкретно? 1-2 предложения"
    )


def test_every_field_card_has_required_sections():
    tone = ToneEngine.default()

    for target in OBSERVED_FIELDS:
        card = tone.target_prompt(target)
        guide = tone.field_guide(target)
        assert "🧠 CBT / ACT loop" not in card
        assert "🧩 Поле" not in card
        assert f"\n{target}\n" not in card
        assert "📝 Описание" in card
        assert "🧬 Формула" in card
        assert "🎯 Пример" in card
        assert "💡 Подсказки" in card
        assert len(guide["examples"]) == 3
        assert len(guide["tips"]) == 3
        assert guide["description"] in card
        assert guide["formula"] in card
        assert guide["question"] in card
        for example in guide["examples"]:
            assert f"• <i>{example}</i>" in card
        for tip in guide["tips"]:
            assert f"• <i>{tip}</i>" in card


def test_session_messages_render_unchanged():
    tone = ToneEngine.default()
    situation_card = tone.target_prompt("situation")
    behavior_card = tone.target_prompt("behavior")

    assert tone.empty_answer("situation") == (
        f"Нужен непустой ответ\n\n{situation_card}"
    )
    assert tone.start_session(situation_card) == (
        f"Соберём один конкретный эпизод. Идём коротко, по фактам\n\n"
        f"{situation_card}"
    )
    assert tone.next_prompt_bridge(1, 7, behavior_card) == (
        f"💾 ■□□□□□□ 1/7\n\n{behavior_card}"
    )
    assert tone.complete() == "Готово. Эпизод собран"
    assert tone.already_complete() == "Эпизод уже собран"
    assert tone.status("situation", 1, 7) == "Текущий шаг: situation\nЗаполнено: 1/7"
    assert tone.help() == (
        "Команды:\n"
        "/start — начать новый эпизод\n"
        "/cancel — отменить сессию\n"
        "/help — показать команды"
    )
    assert tone.no_active_loop() == "Активной сессии нет"
    assert tone.no_active_loop_start() == (
        "Сейчас активной сессии нет. Отправь /start, чтобы начать новый эпизод"
    )
    assert tone.cancel() == "Сессия отменена"
    assert tone.unauthorized() == "Нет доступа"
    assert tone.expired_initial_session() == (
        "Прошлая сессия истекла до первого ответа. Отправь /start заново"
    )
    assert tone.saved_episode("Готово. Эпизод собран") == "Готово. Эпизод собран"
    assert set(SESSION_MESSAGES) == {
        "field_card",
        "empty_answer",
        "start_session",
        "next_prompt_bridge",
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


def test_bot_profile_messages_render_unchanged():
    tone = ToneEngine.default()

    assert tone.bot_short_description() == (
        "Собирает один CBT-эпизод короткими вопросами."
    )
    assert tone.bot_description() == (
        "Бот помогает зафиксировать один конкретный эпизод: что произошло, "
        "что ты сделал, что было потом, какая мысль мелькнула, эмоция и тело. "
        "Начни с /start."
    )
    assert BOT_PROFILE == {
        "short_description": "Собирает один CBT-эпизод короткими вопросами.",
        "description": (
            "Бот помогает зафиксировать один конкретный эпизод: что произошло, "
            "что ты сделал, что было потом, какая мысль мелькнула, эмоция и тело. "
            "Начни с /start."
        ),
    }


def test_progress_bar_renders_fixed_rail():
    tone = ToneEngine.default()

    assert tone.progress_bar(0, 7) == "□□□□□□□"
    assert tone.progress_bar(1, 7) == "■□□□□□□"
    assert tone.progress_bar(6, 7) == "■■■■■■□"
    assert tone.progress_bar(7, 7) == "■■■■■■■"
    assert tone.progress_bar(9, 7) == "■■■■■■■"
    assert tone.progress_bar(-1, 7) == "□□□□□□□"


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

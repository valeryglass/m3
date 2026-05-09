from app.loop_extractor import OBSERVED_FIELDS
from app.messages import (
    BASIC_TARGETS,
    BOT_PROFILE,
    COMMAND_DESCRIPTIONS,
    FIELD_GUIDES,
    FULL_TARGETS,
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
    assert tone.prompts["situation"] == "Опиши ситуацию несколькими предложениями"


def test_load_tone_engine_falls_back_when_missing():
    tone = load_tone_engine("/tmp/does-not-exist/tone.yaml")

    assert tone.config["tone"]["name"] == "pragmatic_cbt_guide"


def test_default_target_prompts_are_russian_and_short():
    tone = ToneEngine.default()

    assert tone.prompts["situation"] == "Опиши ситуацию несколькими предложениями"
    for prompt in tone.prompts.values():
        assert len(prompt) <= tone.max_question_length


def test_message_catalog_covers_every_observed_target():
    assert set(TARGET_PROMPTS) == set(OBSERVED_FIELDS)
    assert set(FIELD_GUIDES) == set(FULL_TARGETS)
    assert BASIC_TARGETS == OBSERVED_FIELDS


def test_field_guide_card_renders_source_copy():
    tone = ToneEngine.default()

    assert tone.field_guide("situation")["source_field"] == (
        "situation.event_description"
    )
    assert tone.target_prompt("situation") == (
        "Ситуация\n\n"
        "<blockquote>"
        "• коллега раскритиковал мой текст в чате\n"
        "• партнёр не ответил на сообщение вечером\n"
        "• я увидел дедлайн в календаре утром"
        "</blockquote>\n\n"
        "Опиши ситуацию несколькими предложениями"
    )


def test_full_mode_field_cards_render_source_copy():
    tone = ToneEngine.default()

    assert tone.target_prompt("trigger") == (
        "Триггер\n\n"
        "<blockquote>"
        "• резкий комментарий в чате\n"
        "• уведомление от банка\n"
        "• воспоминание о конфликте"
        "</blockquote>\n\n"
        "Что именно зацепило или запустило реакцию?"
    )
    assert tone.target_prompt("actors") == (
        "Участники\n\n"
        "<blockquote>"
        "• я и коллега\n"
        "• партнёр\n"
        "• начальник и команда"
        "</blockquote>\n\n"
        "Кто был вовлечён в ситуацию?"
    )
    assert tone.target_prompt("speech") == (
        "Речь\n\n"
        "<blockquote>"
        "• коллега: «это не подходит»\n"
        "• я написал: «ок»\n"
        "• сообщений не было"
        "</blockquote>\n\n"
        "Какие слова или сообщения там были?"
    )


def test_every_field_card_has_required_sections():
    tone = ToneEngine.default()

    for target in OBSERVED_FIELDS:
        card = tone.target_prompt(target)
        guide = tone.field_guide(target)
        assert "🧠 CBT / ACT loop" not in card
        assert "🧩 Поле" not in card
        assert f"\n{target}\n" not in card
        assert "🎯 Пример" not in card
        assert "<blockquote>" in card
        assert "</blockquote>" in card
        assert "📝 Описание" not in card
        assert "🧬 Формула" not in card
        assert "💡 Подсказки" not in card
        if target != "emotion":
            assert len(guide["examples"]) == 3
        assert len(guide["tips"]) == 3
        assert guide["label"]
        assert guide["label"].capitalize() in card
        assert guide["description"] not in card
        assert guide["formula"] not in card
        assert guide["question"] in card
        for example in guide["examples"]:
            assert f"• {example}" in card
        for tip in guide["tips"]:
            assert tip not in card


def test_emotion_card_explains_buttons_and_free_text():
    tone = ToneEngine.default()

    assert tone.target_prompt("emotion") == (
        "Эмоция\n\n"
        "<blockquote>"
        "• растерянность, оцепенение, беспомощность"
        "</blockquote>\n\n"
        "Выбери одну или несколько эмоций\n"
        "Щёлкай несколько раз, чтобы выбрать интенсивность\n"
        "Можешь написать дополнительно, что чувствовал"
    )


def test_session_messages_render_unchanged():
    tone = ToneEngine.default()
    situation_card = tone.target_prompt("situation")
    behavior_card = tone.target_prompt("behavior")

    assert tone.empty_answer("situation") == (
        f"Нужен непустой ответ\n\n{situation_card}"
    )
    assert tone.start_session(situation_card) == (
        "Соберём один конкретный эпизод. Идём коротко, не спеша, по фактам\n\n"
        "□□□□□□□ 0/7\n\n"
        f"{situation_card}"
    )
    assert tone.next_prompt_bridge(1, 7, behavior_card) == (
        f"■□□□□□□ 1/7\n\n{behavior_card}"
    )
    assert tone.review_screen(
        {
            "situation": {"value": "s"},
            "behavior": {"value": "b"},
            "short_term_consequence": {"value": "st"},
            "long_term_consequence": {"value": "lt"},
            "automatic_thought": {"value": "at"},
            "emotion": {"value": "e"},
            "body": {"value": "body"},
        }
    ) == (
        "■■■■■■■ 7/7 💯\n\n"
        "ситуация: s\n"
        "действие: b\n"
        "сразу после: st\n"
        "потом: lt\n"
        "мысль: at\n"
        "эмоция: e\n"
        "тело: body\n\n"
        "Сохраняем?"
    )
    assert tone.review_screen(
        {
            "situation": {"value": "s"},
            "trigger": {"value": "tr"},
            "actors": {"value": "ac"},
            "speech": {"value": "sp"},
            "behavior": {"value": "b"},
            "short_term_consequence": {"value": "st"},
            "long_term_consequence": {"value": "lt"},
            "automatic_thought": {"value": "at"},
            "emotion": {"value": "e"},
            "body": {"value": "body"},
        },
        FULL_TARGETS,
    ) == (
        "■■■■■■■■■■ 10/10 💯\n\n"
        "ситуация: s\n"
        "триггер: tr\n"
        "участники: ac\n"
        "речь: sp\n"
        "действие: b\n"
        "сразу после: st\n"
        "потом: lt\n"
        "мысль: at\n"
        "эмоция: e\n"
        "тело: body\n\n"
        "Сохраняем?"
    )
    assert tone.complete() == "Готово. Эпизод собран"
    assert tone.already_complete() == "Эпизод уже собран"
    assert tone.status("situation", 1, 7) == "Текущий шаг: situation\nЗаполнено: 1/7"
    assert tone.help() == (
        "МИШа\n"
        "машина извлечения шаблонов\n"
        "(аналитическая)\n\n"
        "Бот не ставит диагнозы и не даёт советов\n"
        "Он помогает аккуратно зафиксировать один эпизод по CBT/ACT-фрейму\n\n"
        "Команды:\n"
        "/start — начать один эпизод\n"
        "/cancel — отменить сессию\n"
        "/help — показать команды\n\n"
        "Связь: @mesto3"
    )
    assert tone.no_active_loop() == "Активной сессии нет"
    assert tone.no_active_loop_start() == (
        "Сейчас активной сессии нет. Отправь /start, чтобы начать новый эпизод"
    )
    assert tone.cancel() == "Сессия отменена"
    assert tone.unauthorized() == "Нет доступа"
    assert tone.emotion_buttons_required() == "Выбери эмоции кнопками и нажми Готово"
    assert tone.waitlisted() == (
        "Спасибо за интерес. Мы добавили тебя в waitlist. "
        "Напишем, как только доступ откроется"
    )
    assert tone.admin_waitlist_notice(456, "456") == (
        "Новый пользователь в waitlist\n"
        "chat_id: 456\n"
        "user_id: 456\n\n"
        "/approve 456\n"
        "/pause 456"
    )
    assert tone.admin_approved(456) == "Доступ одобрен для 456"
    assert tone.approval_granted() == "Доступ открыт. Отправь /start, чтобы начать."
    assert tone.admin_paused(456) == "Заявка поставлена на паузу для 456"
    assert tone.admin_bad_command("/approve") == "Используй /approve &lt;chat_id&gt;"
    assert tone.expired_initial_session() == (
        "Прошлая сессия истекла до первого ответа. Отправь /start заново"
    )
    assert tone.saved_episode("Готово. Эпизод собран", 3) == (
        "Готово. Эпизод собран\n\nВсего эпизодов: 3"
    )
    assert set(SESSION_MESSAGES) == {
        "field_card",
        "empty_answer",
        "start_session",
        "next_prompt_bridge",
        "review_screen",
        "complete",
        "already_complete",
        "status",
        "help",
        "no_active_loop",
        "no_active_loop_start",
        "cancel",
        "unauthorized",
        "emotion_buttons_required",
        "waitlisted",
        "admin_waitlist_notice",
        "admin_approved",
        "approval_granted",
        "admin_paused",
        "admin_bad_command",
        "expired_initial_session",
        "saved_episode",
    }


def test_bot_profile_messages_render_unchanged():
    tone = ToneEngine.default()

    assert tone.bot_short_description() == (
        "МИШа собирает один CBT/ACT-эпизод короткими вопросами"
    )
    assert tone.bot_description() == (
        "МИШа — машина извлечения шаблонов\n\n"
        "Помогает собрать один конкретный эпизод: факт, действие, последствия, "
        "мысль, эмоцию и тело\n\n"
        "Начни с /start"
    )
    assert BOT_PROFILE == {
        "short_description": "МИШа собирает один CBT/ACT-эпизод короткими вопросами",
        "description": (
            "МИШа — машина извлечения шаблонов\n\n"
            "Помогает собрать один конкретный эпизод: факт, действие, последствия, "
            "мысль, эмоцию и тело\n\n"
            "Начни с /start"
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

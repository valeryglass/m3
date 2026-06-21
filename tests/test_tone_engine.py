from app.loop_extractor import OBSERVED_FIELDS
from app.messages import (
    BOT_PROFILE,
    COMMAND_DESCRIPTIONS,
    FIELD_GUIDES,
    SESSION_MESSAGES,
    TARGETS,
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
    assert set(FIELD_GUIDES) == set(TARGETS)
    assert TARGETS == OBSERVED_FIELDS


def test_field_guide_card_renders_source_copy():
    tone = ToneEngine.default()

    assert tone.field_guide("situation")["source_field"] == (
        "situation.event_description"
    )
    assert (
        tone.target_prompt("situation")
        == "Опиши ситуацию несколькими предложениями"
    )
    assert tone.field_card("situation") == (
        "Соберем эпизод\n\n"
        "<blockquote>"
        "• коллега раскритиковал мой текст в чате\n"
        "• партнёр не ответил на сообщение вечером\n"
        "• я увидел дедлайн в календаре утром"
        "</blockquote>\n\n"
        "Опиши ситуацию несколькими предложениями"
    )


def test_expanded_field_cards_render_source_copy():
    tone = ToneEngine.default()

    assert tone.field_card("trigger") == (
        "Выявление триггера\n\n"
        "<blockquote>"
        "• резкий комментарий в чате\n"
        "• уведомление от банка\n"
        "• воспоминание о конфликте"
        "</blockquote>\n\n"
        "Что именно спровоцировало, зацепило или запустило реакцию?"
    )
    assert tone.field_card("actor") == (
        "Определение участников\n\n"
        "<blockquote>"
        "• я и коллега\n"
        "• партнёр\n"
        "• начальник и команда"
        "</blockquote>\n\n"
        "Кто был рядом, влиял или участвовал в ситуации?"
    )
    assert tone.field_card("quote") == (
        "Зафиксировать цитату\n\n"
        "<blockquote>"
        "• коллега: «это не подходит»\n"
        "• я написал: «ок»\n"
        "• сообщений не было"
        "</blockquote>\n\n"
        "Какая фраза или сообщение зафиксировались во внимании?"
    )


def test_every_field_card_has_required_sections():
    tone = ToneEngine.default()

    for target in OBSERVED_FIELDS:
        card = tone.field_card(target)
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
        assert guide["name"] in card
        assert guide["description"] not in card
        assert guide["formula"] not in card
        assert guide["question"] in card
        for example in guide["examples"]:
            assert f"• {example}" in card
        for tip in guide["tips"]:
            assert tip not in card


def test_emotion_card_uses_plain_text_frame():
    tone = ToneEngine.default()

    assert tone.field_card("emotion") == (
        "Определение эмоций\n\n"
        "<blockquote>"
        "• растерянность, оцепенение, беспомощность\n"
        "• тревога с раздражением\n"
        "• стыд и растерянность"
        "</blockquote>\n\n"
        "Какие эмоции были самыми яркими в эпизоде?"
    )


def test_session_messages_render_concise_prompts():
    tone = ToneEngine.default()
    situation_prompt = tone.target_prompt("situation")
    behavior_prompt = tone.target_prompt("behavior")

    assert tone.empty_answer("situation") == (
        f"Нужен непустой ответ\n\n{situation_prompt}"
    )
    assert tone.start_session(situation_prompt) == (
        "□□□□□□□□□□ 0/10\n\n"
        "Опиши ситуацию несколькими предложениями"
    )
    assert tone.next_prompt_bridge(1, 10, behavior_prompt) == (
        f"■□□□□□□□□□ 1/10\n\n{behavior_prompt}"
    )
    assert tone.review_screen(
        {
            "situation": {"value": "s"},
            "trigger": {"value": "tr"},
            "actor": {"value": "ac"},
            "quote": {"value": "sp"},
            "automatic_thought": {"value": "at"},
            "emotion": {"value": "e"},
            "behavior": {"value": "b"},
            "physical": {"value": "physical"},
            "short_term_consequence": {"value": "st"},
            "long_term_consequence": {"value": "lt"},
        }
    ) == (
        "■■■■■■■■■■ 10/10 💯\n\n"
        "ситуация: s\n"
        "триггер: tr\n"
        "участник: ac\n"
        "цитата: sp\n"
        "мысль: at\n"
        "эмоция: e\n"
        "действие: b\n"
        "физическое: physical\n"
        "сразу после: st\n"
        "потом: lt\n\n"
        "Сохраняем?"
    )
    assert tone.complete() == "Готово. Эпизод собран"
    assert tone.already_complete() == "Эпизод уже собран"
    assert tone.status("situation", 1, 10) == "Текущий шаг: situation\nЗаполнено: 1/10"
    assert tone.help() == (
        "МИШа\n"
        "машина извлечения шаблонов\n"
        "(аналитическая)\n\n"
        "Бот не ставит диагнозы и не даёт советов\n"
        "Он помогает аккуратно зафиксировать один эпизод по CBT/ACT-фрейму\n\n"
        "Команды:\n"
        "/start или /10q — десять коротких вопросов\n"
        "/3b — три последовательных блока\n"
        "/1t — один текст, затем только недостающее\n"
        "/1a — одно голосовое или аудио\n"
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
    assert tone.waitlisted() == (
        "Спасибо за интерес. Мы добавили тебя в waitlist. "
        "Напишем, как только доступ откроется"
    )
    assert tone.admin_waitlist_notice(
        456,
        "456",
        {
            "username": "tester",
            "first_name": "Test",
            "language_code": "en",
        },
    ) == (
        "Новый пользователь в waitlist\n"
        "chat_id: 456\n"
        "user_id: 456\n"
        "username: tester\n"
        "first_name: Test\n"
        "language_code: en\n\n"
        "/approve 456\n"
        "/pause 456"
    )
    assert tone.admin_approved(456) == "Доступ одобрен для 456"
    assert tone.approval_granted() == "Доступ открыт. Отправь /start, чтобы начать."
    assert tone.admin_paused(456) == "Заявка поставлена на паузу для 456"
    assert tone.admin_bad_command("/approve") == "Используй /approve &lt;chat_id&gt;"
    assert tone.profile_missing() == (
        "Профиль пока не собран. Нужны сохранённые и обработанные эпизоды."
    )
    assert tone.report_failed("broken <data>") == (
        "Не удалось собрать отчёт: broken &lt;data&gt;"
    )
    assert tone.graph_reports_ready(
        episodes=1,
        observed_count=1,
        annotated_count=1,
        pending_count=0,
        coverage="full",
        invalid=0,
        empty_derived=0,
        annotation_ready=1,
        graph_ready=1,
        report_ready=1,
        payload_eligible=1,
    ) == (
        "Отчёт собран\n"
        "episodes: 1\n"
        "coverage: 1/1 annotated (full); pending: 0\n"
        "invalid: 0\n"
        "empty_derived: 0\n"
        "annotation_ready: 1\n"
        "graph_ready: 1\n"
        "report_ready: 1\n"
        "payload_eligible: 1"
    )
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
        "waitlisted",
        "admin_waitlist_notice",
        "admin_approved",
        "approval_granted",
        "admin_paused",
        "admin_bad_command",
        "profile_missing",
        "report_failed",
        "graph_reports_ready",
        "expired_initial_session",
        "saved_episode",
    }


def test_bot_profile_messages_render_unchanged():
    tone = ToneEngine.default()

    assert tone.bot_short_description() == (
        "МИШа собирает один CBT/ACT-эпизод короткими вопросами"
    )
    assert tone.bot_description() == (
        "МИШа — машина извлечения шаблонов аналитическая\n\n"
        "Помогает собрать один конкретный эпизод: факт, действие, последствия, "
        "мысль, эмоцию и тело\n\n"
        "Начни с /start"
    )
    assert BOT_PROFILE == {
        "short_description": "МИШа собирает один CBT/ACT-эпизод короткими вопросами",
        "description": (
            "МИШа — машина извлечения шаблонов аналитическая\n\n"
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

    assert tone.command_description("start") == "Начать 10 вопросов"
    assert tone.command_description("10q") == "Эпизод через 10 вопросов"
    assert tone.command_description("3b") == "Эпизод через 3 блока"
    assert tone.command_description("1t") == "Эпизод одним текстом"
    assert tone.command_description("1a") == "Эпизод голосом или аудио"
    assert tone.command_description("cancel") == "Отменить сессию"
    assert tone.command_description("help") == "Показать команды"
    assert COMMAND_DESCRIPTIONS == {
        "start": "Начать 10 вопросов",
        "10q": "Эпизод через 10 вопросов",
        "3b": "Эпизод через 3 блока",
        "1t": "Эпизод одним текстом",
        "1a": "Эпизод голосом или аудио",
        "cancel": "Отменить сессию",
        "help": "Показать команды",
    }


def test_default_prompts_avoid_forbidden_style_terms():
    tone = ToneEngine.default()
    prompt_text = "\n".join(tone.prompts.values()).lower()

    for forbidden in tone.forbidden:
        assert forbidden.lower() not in prompt_text

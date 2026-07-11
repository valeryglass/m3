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


def test_field_guides_keep_only_runtime_copy():
    tone = ToneEngine.default()

    assert (
        tone.target_prompt("situation")
        == "Опиши ситуацию несколькими предложениями"
    )

    for target in OBSERVED_FIELDS:
        guide = tone.field_guide(target)
        assert set(guide) == {"label", "question"}
        assert guide["label"]
        assert guide["question"] == TARGET_PROMPTS[target]


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
        "/status — показать текущий шаг\n"
        "/profile — открыть короткий и подробный отчёт\n"
        "/cancel — отменить сессию\n"
        "/help — показать команды\n\n"
        "Связь: @mesto3"
    )
    assert tone.no_active_loop() == "Активной сессии нет"
    assert tone.no_active_loop_start() == (
        "Сейчас активной сессии нет. Отправь /start, чтобы начать новый эпизод"
    )
    assert tone.cancel() == "Сессия отменена"
    assert tone.unknown_command() == "Неизвестная команда. Открой /help."
    assert tone.unauthorized() == "Нет доступа"
    assert tone.waitlisted() == (
        "Спасибо за интерес. Мы добавили тебя в waitlist. "
        "Напишем, как только доступ откроется"
    )
    assert "beta-1" in tone.consent_notice("beta-1")
    assert "18+" in tone.consent_notice("beta-1")
    assert tone.consent_accepted() == (
        "Согласие сохранено. Теперь можно отправить /start."
    )
    assert tone.consent_declined().startswith("Согласие не дано")
    assert "приватный чат" in tone.private_chat_required()
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
    assert tone.approval_granted() == (
        "Доступ открыт. Отправь /start: перед первым эпизодом бот покажет условия."
    )
    assert tone.admin_paused(456) == "Заявка поставлена на паузу для 456"
    assert tone.admin_bad_command("/approve") == "Используй /approve &lt;chat_id&gt;"
    assert tone.profile_missing() == (
        "Профиль пока не собран. Нужны сохранённые и обработанные эпизоды."
    )
    assert tone.profile_updating().startswith("Обработка отчёта пока не завершена")
    assert tone.report_failed("broken <data>") == (
        "Не удалось собрать отчёт: broken &lt;data&gt;"
    )
    assert tone.graph_reports_ready(
        episodes=1,
        selected_run_id="run-test",
        freshness="ready",
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
        "run: run-test\n"
        "freshness: ready\n"
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
        "unknown_command",
        "unauthorized",
        "waitlisted",
        "private_chat_required",
        "consent_notice",
        "consent_accepted",
        "consent_declined",
        "consent_stale",
        "admin_waitlist_notice",
        "admin_approved",
        "approval_granted",
        "admin_paused",
        "admin_bad_command",
        "profile_missing",
        "profile_updating",
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
    assert tone.command_description("status") == "Показать текущий шаг"
    assert tone.command_description("profile") == "Показать профиль и отчёт"
    assert tone.command_description("cancel") == "Отменить сессию"
    assert tone.command_description("help") == "Показать команды"
    assert COMMAND_DESCRIPTIONS == {
        "start": "Начать 10 вопросов",
        "10q": "Эпизод через 10 вопросов",
        "3b": "Эпизод через 3 блока",
        "1t": "Эпизод одним текстом",
        "1a": "Эпизод голосом или аудио",
        "status": "Показать текущий шаг",
        "profile": "Показать профиль и отчёт",
        "cancel": "Отменить сессию",
        "help": "Показать команды",
    }


def test_default_prompts_avoid_forbidden_style_terms():
    tone = ToneEngine.default()
    prompt_text = "\n".join(tone.prompts.values()).lower()

    for forbidden in tone.forbidden:
        assert forbidden.lower() not in prompt_text

from __future__ import annotations


FIELD_GUIDES = {
    "situation": {
        "field": "situation",
        "source_field": "situation.event_description",
        "description": "Что произошло фактически. Без анализа и выводов.",
        "formula": "[кто] → [действие] → [контекст]",
        "examples": (
            "коллега раскритиковал мой текст в чате",
            "партнёр не ответил на сообщение вечером",
            "я увидел дедлайн в календаре утром",
        ),
        "tips": (
            "камера, не интерпретация",
            "один конкретный момент",
            "кто → что сделал",
        ),
        "question": "Что произошло конкретно? 1-2 предложения.",
    },
    "behavior": {
        "field": "behavior",
        "source_field": "behavior.action",
        "description": "Совершённое действие.",
        "formula": "[субъект] → [действие]",
        "examples": (
            "закрыл телеграм",
            "не стал отвечать на письмо",
            "перечитал задачу три раза",
        ),
        "tips": (
            "через глагол",
            "что сделал фактически",
            "порядок действий важен",
        ),
        "question": "Что ты сделал или чего избежал?",
    },
    "short_term_consequence": {
        "field": "short_term_consequence",
        "source_field": "immediate_result",
        "description": "Мгновенный эффект поведения.",
        "formula": "[действие] → [мгновенный эффект]",
        "examples": (
            "тревога снизилась",
            "стало легче на пару минут",
            "я почувствовал контроль",
        ),
        "tips": (
            "что изменилось сразу",
            "ищи relief/control",
            "краткосрочный эффект",
        ),
        "question": "Что случилось сразу после этого?",
    },
    "long_term_consequence": {
        "field": "long_term_consequence",
        "source_field": "consequence",
        "description": "Отложенное последствие поведения.",
        "formula": "[действие] → [отложенный эффект]",
        "examples": (
            "задача осталась нерешённой",
            "я снова отложил разговор",
            "напряжение вернулось вечером",
        ),
        "tips": (
            "что стало потом",
            "ищи закрепление цикла",
            "LT-эффект важнее эмоции",
        ),
        "question": "Что осталось потом или к чему это привело?",
    },
    "automatic_thought": {
        "field": "automatic_thought",
        "source_field": "automatic_thought.text",
        "description": "Быстрая автоматическая мысль.",
        "formula": "[субъект] + [оценка/прогноз]",
        "examples": (
            "я всё испортил",
            "сейчас меня осудят",
            "надо срочно всё исправить",
        ),
        "tips": (
            "первая мысль важнее",
            "не редактируй",
            "короткая фраза",
        ),
        "question": "Какая мысль, картинка или смысл мелькнули в моменте?",
    },
    "emotion": {
        "field": "emotion",
        "source_field": "emotion.label",
        "description": "Испытываемая эмоция.",
        "formula": "[название эмоции]",
        "examples": (
            "тревога",
            "стыд",
            "злость",
        ),
        "tips": (
            "эмоция ≠ мысль",
            "можно несколько",
            "называй базово",
        ),
        "question": "Какая эмоция была?",
    },
    "body": {
        "field": "body",
        "source_field": "body_sensation.sensation",
        "description": "Телесное ощущение.",
        "formula": "[ощущение] + [зона тела]",
        "examples": (
            "напряжение в груди",
            "жар в лице",
            "сжатие в животе",
        ),
        "tips": (
            "сканируй тело",
            "где именно?",
            "ищи давление/жар",
        ),
        "question": "Что было в теле?",
    },
}


TARGET_PROMPTS = {
    target: guide["question"] for target, guide in FIELD_GUIDES.items()
}


BOT_PROFILE = {
    "short_description": "Собирает один CBT-эпизод короткими вопросами.",
    "description": (
        "Бот помогает зафиксировать один конкретный эпизод: что произошло, "
        "что ты сделал, что было потом, какая мысль мелькнула, эмоция и тело. "
        "Начни с /start."
    ),
}


SESSION_MESSAGES = {
    "field_card": (
        "📝 Описание\n{description}\n\n"
        "🧬 Формула\n{formula}\n\n"
        "🎯 Пример\n{example}\n\n"
        "💡 Подсказки\n{tips}\n\n"
        "{question}"
    ),
    "empty_answer": "Нужен непустой ответ.",
    "start_session": "Соберём один конкретный эпизод.\n\n{prompt}",
    "next_prompt_bridge": "Записал. {completed_count}/{total_count}\n\n{prompt}",
    "complete": "Готово. Эпизод собран.",
    "already_complete": "Эпизод уже собран.",
    "status": "Текущий шаг: {target}\nЗаполнено: {completed_count}/{total_count}",
    "help": (
        "Команды:\n"
        "/start — начать новый эпизод\n"
        "/cancel — отменить сессию\n"
        "/help — показать команды"
    ),
    "no_active_loop": "Активной сессии нет.",
    "no_active_loop_start": "Активной сессии нет. Отправь /start, чтобы начать.",
    "cancel": "Сессия отменена.",
    "unauthorized": "Нет доступа.",
    "expired_initial_session": (
        "Прошлая сессия истекла до первого ответа. Отправь /start заново."
    ),
    "saved_episode": "{reply}",
}


COMMAND_DESCRIPTIONS = {
    "start": "Начать новый эпизод",
    "cancel": "Отменить сессию",
    "help": "Показать команды",
}

from __future__ import annotations


FIELD_GUIDES = {
    "situation": {
        "field": "situation",
        "label": "ситуация",
        "source_field": "situation.event_description",
        "description": "Что произошло фактически. Без анализа и выводов",
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
        "question": "Опиши ситуацию несколькими предложениями",
    },
    "trigger": {
        "field": "trigger",
        "label": "триггер",
        "source_field": "trigger.description",
        "description": "Что стало пусковым стимулом",
        "formula": "[стимул] → [активация реакции]",
        "examples": (
            "резкий комментарий в чате",
            "уведомление от банка",
            "воспоминание о конфликте",
        ),
        "tips": (
            "что именно зацепило",
            "может быть мысль или тело",
            "минимальный стимул",
        ),
        "question": "Что именно зацепило или запустило реакцию?",
    },
    "actors": {
        "field": "actors",
        "label": "участники",
        "source_field": "actors",
        "description": "Кто был вовлечён в эпизод",
        "formula": "[кто участвовал]",
        "examples": (
            "я и коллега",
            "партнёр",
            "начальник и команда",
        ),
        "tips": (
            "можно роли без имён",
            "кто влиял на момент",
            "короткий список",
        ),
        "question": "Кто был вовлечён в ситуацию?",
    },
    "speech": {
        "field": "speech",
        "label": "речь",
        "source_field": "speech",
        "description": "Точные слова или сообщения",
        "formula": "[кто] → [что сказал/написал]",
        "examples": (
            "коллега: «это не подходит»",
            "я написал: «ок»",
            "сообщений не было",
        ),
        "tips": (
            "дословно если помнишь",
            "можно одним фрагментом",
            "если речи не было — так и напиши",
        ),
        "question": "Какие слова или сообщения там были?",
    },
    "behavior": {
        "field": "behavior",
        "label": "действие",
        "source_field": "behavior.action",
        "description": "Совершённое действие",
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
        "question": "Как ты поступил в этой ситуации, что сделал?",
    },
    "short_term_consequence": {
        "field": "short_term_consequence",
        "label": "сразу после",
        "source_field": "immediate_result",
        "description": "Мгновенный эффект поведения",
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
        "question": "Что случилось сразу после твоего поступка?",
    },
    "long_term_consequence": {
        "field": "long_term_consequence",
        "label": "потом",
        "source_field": "consequence",
        "description": "Отложенное последствие поведения",
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
        "question": "К чему это привело в дальнейшем?",
    },
    "automatic_thought": {
        "field": "automatic_thought",
        "label": "мысль",
        "source_field": "automatic_thought.text",
        "description": "Быстрая автоматическая мысль",
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
        "label": "эмоция",
        "source_field": "emotion.label",
        "description": "Испытываемая эмоция",
        "formula": "[название эмоции]",
        "examples": (
            "растерянность, оцепенение, беспомощность",
        ),
        "tips": (
            "эмоция ≠ мысль",
            "можно несколько",
            "называй базово",
        ),
        "question": (
            "Выбери одну или несколько эмоций\n"
            "Щёлкай несколько раз, чтобы выбрать интенсивность\n"
            "Можешь написать дополнительно, что чувствовал"
        ),
    },
    "body": {
        "field": "body",
        "label": "тело",
        "source_field": "body_sensation.sensation",
        "description": "Телесное ощущение",
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
        "question": "Что ощущалось в теле?",
    },
}


EMOTION_BUCKETS = (
    {"key": "neutral", "label": "нейтраль/мешанные"},
    {"key": "warmth", "label": "любовь/тепло"},
    {"key": "joy", "label": "радость"},
    {"key": "disgust", "label": "отвращение"},
    {"key": "shame", "label": "стыд"},
    {"key": "sadness", "label": "грусть"},
    {"key": "anger", "label": "злость"},
    {"key": "fear", "label": "страх"},
)


EMOTION_INTENSITIES = {
    1: 0.33,
    2: 0.66,
    3: 1.0,
}


EMOTION_INTENSITY_MARKS = {
    1: "▁",
    2: "▄",
    3: "█",
}


BASIC_TARGETS = (
    "situation",
    "behavior",
    "short_term_consequence",
    "long_term_consequence",
    "automatic_thought",
    "emotion",
    "body",
)


FULL_TARGETS = (
    "situation",
    "trigger",
    "actors",
    "speech",
    "behavior",
    "short_term_consequence",
    "long_term_consequence",
    "automatic_thought",
    "emotion",
    "body",
)


TARGET_PROMPTS = {
    target: FIELD_GUIDES[target]["question"] for target in BASIC_TARGETS
}


BOT_PROFILE = {
    "short_description": "МИШа собирает один CBT/ACT-эпизод короткими вопросами",
    "description": (
        "МИШа — машина извлечения шаблонов\n\n"
        "Помогает собрать один конкретный эпизод: факт, действие, последствия, "
        "мысль, эмоцию и тело\n\n"
        "Начни с /start"
    ),
}


SESSION_MESSAGES = {
    "field_card": (
        "{name}\n\n"
        "<blockquote>{example}</blockquote>\n\n"
        "{question}"
    ),
    "empty_answer": "Нужен непустой ответ",
    "start_session": (
        "Соберём один конкретный эпизод. Идём коротко, не спеша, по фактам\n\n"
        "{progress_bar} {completed_count}/{total_count}\n\n"
        "{prompt}"
    ),
    "next_prompt_bridge": (
        "{progress_bar} {completed_count}/{total_count}\n\n{prompt}"
    ),
    "review_screen": "{progress_bar} {completed_count}/{total_count} 💯\n\n{overview}\n\nСохраняем?",
    "complete": "Готово. Эпизод собран",
    "already_complete": "Эпизод уже собран",
    "status": "Текущий шаг: {target}\nЗаполнено: {completed_count}/{total_count}",
    "help": (
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
    ),
    "no_active_loop": "Активной сессии нет",
    "no_active_loop_start": (
        "Сейчас активной сессии нет. Отправь /start, чтобы начать новый эпизод"
    ),
    "cancel": "Сессия отменена",
    "unauthorized": "Нет доступа",
    "emotion_buttons_required": "Выбери эмоции кнопками и нажми Готово",
    "waitlisted": (
        "Спасибо за интерес. Мы добавили тебя в waitlist. "
        "Напишем, как только доступ откроется"
    ),
    "admin_waitlist_notice": (
        "Новый пользователь в waitlist\n"
        "chat_id: {chat_id}\n"
        "user_id: {user_id}\n\n"
        "/approve {chat_id}\n"
        "/pause {chat_id}"
    ),
    "admin_approved": "Доступ одобрен для {chat_id}",
    "approval_granted": "Доступ открыт. Отправь /start, чтобы начать.",
    "admin_paused": "Заявка поставлена на паузу для {chat_id}",
    "admin_bad_command": "Используй {command} &lt;chat_id&gt;",
    "expired_initial_session": (
        "Прошлая сессия истекла до первого ответа. Отправь /start заново"
    ),
    "saved_episode": "{reply}\n\nВсего эпизодов: {episode_count}",
}


COMMAND_DESCRIPTIONS = {
    "start": "Начать новый эпизод",
    "cancel": "Отменить сессию",
    "help": "Показать команды",
}

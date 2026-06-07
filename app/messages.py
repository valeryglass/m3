from __future__ import annotations


FIELD_GUIDES = {
    "situation": {
        "field": "situation",
        "label": "ситуация",
        "name": "Соберем эпизод",
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
        "name": "Выявление триггера",
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
        "question": "Что именно спровоцировало, зацепило или запустило реакцию?",
    },
    "actor": {
        "field": "actor",
        "label": "участник",
        "name": "Определение участников",
        "source_field": "actor",
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
        "question": "Кто был рядом, влиял или участвовал в ситуации?",
    },
    "quote": {
        "field": "quote",
        "label": "цитата",
        "name": "Зафиксировать цитату",
        "source_field": "quote",
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
        "question": "Какая фраза или сообщение зафиксировались во внимании?",
    },
    "behavior": {
        "field": "behavior",
        "label": "действие",
        "name": "Определение действия",
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
        "question": "Как ты поступил или что предпринял?",
    },
    "short_term_consequence": {
        "field": "short_term_consequence",
        "label": "сразу после",
        "name": "Краткосрочные последствия",
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
        "question": "Что случилось сразу после?",
    },
    "long_term_consequence": {
        "field": "long_term_consequence",
        "label": "потом",
        "name": "Долгосрочные последствия",
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
        "question": "Как изменилось состояние со временем или к чему это привело дальше?",
    },
    "automatic_thought": {
        "field": "automatic_thought",
        "label": "мысль",
        "name": "Фиксация мысли",
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
        "name": "Определение эмоций",
        "source_field": "emotion.label",
        "description": "Испытываемая эмоция",
        "formula": "[название эмоции]",
        "examples": (
            "растерянность, оцепенение, беспомощность",
            "тревога с раздражением",
            "стыд и растерянность",
        ),
        "tips": (
            "эмоция ≠ мысль",
            "можно несколько",
            "называй базово",
        ),
        "question": (
            "Какие эмоции были самыми яркими в эпизоде?"
        ),
    },
    "physical": {
        "field": "physical",
        "label": "физическое",
        "name": "Реакция тела",
        "source_field": "physical.sensation",
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
        "question": "Какие ощущения были в теле в течение эпизода?",
    },
}


TARGETS = (
    "situation",
    "trigger",
    "actor",
    "quote",
    "automatic_thought",
    "emotion",
    "behavior",
    "physical",
    "short_term_consequence",
    "long_term_consequence",
)


TARGET_PROMPTS = {
    target: FIELD_GUIDES[target]["question"] for target in TARGETS
}


BOT_PROFILE = {
    "short_description": "МИШа собирает один CBT/ACT-эпизод короткими вопросами",
    "description": (
        "МИШа — машина извлечения шаблонов аналитическая\n\n"
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
    "waitlisted": (
        "Спасибо за интерес. Мы добавили тебя в waitlist. "
        "Напишем, как только доступ откроется"
    ),
    "admin_waitlist_notice": (
        "Новый пользователь в waitlist\n"
        "chat_id: {chat_id}\n"
        "user_id: {user_id}"
        "{profile}\n\n"
        "/approve {chat_id}\n"
        "/pause {chat_id}"
    ),
    "admin_approved": "Доступ одобрен для {chat_id}",
    "approval_granted": "Доступ открыт. Отправь /start, чтобы начать.",
    "admin_paused": "Заявка поставлена на паузу для {chat_id}",
    "admin_bad_command": "Используй {command} &lt;chat_id&gt;",
    "profile_missing": (
        "Профиль пока не собран. Нужны сохранённые и обработанные эпизоды."
    ),
    "report_failed": "Не удалось собрать отчёт: {error}",
    "graph_reports_ready": (
        "Отчёт собран\n"
        "episodes: {episodes}\n"
        "coverage: {annotated_count}/{observed_count} annotated ({coverage}); pending: {pending_count}\n"
        "invalid: {invalid}\n"
        "empty_derived: {empty_derived}\n"
        "annotation_ready: {annotation_ready}\n"
        "graph_ready: {graph_ready}\n"
        "report_ready: {report_ready}\n"
        "payload_eligible: {payload_eligible}"
    ),
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

from __future__ import annotations


FIELD_GUIDES = {
    "situation": {
        "label": "ситуация",
        "question": "Опиши ситуацию несколькими предложениями",
    },
    "trigger": {
        "label": "триггер",
        "question": "Что именно спровоцировало, зацепило или запустило реакцию?",
    },
    "actor": {
        "label": "участник",
        "question": "Кто был рядом, влиял или участвовал в ситуации?",
    },
    "quote": {
        "label": "цитата",
        "question": "Какая фраза или сообщение зафиксировались во внимании?",
    },
    "behavior": {
        "label": "действие",
        "question": "Как ты поступил или что предпринял?",
    },
    "short_term_consequence": {
        "label": "сразу после",
        "question": "Что случилось сразу после?",
    },
    "long_term_consequence": {
        "label": "потом",
        "question": "Как изменилось состояние со временем или к чему это привело дальше?",
    },
    "automatic_thought": {
        "label": "мысль",
        "question": "Какая мысль, картинка или смысл мелькнули в моменте?",
    },
    "emotion": {
        "label": "эмоция",
        "question": (
            "Какие эмоции были самыми яркими в эпизоде?"
        ),
    },
    "physical": {
        "label": "физическое",
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
        "/start или /10q — десять коротких вопросов\n"
        "/3b — три последовательных блока\n"
        "/1t — один текст, затем только недостающее\n"
        "/1a — одно голосовое или аудио\n"
        "/status — показать текущий шаг\n"
        "/profile — открыть короткий и подробный отчёт\n"
        "/cancel — отменить сессию\n"
        "/help — показать команды\n\n"
        "Связь: @mesto3"
    ),
    "no_active_loop": "Активной сессии нет",
    "no_active_loop_start": (
        "Сейчас активной сессии нет. Отправь /start, чтобы начать новый эпизод"
    ),
    "cancel": "Сессия отменена",
    "unknown_command": "Неизвестная команда. Открой /help.",
    "unauthorized": "Нет доступа",
    "waitlisted": (
        "Спасибо за интерес. Мы добавили тебя в waitlist. "
        "Напишем, как только доступ откроется"
    ),
    "private_chat_required": (
        "Для работы с личными эпизодами открой приватный чат с ботом. "
        "В группах и каналах ввод не принимается."
    ),
    "consent_notice": (
        "Перед началом нужно подтвердить условия beta ({notice_version}).\n\n"
        "Бот предназначен только для пользователей 18+. Он хранит введённые "
        "эпизоды и служебные артефакты приватно у оператора. Для /1t, /3b и /1a "
        "подтверждённый текст может передаваться настроенному DeepSeek API для "
        "структурирования. Бот не ставит диагнозы и не заменяет специалиста.\n\n"
        "Нажимая «18+, принимаю», ты подтверждаешь возраст и согласие на такую "
        "обработку. Можно отказаться и запросить у оператора экспорт или удаление."
    ),
    "consent_accepted": "Согласие сохранено. Теперь можно отправить /start.",
    "consent_declined": (
        "Согласие не дано. Бот не будет принимать новые эпизоды. "
        "Можно вернуться к /start позже."
    ),
    "consent_stale": "Условия обновились. Прочитай актуальную версию и выбери снова.",
    "admin_waitlist_notice": (
        "Новый пользователь в waitlist\n"
        "chat_id: {chat_id}\n"
        "user_id: {user_id}"
        "{profile}\n\n"
        "/approve {chat_id}\n"
        "/pause {chat_id}"
    ),
    "admin_approved": "Доступ одобрен для {chat_id}",
    "approval_granted": (
        "Доступ открыт. Отправь /start: перед первым эпизодом бот покажет условия."
    ),
    "admin_paused": "Заявка поставлена на паузу для {chat_id}",
    "admin_bad_command": "Используй {command} &lt;chat_id&gt;",
    "profile_missing": (
        "Профиль пока не собран. Нужны сохранённые и обработанные эпизоды."
    ),
    "profile_updating": (
        "Обработка отчёта пока не завершена. Попробуй открыть /profile немного позже."
    ),
    "report_failed": "Не удалось собрать отчёт: {error}",
    "graph_reports_ready": (
        "Отчёт собран\n"
        "run: {selected_run_id}\n"
        "freshness: {freshness}\n"
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

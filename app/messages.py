from __future__ import annotations


TARGET_PROMPTS = {
    "situation": "Что произошло конкретно? 1-2 предложения.",
    "behavior": "Что ты сделал или чего избежал?",
    "short_term_consequence": "Что случилось сразу после этого?",
    "long_term_consequence": "Что осталось потом или к чему это привело?",
    "automatic_thought": "Какая мысль, картинка или смысл мелькнули в моменте?",
    "emotion": "Какая эмоция была?",
    "body": "Что было в теле?",
}


SESSION_MESSAGES = {
    "empty_answer": "Нужен непустой ответ.",
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
    "cancel": "Сессия отменена.",
    "unauthorized": "Нет доступа.",
    "expired_initial_session": (
        "Прошлая сессия истекла до первого ответа. Отправь /start заново."
    ),
    "saved_episode": "{reply}\nСохранено: {path}",
}


COMMAND_DESCRIPTIONS = {
    "start": "Начать новый эпизод",
    "cancel": "Отменить сессию",
    "help": "Показать команды",
}

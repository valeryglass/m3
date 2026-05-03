from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - dependency guard
    yaml = None


DEFAULT_TONE_CONFIG: dict[str, Any] = {
    "tone": {
        "name": "pragmatic_cbt_guide",
        "language": {
            "default": "ru",
            "style": "concise",
            "slang_allowed": True,
        },
        "voice": {
            "warm": 2,
            "direct": 5,
            "clinical": 2,
            "playful": 1,
            "supportive": 3,
        },
        "behavior": {
            "one_question_at_time": True,
            "avoid_long_explanations": True,
            "avoid_advice": True,
            "avoid_diagnosis": True,
            "keep_user_words": True,
        },
        "question_style": {
            "max_length": 140,
            "examples_allowed": True,
            "prefer_concrete_episode": True,
        },
        "forbidden": [
            "moralizing",
            "diagnosis",
            "personality_typing",
            "motivational_speech",
            "overexplaining",
        ],
    }
}


DEFAULT_PROMPTS = {
    "episode_date": "Дата эпизода? Формат YYYY-MM-DD.",
    "situation": "Что произошло конкретно? 1-2 предложения.",
    "behavior": "Что ты сделал или чего избежал?",
    "short_term_consequence": "Что случилось сразу после этого?",
    "long_term_consequence": "Что осталось потом или к чему это привело?",
    "automatic_thought": "Какая мысль, картинка или смысл мелькнули в моменте?",
    "emotion": "Какая эмоция была?",
    "body": "Что было в теле?",
}


@dataclass(frozen=True)
class ToneEngine:
    config: dict[str, Any]
    prompts: dict[str, str]

    @classmethod
    def default(cls) -> "ToneEngine":
        return cls(config=deepcopy(DEFAULT_TONE_CONFIG), prompts=dict(DEFAULT_PROMPTS))

    @property
    def max_question_length(self) -> int:
        return int(
            self.config["tone"].get("question_style", {}).get("max_length", 140)
        )

    @property
    def forbidden(self) -> tuple[str, ...]:
        return tuple(self.config["tone"].get("forbidden", ()))

    def target_prompt(self, target: str) -> str:
        if target == "complete":
            return self.complete()
        return self.prompts[target]

    def empty_answer(self, target: str) -> str:
        return f"Нужен непустой ответ.\n\n{self.target_prompt(target)}"

    def invalid_date(self) -> str:
        return "Нужна дата в формате YYYY-MM-DD."

    def complete(self) -> str:
        return "Готово. Эпизод собран."

    def already_complete(self) -> str:
        return "Эпизод уже собран."

    def status(self, target: str, completed_count: int, total_count: int) -> str:
        return f"Текущий шаг: {target}\nЗаполнено: {completed_count}/{total_count}"

    def no_active_loop(self) -> str:
        return "Активной сессии нет."

    def cancel(self) -> str:
        return "Сессия отменена."

    def unauthorized(self) -> str:
        return "Нет доступа."

    def expired_initial_session(self) -> str:
        return "Прошлая сессия истекла до первого ответа. Отправь /start заново."

    def saved_episode(self, reply: str, path: Path) -> str:
        return f"{reply}\nСохранено: {path}"


def load_tone_engine(path: Path | str) -> ToneEngine:
    path = Path(path)
    if yaml is None or not path.exists():
        return ToneEngine.default()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return ToneEngine.default()
    if not isinstance(data, dict):
        return ToneEngine.default()
    return ToneEngine(
        config=_deep_merge(DEFAULT_TONE_CONFIG, data),
        prompts=dict(DEFAULT_PROMPTS),
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

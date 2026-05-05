from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.messages import SESSION_MESSAGES, TARGET_PROMPTS

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


@dataclass(frozen=True)
class ToneEngine:
    config: dict[str, Any]
    prompts: dict[str, str]

    @classmethod
    def default(cls) -> "ToneEngine":
        return cls(config=deepcopy(DEFAULT_TONE_CONFIG), prompts=dict(TARGET_PROMPTS))

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
        return f"{SESSION_MESSAGES['empty_answer']}\n\n{self.target_prompt(target)}"

    def complete(self) -> str:
        return SESSION_MESSAGES["complete"]

    def already_complete(self) -> str:
        return SESSION_MESSAGES["already_complete"]

    def status(self, target: str, completed_count: int, total_count: int) -> str:
        return SESSION_MESSAGES["status"].format(
            target=target,
            completed_count=completed_count,
            total_count=total_count,
        )

    def no_active_loop(self) -> str:
        return SESSION_MESSAGES["no_active_loop"]

    def cancel(self) -> str:
        return SESSION_MESSAGES["cancel"]

    def unauthorized(self) -> str:
        return SESSION_MESSAGES["unauthorized"]

    def expired_initial_session(self) -> str:
        return SESSION_MESSAGES["expired_initial_session"]

    def saved_episode(self, reply: str, path: Path) -> str:
        return SESSION_MESSAGES["saved_episode"].format(reply=reply, path=path)


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
        prompts=dict(TARGET_PROMPTS),
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

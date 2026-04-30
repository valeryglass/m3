from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


OBSERVED_FIELDS = (
    "situation",
    "behavior",
    "short_term_consequence",
    "long_term_consequence",
    "automatic_thought",
    "emotion",
    "body",
)

TARGETS = (
    "episode_date",
    *OBSERVED_FIELDS,
    "atomic_thoughts",
    "cognitive_distortions",
)

QUESTIONS = {
    "episode_date": "Target: episode date.\n\nWhat date should this episode use? Send YYYY-MM-DD.",
    "situation": "Target: situation.\n\nWhat happened in this episode?",
    "behavior": "Target: behavior.\n\nWhat did you do or avoid doing?",
    "short_term_consequence": "Target: short-term consequence.\n\nWhat happened immediately after that?",
    "long_term_consequence": "Target: long-term consequence.\n\nWhat remained later, or what did it lead to?",
    "automatic_thought": "Target: automatic thought.\n\nWhat thought, image, prediction, or meaning showed up in the moment?",
    "emotion": "Target: emotion.\n\nWhat feeling was present?",
    "body": "Target: body.\n\nWhat did you notice in the body?",
    "atomic_thoughts": "Target: derived atomic thoughts.\n\nReply yes to use the automatic thought as one atomic thought, empty to leave none, or send a replacement wording.",
    "cognitive_distortions": "Target: derived cognitive distortions.\n\nReply empty to leave distortions empty, or send one clearly traceable distortion type.",
}

EMPTY_REPLIES = {"empty", "none", "no", "нет", "не", "пусто", "-"}
YES_REPLIES = {"yes", "y", "да", "ок", "ok", "ага"}


@dataclass
class LoopSession:
    chat_id: int
    target_index: int = 0
    episode_date: str | None = None
    observed: dict[str, dict[str, str]] = field(default_factory=dict)
    derived: dict[str, list[dict[str, str]]] = field(
        default_factory=lambda: {
            "atomic_thoughts": [],
            "cognitive_distortions": [],
        }
    )
    saved_episode_path: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopSession":
        return cls(
            chat_id=int(data["chat_id"]),
            target_index=int(data.get("target_index", 0)),
            episode_date=data.get("episode_date"),
            observed=dict(data.get("observed", {})),
            derived=dict(
                data.get(
                    "derived",
                    {"atomic_thoughts": [], "cognitive_distortions": []},
                )
            ),
            saved_episode_path=data.get("saved_episode_path"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "target_index": self.target_index,
            "episode_date": self.episode_date,
            "observed": self.observed,
            "derived": self.derived,
            "saved_episode_path": self.saved_episode_path,
        }


@dataclass(frozen=True)
class LoopResult:
    reply: str
    should_save: bool = False


def new_session(chat_id: int) -> LoopSession:
    return LoopSession(chat_id=chat_id)


def active_target(session: LoopSession) -> str:
    if session.target_index >= len(TARGETS):
        return "complete"
    return TARGETS[session.target_index]


def prompt_for_current_target(session: LoopSession) -> str:
    target = active_target(session)
    if target == "complete":
        return "Episode extraction is complete."
    return QUESTIONS[target]


def completed_observed_count(session: LoopSession) -> int:
    return sum(1 for field_name in OBSERVED_FIELDS if field_name in session.observed)


def status_text(session: LoopSession) -> str:
    return (
        f"Active target: {active_target(session)}\n"
        f"Observed fields: {completed_observed_count(session)}/{len(OBSERVED_FIELDS)}"
    )


def apply_user_reply(session: LoopSession, text: str) -> LoopResult:
    value = text.strip()
    if not value:
        return LoopResult(
            reply=f"I need a non-empty answer for this target.\n\n{prompt_for_current_target(session)}"
        )

    target = active_target(session)
    if target == "complete":
        return LoopResult(reply="Episode extraction is already complete.")

    if target == "episode_date":
        return _apply_episode_date(session, value)
    if target in OBSERVED_FIELDS:
        return _apply_observed_field(session, target, value)
    if target == "atomic_thoughts":
        return _apply_atomic_thoughts(session, value)
    if target == "cognitive_distortions":
        return _apply_cognitive_distortions(session, value)

    raise ValueError(f"Unknown target: {target}")


def _apply_episode_date(session: LoopSession, value: str) -> LoopResult:
    try:
        date.fromisoformat(value)
    except ValueError:
        return LoopResult(reply="Use YYYY-MM-DD for the episode date.")

    session.episode_date = value
    session.target_index += 1
    return LoopResult(reply=prompt_for_current_target(session))


def _apply_observed_field(
    session: LoopSession, target: str, value: str
) -> LoopResult:
    session.observed[target] = {
        "value": value,
        "source_quote": value,
    }
    session.target_index += 1
    return LoopResult(reply=prompt_for_current_target(session))


def _apply_atomic_thoughts(session: LoopSession, value: str) -> LoopResult:
    normalized = value.casefold()
    automatic_thought = session.observed.get("automatic_thought")

    if normalized in EMPTY_REPLIES or automatic_thought is None:
        session.derived["atomic_thoughts"] = []
    else:
        text = automatic_thought["value"] if normalized in YES_REPLIES else value
        session.derived["atomic_thoughts"] = [
            {
                "id": "atomic-thought-1",
                "text": text,
                "source_field": "observed.automatic_thought",
                "source_quote": automatic_thought["source_quote"],
                "confidence": "medium",
            }
        ]

    session.target_index += 1
    return LoopResult(reply=prompt_for_current_target(session))


def _apply_cognitive_distortions(session: LoopSession, value: str) -> LoopResult:
    normalized = value.casefold()
    atomic_thoughts = session.derived.get("atomic_thoughts", [])

    if normalized in EMPTY_REPLIES or not atomic_thoughts:
        session.derived["cognitive_distortions"] = []
    else:
        source = atomic_thoughts[0]
        session.derived["cognitive_distortions"] = [
            {
                "type": value,
                "source_atomic_thought": source["id"],
                "source_field": "observed.automatic_thought",
                "source_quote": source["source_quote"],
                "confidence": "low",
            }
        ]

    session.target_index += 1
    return LoopResult(reply="Episode extraction is complete.", should_save=True)

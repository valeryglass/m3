from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.tone_engine import ToneEngine


OBSERVED_FIELDS = (
    "situation",
    "behavior",
    "short_term_consequence",
    "long_term_consequence",
    "automatic_thought",
    "emotion",
    "body",
)

TARGETS = OBSERVED_FIELDS


@dataclass
class LoopSession:
    chat_id: int
    session_id: str | None = None
    target_index: int = 0
    last_prompted_at: str | None = None
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
            session_id=data.get("session_id"),
            target_index=int(data.get("target_index", 0)),
            last_prompted_at=data.get("last_prompted_at"),
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
            "session_id": self.session_id,
            "target_index": self.target_index,
            "last_prompted_at": self.last_prompted_at,
            "episode_date": self.episode_date,
            "observed": self.observed,
            "derived": self.derived,
            "saved_episode_path": self.saved_episode_path,
        }


@dataclass(frozen=True)
class LoopResult:
    reply: str
    should_save: bool = False


def new_session(
    chat_id: int,
    session_id: str | None = None,
    episode_date: str | None = None,
) -> LoopSession:
    return LoopSession(
        chat_id=chat_id,
        session_id=session_id,
        episode_date=episode_date or date.today().isoformat(),
    )


def active_target(session: LoopSession) -> str:
    if session.target_index >= len(TARGETS):
        return "complete"
    return TARGETS[session.target_index]


def prompt_for_current_target(
    session: LoopSession, tone: ToneEngine | None = None
) -> str:
    target = active_target(session)
    return _tone(tone).target_prompt(target)


def completed_observed_count(session: LoopSession) -> int:
    return sum(1 for field_name in OBSERVED_FIELDS if field_name in session.observed)


def status_text(session: LoopSession, tone: ToneEngine | None = None) -> str:
    return _tone(tone).status(
        active_target(session), completed_observed_count(session), len(OBSERVED_FIELDS)
    )


def apply_user_reply(
    session: LoopSession, text: str, tone: ToneEngine | None = None
) -> LoopResult:
    tone = _tone(tone)
    value = text.strip()
    if not value:
        return LoopResult(reply=tone.empty_answer(active_target(session)))

    target = active_target(session)
    if target == "complete":
        return LoopResult(reply=tone.already_complete())

    if target in OBSERVED_FIELDS:
        return _apply_observed_field(session, target, value, tone)

    raise ValueError(f"Unknown target: {target}")


def _apply_observed_field(
    session: LoopSession, target: str, value: str, tone: ToneEngine
) -> LoopResult:
    session.observed[target] = {
        "value": value,
        "source_quote": value,
    }
    session.target_index += 1
    if active_target(session) == "complete":
        return LoopResult(reply=tone.complete(), should_save=True)
    return LoopResult(reply=prompt_for_current_target(session, tone))


def _tone(tone: ToneEngine | None) -> ToneEngine:
    return tone if tone is not None else ToneEngine.default()

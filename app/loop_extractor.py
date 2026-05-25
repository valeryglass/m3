from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.messages import TARGETS
from app.derived_normalizer import empty_derived
from app.tone_engine import ToneEngine


FLOW_UNIFIED = "uniflow"
OBSERVED_FIELDS = TARGETS


@dataclass
class LoopSession:
    chat_id: int
    flow_mode: str = FLOW_UNIFIED
    session_id: str | None = None
    target_index: int = 0
    last_prompted_at: str | None = None
    episode_date: str | None = None
    observed: dict[str, dict[str, Any]] = field(default_factory=dict)
    derived: dict[str, list[dict[str, Any]]] = field(
        default_factory=empty_derived
    )
    saved_episode_path: str | None = None
    awaiting_save_confirmation: bool = False
    emotion_draft: dict[str, int] = field(default_factory=dict)
    emotion_free_text: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopSession":
        observed = _normalize_observed_keys(dict(data.get("observed", {})))
        flow_mode = _normalize_flow_mode(data.get("flow_mode"))
        return cls(
            chat_id=int(data["chat_id"]),
            flow_mode=flow_mode,
            session_id=data.get("session_id"),
            target_index=_target_index_for_observed(observed, flow_mode),
            last_prompted_at=data.get("last_prompted_at"),
            episode_date=data.get("episode_date"),
            observed=observed,
            derived=_normalize_derived(data.get("derived")),
            saved_episode_path=data.get("saved_episode_path"),
            awaiting_save_confirmation=bool(
                data.get("awaiting_save_confirmation", False)
            ),
            emotion_draft=_normalize_emotion_draft(data.get("emotion_draft", {})),
            emotion_free_text=_normalize_optional_text(data.get("emotion_free_text")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "flow_mode": self.flow_mode,
            "session_id": self.session_id,
            "target_index": self.target_index,
            "last_prompted_at": self.last_prompted_at,
            "episode_date": self.episode_date,
            "observed": self.observed,
            "derived": self.derived,
            "saved_episode_path": self.saved_episode_path,
            "awaiting_save_confirmation": self.awaiting_save_confirmation,
            "emotion_draft": self.emotion_draft,
            "emotion_free_text": self.emotion_free_text,
        }


@dataclass(frozen=True)
class LoopResult:
    reply: str
    should_save: bool = False


def new_session(
    chat_id: int,
    session_id: str | None = None,
    episode_date: str | None = None,
    flow_mode: str = FLOW_UNIFIED,
) -> LoopSession:
    return LoopSession(
        chat_id=chat_id,
        flow_mode=_normalize_flow_mode(flow_mode),
        session_id=session_id,
        episode_date=episode_date or date.today().isoformat(),
    )


def active_target(session: LoopSession) -> str:
    targets = target_fields(session)
    if session.target_index >= len(targets):
        return "complete"
    return targets[session.target_index]


def target_fields(session: LoopSession) -> tuple[str, ...]:
    return OBSERVED_FIELDS


def prompt_for_current_target(
    session: LoopSession, tone: ToneEngine | None = None
) -> str:
    target = active_target(session)
    return _tone(tone).target_prompt(target)


def completed_observed_count(session: LoopSession) -> int:
    return sum(1 for field_name in target_fields(session) if field_name in session.observed)


def status_text(session: LoopSession, tone: ToneEngine | None = None) -> str:
    return _tone(tone).status(
        active_target(session), completed_observed_count(session), len(target_fields(session))
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

    if target in target_fields(session):
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


def _target_index_for_observed(
    observed: dict[str, dict[str, Any]], flow_mode: str = FLOW_UNIFIED
) -> int:
    for index, field_name in enumerate(OBSERVED_FIELDS):
        if field_name not in observed:
            return index
    return len(OBSERVED_FIELDS)


def _normalize_flow_mode(flow_mode: Any) -> str:
    return FLOW_UNIFIED


def _normalize_observed_keys(observed: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    renames = {
        "actors": "actor",
        "speech": "quote",
        "body": "physical",
    }
    for old_key, new_key in renames.items():
        if old_key in observed and new_key not in observed:
            observed[new_key] = observed.pop(old_key)
        elif old_key in observed:
            observed.pop(old_key)
    return observed


def _normalize_emotion_draft(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    draft: dict[str, int] = {}
    for key, level in value.items():
        if isinstance(key, str) and level in (1, 2, 3):
            draft[key] = int(level)
    return draft


def _normalize_optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _normalize_derived(value: Any) -> dict[str, list[dict[str, Any]]]:
    derived = empty_derived()
    if not isinstance(value, dict):
        return derived
    for key in derived:
        items = value.get(key)
        if isinstance(items, list):
            derived[key] = items
    return derived

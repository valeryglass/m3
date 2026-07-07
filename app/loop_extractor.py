from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.messages import TARGETS
from app.derived_normalizer import empty_derived
from app.episode_drafts import (
    DRAFT_STATUS_COMPLETE,
    DRAFT_STATUS_PARTIAL,
    EpisodeDraft,
    completed_draft_field_count as _completed_draft_field_count,
    draft_status as _draft_status,
    is_draft_complete as _is_draft_complete,
)
from app.gap_hydration import missing_draft_gaps, select_next_gap
from app.tone_engine import ToneEngine


FLOW_UNIFIED = "uniflow"
CAPTURE_FLOW_MODES = frozenset(
    {
        "classic_10q",
        "three_block",
        "one_take_text",
        "one_take_audio",
    }
)
OBSERVED_FIELDS = TARGETS
@dataclass
class LoopSession:
    chat_id: int
    flow_mode: str = FLOW_UNIFIED
    capture_funnel: str | None = None
    media_kind: str | None = None
    intake_transcript_path: str | None = None
    capture_id: str | None = None
    capture_artifact_path: str | None = None
    extraction_id: str | None = None
    extraction_path: str | None = None
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopSession":
        observed = _normalize_observed_keys(dict(data.get("observed", {})))
        flow_mode = _normalize_flow_mode(data.get("flow_mode"))
        return cls(
            chat_id=int(data["chat_id"]),
            flow_mode=flow_mode,
            capture_funnel=data.get("capture_funnel"),
            media_kind=data.get("media_kind"),
            intake_transcript_path=data.get("intake_transcript_path"),
            capture_id=data.get("capture_id"),
            capture_artifact_path=data.get("capture_artifact_path"),
            extraction_id=data.get("extraction_id"),
            extraction_path=data.get("extraction_path"),
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
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "flow_mode": self.flow_mode,
            "capture_funnel": self.capture_funnel,
            "media_kind": self.media_kind,
            "intake_transcript_path": self.intake_transcript_path,
            "capture_id": self.capture_id,
            "capture_artifact_path": self.capture_artifact_path,
            "extraction_id": self.extraction_id,
            "extraction_path": self.extraction_path,
            "session_id": self.session_id,
            "target_index": self.target_index,
            "last_prompted_at": self.last_prompted_at,
            "episode_date": self.episode_date,
            "observed": self.observed,
            "derived": self.derived,
            "saved_episode_path": self.saved_episode_path,
            "awaiting_save_confirmation": self.awaiting_save_confirmation,
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
    capture_funnel: str | None = None,
    media_kind: str | None = None,
    intake_transcript_path: str | None = None,
    capture_id: str | None = None,
    capture_artifact_path: str | None = None,
    extraction_id: str | None = None,
    extraction_path: str | None = None,
) -> LoopSession:
    return LoopSession(
        chat_id=chat_id,
        flow_mode=_normalize_flow_mode(flow_mode),
        capture_funnel=capture_funnel,
        media_kind=media_kind,
        intake_transcript_path=intake_transcript_path,
        capture_id=capture_id,
        capture_artifact_path=capture_artifact_path,
        extraction_id=extraction_id,
        extraction_path=extraction_path,
        session_id=session_id,
        episode_date=episode_date or date.today().isoformat(),
    )


def new_session_from_draft(
    chat_id: int,
    draft: EpisodeDraft,
    session_id: str | None = None,
    episode_date: str | None = None,
    flow_mode: str = FLOW_UNIFIED,
    capture_funnel: str | None = None,
    media_kind: str | None = None,
    intake_transcript_path: str | None = None,
    capture_id: str | None = None,
    capture_artifact_path: str | None = None,
    extraction_id: str | None = None,
    extraction_path: str | None = None,
) -> LoopSession:
    normalized_flow_mode = _normalize_flow_mode(flow_mode)
    observed = _normalize_observed_keys(dict(draft.observed))
    return LoopSession(
        chat_id=chat_id,
        flow_mode=normalized_flow_mode,
        capture_funnel=capture_funnel,
        media_kind=media_kind,
        intake_transcript_path=intake_transcript_path,
        capture_id=capture_id,
        capture_artifact_path=capture_artifact_path,
        extraction_id=extraction_id,
        extraction_path=extraction_path,
        session_id=session_id,
        target_index=_target_index_for_observed(observed, normalized_flow_mode),
        episode_date=episode_date or date.today().isoformat(),
        observed=observed,
    )


def active_target(session: LoopSession) -> str:
    return next_draft_target(session)


def target_fields(session: LoopSession) -> tuple[str, ...]:
    return OBSERVED_FIELDS


def prompt_for_current_target(
    session: LoopSession, tone: ToneEngine | None = None
) -> str:
    target = active_target(session)
    return _tone(tone).target_prompt(target)


def next_missing_draft_field(session: LoopSession) -> str | None:
    gaps = missing_draft_gaps(draft_observed_fields(session), target_fields(session))
    if not gaps:
        return None
    return gaps[0].field_name


def next_draft_target(session: LoopSession) -> str:
    gap = select_next_gap(
        draft_observed_fields(session),
        target_fields(session),
        target_index=session.target_index,
        current_order_only=True,
    )
    if gap is None:
        return "complete"
    return gap.field_name


def draft_observed_fields(session: LoopSession) -> dict[str, dict[str, Any]]:
    """Return the current provisional observed fields for the episode draft."""
    return session.observed


def completed_draft_field_count(session: LoopSession) -> int:
    return _completed_draft_field_count(draft_observed_fields(session), target_fields(session))


def draft_status(session: LoopSession) -> str:
    return _draft_status(draft_observed_fields(session), target_fields(session))


def is_draft_complete(session: LoopSession) -> bool:
    return _is_draft_complete(draft_observed_fields(session), target_fields(session))


def completed_observed_count(session: LoopSession) -> int:
    return completed_draft_field_count(session)


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
        return _apply_draft_field(session, target, value, tone)

    raise ValueError(f"Unknown target: {target}")


def _apply_draft_field(
    session: LoopSession, target: str, value: str, tone: ToneEngine
) -> LoopResult:
    draft_observed_fields(session)[target] = {
        "value": value,
        "source_quote": value,
    }
    session.target_index += 1
    if is_draft_complete(session):
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
    if flow_mode in CAPTURE_FLOW_MODES:
        return str(flow_mode)
    return FLOW_UNIFIED


def _normalize_observed_keys(observed: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return observed


def _normalize_derived(value: Any) -> dict[str, list[dict[str, Any]]]:
    derived = empty_derived()
    if not isinstance(value, dict):
        return derived
    for key in derived:
        items = value.get(key)
        if isinstance(items, list):
            derived[key] = items
    return derived

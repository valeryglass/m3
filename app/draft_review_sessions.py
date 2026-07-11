from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.loop_extractor import LoopSession
from app.runtime_storage import atomic_write_json, locked_unlink
from app.schemas.capture import CaptureMode
from app.schemas.episode import Observed
from app.session_store import LoopSessionStore


class DraftReviewSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["m3.draft_review_session.v1"] = (
        "m3.draft_review_session.v1"
    )
    chat_id: int
    review_id: str = Field(min_length=1)
    mode: CaptureMode
    episode_date: str
    observed: dict[str, dict[str, str]]
    created_at: datetime
    review_started_at: datetime
    capture_id: str | None = None
    capture_artifact_path: str | None = None
    extraction_id: str | None = None
    extraction_path: str | None = None
    intake_transcript_path: str | None = None
    media_kind: str | None = None

    @model_validator(mode="after")
    def validate_observed(self):
        Observed.model_validate(self.observed)
        return self

    @classmethod
    def from_legacy_loop_session(
        cls,
        session: LoopSession,
        *,
        now: datetime,
    ) -> "DraftReviewSession":
        if not session.awaiting_save_confirmation:
            raise ValueError("legacy loop session is not awaiting review")
        if not session.episode_date:
            raise ValueError("legacy review has no episode date")
        mode = (
            session.flow_mode
            if session.flow_mode
            in {"classic_10q", "three_block", "one_take_text", "one_take_audio"}
            else "classic_10q"
        )
        return cls(
            chat_id=session.chat_id,
            review_id=session.session_id or f"legacy-review-{session.chat_id}",
            mode=mode,
            episode_date=session.episode_date,
            observed=session.observed,
            created_at=now,
            review_started_at=now,
            intake_transcript_path=session.intake_transcript_path,
            media_kind=session.media_kind,
        )


class DraftReviewSessionStore:
    def __init__(
        self,
        session_root: Path,
        *,
        loop_session_store: LoopSessionStore | None = None,
    ) -> None:
        self.review_dir = session_root / "review"
        self.review_dir.mkdir(parents=True, exist_ok=True)
        self.loop_session_store = loop_session_store

    def load_session(
        self,
        chat_id: int,
        *,
        now: datetime | None = None,
    ) -> DraftReviewSession | None:
        path = self._session_path(chat_id)
        if path.exists():
            return DraftReviewSession.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        if self.loop_session_store is None or now is None:
            return None
        legacy = self.loop_session_store.load_session(chat_id)
        if legacy is None or not legacy.awaiting_save_confirmation:
            return None
        review = DraftReviewSession.from_legacy_loop_session(legacy, now=now)
        self.save_session(review)
        self.loop_session_store.delete_session(chat_id)
        return review

    def save_session(self, session: DraftReviewSession) -> None:
        atomic_write_json(
            self._session_path(session.chat_id),
            session.model_dump(mode="json"),
            sort_keys=True,
        )

    def delete_session(self, chat_id: int) -> None:
        locked_unlink(self._session_path(chat_id))

    def _session_path(self, chat_id: int) -> Path:
        return self.review_dir / f"chat-{chat_id}.json"


def review_session_from_extraction(
    *,
    chat_id: int,
    mode: CaptureMode,
    observed: dict[str, dict[str, Any]],
    episode_date: str,
    now: datetime,
    capture_id: str,
    capture_artifact_path: Path,
    extraction_id: str,
    extraction_path: Path,
    intake_transcript_path: str | None = None,
    media_kind: str | None = None,
) -> DraftReviewSession:
    return DraftReviewSession(
        chat_id=chat_id,
        review_id=f"review-{capture_id}",
        mode=mode,
        episode_date=episode_date,
        observed=observed,
        created_at=now,
        review_started_at=now,
        capture_id=capture_id,
        capture_artifact_path=str(capture_artifact_path),
        extraction_id=extraction_id,
        extraction_path=str(extraction_path),
        intake_transcript_path=intake_transcript_path,
        media_kind=media_kind,
    )

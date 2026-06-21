from datetime import datetime, timezone

from app.draft_review_sessions import (
    DraftReviewSession,
    DraftReviewSessionStore,
    review_session_from_extraction,
)
from app.loop_extractor import LoopSession
from app.session_store import LoopSessionStore


NOW = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
OBSERVED = {
    "situation": {"value": "s", "source_quote": "s"},
    "automatic_thought": {"value": "at", "source_quote": "at"},
    "emotion": {"value": "e", "source_quote": "e"},
    "behavior": {"value": "b", "source_quote": "b"},
    "physical": {"value": "p", "source_quote": "p"},
    "short_term_consequence": {"value": "st", "source_quote": "st"},
    "long_term_consequence": {"value": "lt", "source_quote": "lt"},
}


def test_review_session_round_trip(tmp_path):
    store = DraftReviewSessionStore(tmp_path)
    review = review_session_from_extraction(
        chat_id=42,
        mode="one_take_text",
        observed=OBSERVED,
        episode_date="2026-06-21",
        now=NOW,
        capture_id="capture-one-take-text-42-20260621t120000z-nomessage",
        capture_artifact_path=tmp_path / "capture.json",
        extraction_id=(
            "extraction-capture-one-take-text-42-20260621t120000z-nomessage"
        ),
        extraction_path=tmp_path / "extraction.json",
    )
    store.save_session(review)
    assert store.load_session(42) == review


def test_review_store_migrates_legacy_completed_loop_session(tmp_path):
    loops = LoopSessionStore(tmp_path)
    loops.save_session(
        LoopSession(
            chat_id=42,
            flow_mode="one_take_text",
            session_id="legacy-session",
            episode_date="2026-06-21",
            observed=OBSERVED,
            awaiting_save_confirmation=True,
        )
    )
    reviews = DraftReviewSessionStore(tmp_path, loop_session_store=loops)
    review = reviews.load_session(42, now=NOW)
    assert review is not None
    assert review.mode == "one_take_text"
    assert loops.load_session(42) is None
    assert reviews.load_session(42) == review


def test_review_session_requires_complete_observed_contract():
    try:
        DraftReviewSession(
            chat_id=42,
            review_id="review",
            mode="one_take_text",
            episode_date="2026-06-21",
            observed={"situation": OBSERVED["situation"]},
            created_at=NOW,
            review_started_at=NOW,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete review must be rejected")

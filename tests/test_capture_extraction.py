from datetime import datetime, timezone

import pytest

from app.capture_artifacts import build_capture_artifact
from app.capture_extraction import (
    CaptureExtractionError,
    UnavailableCaptureExtractionProvider,
    link_capture_extraction_to_episode,
    load_capture_extraction,
    project_classic_10q,
    run_capture_extraction,
    source_piece,
    validate_grounded_extraction,
)
from app.schemas.capture import CaptureExtractionResult


NOW = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
REQUIRED = (
    "situation",
    "automatic_thought",
    "emotion",
    "behavior",
    "physical",
    "short_term_consequence",
    "long_term_consequence",
)


def _one_take_artifact():
    return build_capture_artifact(
        chat_id=42,
        mode="one_take_text",
        media_kind="text",
        pieces=(("one_take_text", "I froze, felt fear, then left and felt relief."),),
        created_at=NOW,
        message_id=7,
    )


def _one_take_result(**overrides):
    quote = "felt fear"
    values = {
        field: source_piece("one_take_text", field.replace("_", " "), quote)
        for field in REQUIRED
    }
    values.update({"trigger": None, "actor": None, "quote": None})
    values.update(overrides)
    return CaptureExtractionResult(**values)


def test_grounding_accepts_normalized_values_with_exact_quotes():
    result = validate_grounded_extraction(_one_take_artifact(), _one_take_result())
    assert result.automatic_thought.value == "automatic thought"


def test_grounding_rejects_invented_quote():
    with pytest.raises(CaptureExtractionError) as exc:
        validate_grounded_extraction(
            _one_take_artifact(),
            _one_take_result(emotion=source_piece("one_take_text", "fear", "invented")),
        )
    assert exc.value.code == "invalid_source_quote"


def test_three_block_grounding_rejects_wrong_evidence_group():
    artifact = build_capture_artifact(
        chat_id=42,
        mode="three_block",
        media_kind="text",
        pieces=(
            ("outside_context", "meeting happened"),
            ("inner_context", "fear and tension"),
            ("response_outcome", "left, relief now, regret later"),
        ),
        created_at=NOW,
    )
    result = CaptureExtractionResult(
        situation=source_piece("outside_context", "meeting", "meeting"),
        trigger=None,
        actor=None,
        quote=None,
        automatic_thought=source_piece("inner_context", "danger", "fear"),
        emotion=source_piece("inner_context", "fear", "fear"),
        physical=source_piece("inner_context", "tension", "tension"),
        behavior=source_piece("inner_context", "left", "fear"),
        short_term_consequence=source_piece("response_outcome", "relief", "relief"),
        long_term_consequence=source_piece("response_outcome", "regret", "regret"),
    )
    with pytest.raises(CaptureExtractionError) as exc:
        validate_grounded_extraction(artifact, result)
    assert exc.value.code == "invalid_piece_role"


def test_unavailable_provider_persists_typed_failure_without_draft(tmp_path):
    outcome = run_capture_extraction(
        _one_take_artifact(),
        UnavailableCaptureExtractionProvider(),
        tmp_path,
        created_at=NOW,
    )
    assert outcome.draft is None
    assert outcome.extraction.failure_code == "provider_unavailable"
    assert load_capture_extraction(outcome.path) == outcome.extraction


def test_classic_projection_persists_success_and_episode_link(tmp_path):
    artifact = build_capture_artifact(
        chat_id=42,
        mode="classic_10q",
        media_kind="text",
        pieces=tuple((field, field) for field in REQUIRED),
        created_at=NOW,
    )
    outcome = project_classic_10q(artifact, tmp_path, created_at=NOW)
    assert outcome.draft is not None
    assert outcome.extraction.provider == "deterministic.direct"
    linked = link_capture_extraction_to_episode(
        outcome.path, "episode-20260621-1"
    )
    assert linked.episode_id == "episode-20260621-1"

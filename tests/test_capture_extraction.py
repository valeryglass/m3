import json
from datetime import datetime, timezone

import pytest

from app.capture_artifacts import build_capture_artifact
from app.capture_extraction import (
    CaptureExtractionError,
    UnavailableCaptureExtractionProvider,
    partial_extraction_from_mapping,
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
    journal_path = tmp_path / "journal.jsonl"
    outcome = run_capture_extraction(
        _one_take_artifact(),
        UnavailableCaptureExtractionProvider(),
        tmp_path,
        created_at=NOW,
        journal_log=journal_path,
    )
    assert outcome.draft is None
    assert outcome.extraction.failure_code == "provider_unavailable"
    assert load_capture_extraction(outcome.path) == outcome.extraction
    events = _read_jsonl(journal_path)
    assert [event["event_type"] for event in events] == [
        "capture_extraction.started",
        "capture_extraction.failed",
    ]
    assert events[-1]["failure_code"] == "provider_unavailable"
    assert "felt fear" not in journal_path.read_text(encoding="utf-8")


def test_unavailable_one_take_can_seed_partial_draft(tmp_path):
    outcome = run_capture_extraction(
        _one_take_artifact(),
        UnavailableCaptureExtractionProvider(),
        tmp_path,
        created_at=NOW,
        allow_partial_draft=True,
    )

    assert outcome.extraction.status == "failed"
    assert outcome.extraction.failure_code == "provider_unavailable"
    assert outcome.partial is True
    assert outcome.draft is not None
    assert outcome.draft.observed == {
        "situation": {
            "value": "I froze, felt fear, then left and felt relief.",
            "source_quote": "I froze, felt fear, then left and felt relief.",
        }
    }
    assert outcome.missing_required_fields == (
        "automatic_thought",
        "emotion",
        "behavior",
        "physical",
        "short_term_consequence",
        "long_term_consequence",
    )


def test_three_block_partial_fallback_maps_blocks_to_observed_fields(tmp_path):
    artifact = build_capture_artifact(
        chat_id=42,
        mode="three_block",
        media_kind="text",
        pieces=(
            ("outside_context", "факт"),
            ("inner_context", "мысль"),
            ("response_outcome", "замолчал"),
        ),
        created_at=NOW,
    )

    outcome = run_capture_extraction(
        artifact,
        UnavailableCaptureExtractionProvider(),
        tmp_path,
        created_at=NOW,
        allow_partial_draft=True,
    )

    assert outcome.partial is True
    assert outcome.draft is not None
    assert outcome.draft.observed == {
        "situation": {"value": "факт", "source_quote": "факт"},
        "automatic_thought": {"value": "мысль", "source_quote": "мысль"},
        "behavior": {"value": "замолчал", "source_quote": "замолчал"},
    }


def test_partial_extraction_accepts_grounded_fields_and_rejects_bad_field():
    payload = _one_take_result().model_dump(mode="python")
    payload["physical"] = {"value": "tense"}

    partial = partial_extraction_from_mapping(_one_take_artifact(), payload)

    assert "emotion" in partial.observed
    assert "physical" not in partial.observed
    assert partial.rejected_fields == {"physical": "invalid_schema"}
    assert partial.missing_required_fields == ("physical",)


def test_grounding_failure_writes_capture_debug_and_journal_summary(tmp_path):
    journal_path = tmp_path / "journal.jsonl"
    debug_dir = tmp_path / "capture-debug"
    provider = _FakeProvider(
        _one_take_result(
            situation=source_piece("one_take_text", "situation", "invented")
        ),
        debug_dir,
    )

    outcome = run_capture_extraction(
        _one_take_artifact(),
        provider,
        tmp_path,
        created_at=NOW,
        journal_log=journal_path,
    )

    assert outcome.draft is None
    assert outcome.extraction.failure_code == "invalid_source_quote"
    debug_paths = list(debug_dir.rglob("debug-*.json"))
    assert len(debug_paths) == 1
    debug = json.loads(debug_paths[0].read_text(encoding="utf-8"))
    assert debug["parser_stage"] == "grounding"
    assert debug["grounding_failure_code"] == "invalid_source_quote"
    journal = _read_jsonl(journal_path)[-1]
    assert journal["details"]["parser_stage"] == "grounding"
    assert journal["details"]["grounding_failure_code"] == "invalid_source_quote"
    assert "invented" not in journal_path.read_text(encoding="utf-8")


def test_classic_projection_persists_success_and_episode_link(tmp_path):
    journal_path = tmp_path / "journal.jsonl"
    artifact = build_capture_artifact(
        chat_id=42,
        mode="classic_10q",
        media_kind="text",
        pieces=tuple((field, field) for field in REQUIRED),
        created_at=NOW,
    )
    outcome = project_classic_10q(
        artifact,
        tmp_path,
        created_at=NOW,
        journal_log=journal_path,
    )
    assert outcome.draft is not None
    assert outcome.extraction.provider == "deterministic.direct"
    events = _read_jsonl(journal_path)
    assert [event["event_type"] for event in events] == [
        "capture_extraction.started",
        "capture_extraction.succeeded",
    ]
    linked = link_capture_extraction_to_episode(
        outcome.path, "episode-20260621-1"
    )
    assert linked.episode_id == "episode-20260621-1"


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class _FakeProvider:
    provider_name = "fake.provider"
    model = "fake-model"
    prompt_version = "fake-prompt"

    def __init__(self, result, capture_debug_dir):
        self.result = result
        self.capture_debug_dir = capture_debug_dir

    def extract(self, artifact):
        from app.capture_debug import record_provider_debug

        record_provider_debug(
            self.capture_debug_dir,
            artifact,
            provider=self.provider_name,
            model=self.model,
            prompt_version=self.prompt_version,
            response_text=json.dumps(self.result.model_dump(mode="json")),
        )
        return self.result

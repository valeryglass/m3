from app.episode_drafts import (
    COMPLETE_TARGET,
    DRAFT_STATUS_COMPLETE,
    DRAFT_STATUS_PARTIAL,
    EpisodeDraft,
    THREE_BLOCK_DEFAULT_FIELDS,
    completed_draft_field_count,
    draft_from_input_artifact,
    draft_from_text,
    draft_from_three_blocks,
    draft_status,
    is_draft_complete,
    next_draft_target,
    next_missing_draft_field,
    observed_text_field,
)
from app.input_funnels import InputArtifact, MEDIA_KIND_VOICE, text_input_artifact


FIELDS = ("situation", "trigger", "emotion")


def test_observed_text_field_preserves_source_quote():
    assert observed_text_field("hello") == {"value": "hello", "source_quote": "hello"}


def test_draft_from_text_creates_situation_draft_by_default():
    draft = draft_from_text("  something happened  ")

    assert isinstance(draft, EpisodeDraft)
    assert draft.observed == {
        "situation": {
            "value": "something happened",
            "source_quote": "something happened",
        }
    }


def test_draft_from_text_can_target_a_specific_field():
    draft = draft_from_text("felt shame", field_name="emotion")

    assert draft.observed == {
        "emotion": {"value": "felt shame", "source_quote": "felt shame"}
    }


def test_draft_from_text_returns_empty_draft_for_blank_text():
    assert draft_from_text("   ").observed == {}


def test_draft_from_input_artifact_uses_artifact_text():
    draft = draft_from_input_artifact(text_input_artifact("one take"))

    assert draft.observed == {
        "situation": {"value": "one take", "source_quote": "one take"}
    }


def test_draft_from_input_artifact_prefers_transcript_text():
    artifact = InputArtifact(
        source="telegram",
        media_kind=MEDIA_KIND_VOICE,
        raw_text="caption",
        transcript="spoken note",
    )

    assert draft_from_input_artifact(artifact).observed == {
        "situation": {"value": "spoken note", "source_quote": "spoken note"}
    }



def test_draft_from_three_blocks_uses_default_field_mapping():
    draft = draft_from_three_blocks(
        "коллега резко ответил",
        "я подумал что меня отвергли",
        "я замолчал",
    )

    assert THREE_BLOCK_DEFAULT_FIELDS == (
        "situation",
        "automatic_thought",
        "behavior",
    )
    assert draft.observed == {
        "situation": {
            "value": "коллега резко ответил",
            "source_quote": "коллега резко ответил",
        },
        "automatic_thought": {
            "value": "я подумал что меня отвергли",
            "source_quote": "я подумал что меня отвергли",
        },
        "behavior": {"value": "я замолчал", "source_quote": "я замолчал"},
    }


def test_draft_from_three_blocks_skips_blank_blocks():
    draft = draft_from_three_blocks("happened", "   ", "response")

    assert draft.observed == {
        "situation": {"value": "happened", "source_quote": "happened"},
        "behavior": {"value": "response", "source_quote": "response"},
    }


def test_draft_from_three_blocks_can_use_custom_field_mapping():
    draft = draft_from_three_blocks(
        "s",
        "e",
        "st",
        field_names=("situation", "emotion", "short_term_consequence"),
    )

    assert draft.observed == {
        "situation": {"value": "s", "source_quote": "s"},
        "emotion": {"value": "e", "source_quote": "e"},
        "short_term_consequence": {"value": "st", "source_quote": "st"},
    }


def test_draft_from_three_blocks_requires_three_field_mapping():
    try:
        draft_from_three_blocks("s", "i", "r", field_names=("situation",))
    except ValueError as exc:
        assert "exactly three fields" in str(exc)
    else:
        raise AssertionError("expected ValueError")

def test_completed_draft_field_count_uses_declared_fields_only():
    observed = {
        "situation": {"value": "s", "source_quote": "s"},
        "unknown": {"value": "x", "source_quote": "x"},
    }

    assert completed_draft_field_count(observed, FIELDS) == 1


def test_next_missing_draft_field_returns_first_declared_gap():
    observed = {
        "situation": {"value": "s", "source_quote": "s"},
        "emotion": {"value": "e", "source_quote": "e"},
    }

    assert next_missing_draft_field(observed, FIELDS) == "trigger"


def test_draft_status_and_complete_check():
    partial = {"situation": {"value": "s", "source_quote": "s"}}
    complete = {
        field_name: {"value": field_name, "source_quote": field_name}
        for field_name in FIELDS
    }

    assert draft_status(partial, FIELDS) == DRAFT_STATUS_PARTIAL
    assert is_draft_complete(partial, FIELDS) is False
    assert draft_status(complete, FIELDS) == DRAFT_STATUS_COMPLETE
    assert is_draft_complete(complete, FIELDS) is True


def test_next_draft_target_preserves_current_order_index_until_complete():
    observed = {
        "situation": {"value": "s", "source_quote": "s"},
        "emotion": {"value": "e", "source_quote": "e"},
    }

    assert next_missing_draft_field(observed, FIELDS) == "trigger"
    assert next_draft_target(observed, FIELDS, target_index=2) == "emotion"


def test_next_draft_target_returns_complete_for_complete_or_exhausted_draft():
    complete = {
        field_name: {"value": field_name, "source_quote": field_name}
        for field_name in FIELDS
    }
    partial = {"situation": {"value": "s", "source_quote": "s"}}

    assert next_draft_target(complete, FIELDS, target_index=0) == COMPLETE_TARGET
    assert next_draft_target(partial, FIELDS, target_index=99) == COMPLETE_TARGET

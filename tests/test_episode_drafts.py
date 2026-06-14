from app.episode_drafts import (
    COMPLETE_TARGET,
    DRAFT_STATUS_COMPLETE,
    DRAFT_STATUS_PARTIAL,
    completed_draft_field_count,
    draft_status,
    is_draft_complete,
    next_draft_target,
    next_missing_draft_field,
)


FIELDS = ("situation", "trigger", "emotion")


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

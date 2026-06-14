from app.gap_hydration import (
    GAP_REASON_MISSING,
    DraftGap,
    missing_draft_gaps,
    select_next_gap,
)


FIELDS = ("situation", "trigger", "emotion")


def test_missing_draft_gaps_returns_declared_field_gaps_in_order():
    observed = {"situation": {"value": "s", "source_quote": "s"}}

    assert missing_draft_gaps(observed, FIELDS) == (
        DraftGap("trigger"),
        DraftGap("emotion"),
    )


def test_gap_reason_defaults_to_missing():
    assert DraftGap("trigger").reason == GAP_REASON_MISSING


def test_select_next_gap_prefers_current_order_target_when_it_is_missing():
    observed = {
        "situation": {"value": "s", "source_quote": "s"},
    }

    assert select_next_gap(observed, FIELDS, target_index=2) == DraftGap("emotion")


def test_select_next_gap_falls_back_to_first_missing_field():
    observed = {
        "situation": {"value": "s", "source_quote": "s"},
        "emotion": {"value": "e", "source_quote": "e"},
    }

    assert select_next_gap(observed, FIELDS, target_index=2) == DraftGap("trigger")


def test_select_next_gap_can_ignore_current_order_for_future_non_linear_modes():
    observed = {
        "situation": {"value": "s", "source_quote": "s"},
    }

    assert select_next_gap(
        observed,
        FIELDS,
        target_index=2,
        current_order_only=False,
    ) == DraftGap("trigger")


def test_select_next_gap_returns_none_when_complete():
    observed = {
        field_name: {"value": field_name, "source_quote": field_name}
        for field_name in FIELDS
    }

    assert missing_draft_gaps(observed, FIELDS) == ()
    assert select_next_gap(observed, FIELDS, target_index=0) is None

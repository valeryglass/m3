from app.loop_extractor import (
    DRAFT_STATUS_COMPLETE,
    DRAFT_STATUS_PARTIAL,
    FLOW_UNIFIED,
    LoopSession,
    OBSERVED_FIELDS,
    active_target,
    apply_user_reply,
    completed_draft_field_count,
    completed_observed_count,
    draft_observed_fields,
    draft_status,
    is_draft_complete,
    new_session,
    new_session_from_draft,
    next_draft_target,
    next_missing_draft_field,
    target_fields,
)
from app.derived_normalizer import empty_derived
from app.episode_drafts import EpisodeDraft, draft_from_text


def test_loop_starts_with_situation_and_creation_date():
    session = new_session(chat_id=123, episode_date="2026-05-03")

    assert session.episode_date == "2026-05-03"
    assert active_target(session) == "situation"


def test_new_session_from_partial_draft_starts_at_next_missing_field():
    draft = draft_from_text("one-take situation")

    session = new_session_from_draft(
        chat_id=123,
        draft=draft,
        session_id="session-123",
        episode_date="2026-05-03",
    )

    assert session.session_id == "session-123"
    assert session.episode_date == "2026-05-03"
    assert session.observed == {
        "situation": {
            "value": "one-take situation",
            "source_quote": "one-take situation",
        }
    }
    assert session.target_index == 1
    assert active_target(session) == "trigger"


def test_new_session_from_complete_draft_starts_complete():
    draft = EpisodeDraft(
        observed={
            field_name: {"value": field_name, "source_quote": field_name}
            for field_name in target_fields(LoopSession(chat_id=123))
        }
    )

    session = new_session_from_draft(
        chat_id=123,
        draft=draft,
        episode_date="2026-05-03",
    )

    assert session.target_index == len(target_fields(session))
    assert active_target(session) == "complete"


def test_story_first_target_progression():
    session = new_session(chat_id=123, episode_date="2026-04-30")

    apply_user_reply(session, "Had a conversation.")
    assert active_target(session) == "trigger"

    apply_user_reply(session, "Sharp comment.")
    assert active_target(session) == "actor"
    assert completed_observed_count(session) == 2


def test_draft_vocabulary_aliases_current_observed_session_state():
    session = LoopSession(
        chat_id=123,
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "t", "source_quote": "t"},
        },
    )

    assert draft_observed_fields(session) is session.observed
    assert completed_draft_field_count(session) == 2
    assert completed_observed_count(session) == 2
    assert draft_status(session) == DRAFT_STATUS_PARTIAL
    assert is_draft_complete(session) is False


def test_complete_draft_status_reuses_existing_observed_completion_rule():
    session = LoopSession(
        chat_id=123,
        observed={
            field_name: {"value": field_name, "source_quote": field_name}
            for field_name in target_fields(LoopSession(chat_id=123))
        },
    )

    assert completed_draft_field_count(session) == len(target_fields(session))
    assert draft_status(session) == DRAFT_STATUS_COMPLETE
    assert is_draft_complete(session) is True


def test_next_draft_target_preserves_current_order_index_rule():
    session = LoopSession(
        chat_id=123,
        target_index=5,
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "actor": {"value": "a", "source_quote": "a"},
        },
    )

    assert next_missing_draft_field(session) == "trigger"
    assert next_draft_target(session) == "emotion"
    assert active_target(session) == "emotion"


def test_next_draft_target_falls_back_to_gap_selector_when_index_is_filled():
    session = LoopSession(
        chat_id=123,
        target_index=1,
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "tr", "source_quote": "tr"},
            "actor": {"value": "ac", "source_quote": "ac"},
        },
    )

    assert next_missing_draft_field(session) == "quote"
    assert next_draft_target(session) == "quote"
    assert active_target(session) == "quote"


def test_next_draft_target_returns_complete_when_no_gaps_remain():
    session = LoopSession(
        chat_id=123,
        observed={
            field_name: {"value": field_name, "source_quote": field_name}
            for field_name in target_fields(LoopSession(chat_id=123))
        },
    )

    assert next_missing_draft_field(session) is None
    assert next_draft_target(session) == "complete"
    assert active_target(session) == "complete"


def test_session_from_dict_normalizes_legacy_target_index():
    session = LoopSession.from_dict(
        {
            "chat_id": 123,
            "session_id": "session-123",
            "target_index": 5,
            "episode_date": None,
            "observed": {
                "situation": {"value": "s", "source_quote": "s"},
                "trigger": {"value": "tr", "source_quote": "tr"},
                "actor": {"value": "ac", "source_quote": "ac"},
                "quote": {"value": "sp", "source_quote": "sp"},
            },
        }
    )

    assert session.target_index == 4
    assert active_target(session) == "automatic_thought"
    assert session.awaiting_save_confirmation is False
    assert session.flow_mode == FLOW_UNIFIED


def test_uniflow_uses_single_target_order():
    session = new_session(chat_id=123, episode_date="2026-05-03")

    assert target_fields(session) == (
        "situation",
        "trigger",
        "actor",
        "quote",
        "automatic_thought",
        "emotion",
        "behavior",
        "physical",
        "short_term_consequence",
        "long_term_consequence",
    )
    assert OBSERVED_FIELDS == target_fields(session)


def test_session_from_dict_restores_save_confirmation_state():
    session = LoopSession.from_dict(
        {
            "chat_id": 123,
            "session_id": "session-123",
            "awaiting_save_confirmation": True,
            "observed": {},
        }
    )

    assert session.awaiting_save_confirmation is True
    assert session.to_dict()["awaiting_save_confirmation"] is True


def test_session_round_trip_preserves_optional_transcript_link():
    session = LoopSession(
        chat_id=123,
        flow_mode="one_take_audio",
        capture_funnel="one_take_audio",
        media_kind="voice",
        intake_transcript_path="data/intake-transcripts/chat/message.json",
    )

    loaded = LoopSession.from_dict(session.to_dict())

    assert loaded.intake_transcript_path == session.intake_transcript_path
    assert loaded.flow_mode == "one_take_audio"
    assert loaded.capture_funnel == "one_take_audio"


def test_session_from_dict_drops_legacy_derived_keys():
    session = LoopSession.from_dict(
        {
            "chat_id": 123,
            "session_id": "session-123",
            "observed": {},
            "derived": {
                "atomic_thoughts": [{"id": "atomic-thought-1"}],
                "cognitive_distortions": [],
            },
        }
    )

    assert session.derived == empty_derived()


def test_emotion_reply_writes_plain_observed_field():
    session = LoopSession(
        chat_id=123,
        target_index=5,
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "tr", "source_quote": "tr"},
            "actor": {"value": "ac", "source_quote": "ac"},
            "quote": {"value": "sp", "source_quote": "sp"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
        },
    )

    result = apply_user_reply(session, "страх и растерянность")

    assert result.should_save is False
    assert session.target_index == 6
    assert active_target(session) == "behavior"
    assert session.observed["emotion"] == {
        "value": "страх и растерянность",
        "source_quote": "страх и растерянность",
    }


def test_empty_observed_reply_stays_on_current_target():
    session = LoopSession(chat_id=123, target_index=0, episode_date="2026-05-03")
    result = apply_user_reply(session, " ")

    assert "непустой" in result.reply
    assert active_target(session) == "situation"


def test_loop_completes_after_body_without_derived_targets():
    session = new_session(chat_id=123, episode_date="2026-04-30")

    for answer in (
        "Had a conversation.",
        "Sharp comment.",
        "Me and a colleague.",
        "They said no.",
        "I can say this.",
        "Shame.",
        "Answered directly.",
        "Chest pressure.",
        "Felt relief.",
    ):
        result = apply_user_reply(session, answer)
        assert not result.should_save

    result = apply_user_reply(session, "It was okay later.")

    assert result.should_save
    assert active_target(session) == "complete"
    assert completed_observed_count(session) == 10
    assert session.derived == empty_derived()

from app.loop_extractor import (
    FLOW_UNIFIED,
    LoopSession,
    OBSERVED_FIELDS,
    active_target,
    apply_user_reply,
    completed_observed_count,
    new_session,
    target_fields,
)
from app.derived_normalizer import empty_derived


def test_loop_starts_with_situation_and_creation_date():
    session = new_session(chat_id=123, episode_date="2026-05-03")

    assert session.episode_date == "2026-05-03"
    assert active_target(session) == "situation"


def test_story_first_target_progression():
    session = new_session(chat_id=123, episode_date="2026-04-30")

    apply_user_reply(session, "Had a conversation.")
    assert active_target(session) == "trigger"

    apply_user_reply(session, "Sharp comment.")
    assert active_target(session) == "actor"
    assert completed_observed_count(session) == 2


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

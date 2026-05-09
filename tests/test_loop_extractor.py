from app.loop_extractor import (
    FLOW_FULL,
    FULL_OBSERVED_FIELDS,
    LoopSession,
    OBSERVED_FIELDS,
    active_target,
    apply_emotion_draft,
    apply_user_reply,
    completed_observed_count,
    cycle_emotion_draft,
    new_session,
    target_fields,
)


def test_loop_starts_with_situation_and_creation_date():
    session = new_session(chat_id=123, episode_date="2026-05-03")

    assert session.episode_date == "2026-05-03"
    assert active_target(session) == "situation"


def test_story_first_target_progression():
    session = new_session(chat_id=123, episode_date="2026-04-30")

    apply_user_reply(session, "Had a conversation.")
    assert active_target(session) == "behavior"

    apply_user_reply(session, "Answered directly.")
    assert active_target(session) == "short_term_consequence"
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
                "behavior": {"value": "b", "source_quote": "b"},
                "short_term_consequence": {"value": "st", "source_quote": "st"},
                "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            },
        }
    )

    assert session.target_index == 4
    assert active_target(session) == "automatic_thought"
    assert session.awaiting_save_confirmation is False
    assert session.emotion_draft == {}
    assert session.flow_mode == "basic"


def test_full_flow_uses_expanded_target_order():
    session = new_session(
        chat_id=123, episode_date="2026-05-03", flow_mode=FLOW_FULL
    )

    assert target_fields(session) == FULL_OBSERVED_FIELDS
    assert target_fields(session) == (
        "situation",
        "trigger",
        "actors",
        "speech",
        "behavior",
        "short_term_consequence",
        "long_term_consequence",
        "automatic_thought",
        "emotion",
        "body",
    )
    assert OBSERVED_FIELDS == (
        "situation",
        "behavior",
        "short_term_consequence",
        "long_term_consequence",
        "automatic_thought",
        "emotion",
        "body",
    )


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


def test_session_from_dict_restores_emotion_draft():
    session = LoopSession.from_dict(
        {
            "chat_id": 123,
            "session_id": "session-123",
            "emotion_draft": {"fear": 2, "bad": 2, "joy": 9},
            "observed": {},
        }
    )

    assert session.emotion_draft == {"fear": 2}
    assert session.to_dict()["emotion_draft"] == {"fear": 2}
    assert session.emotion_free_text is None


def test_session_from_dict_restores_emotion_free_text():
    session = LoopSession.from_dict(
        {
            "chat_id": 123,
            "session_id": "session-123",
            "emotion_free_text": "растерянность",
            "observed": {},
        }
    )

    assert session.emotion_free_text == "растерянность"
    assert session.to_dict()["emotion_free_text"] == "растерянность"


def test_emotion_draft_cycles_to_high_then_off():
    session = LoopSession(chat_id=123)

    cycle_emotion_draft(session, "fear")
    assert session.emotion_draft == {"fear": 1}

    cycle_emotion_draft(session, "fear")
    assert session.emotion_draft == {"fear": 2}

    cycle_emotion_draft(session, "fear")
    assert session.emotion_draft == {"fear": 3}

    cycle_emotion_draft(session, "fear")
    assert session.emotion_draft == {}


def test_apply_emotion_draft_writes_structured_items_and_advances():
    session = LoopSession(
        chat_id=123,
        target_index=5,
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "behavior": {"value": "b", "source_quote": "b"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
        },
        emotion_draft={"shame": 1, "fear": 3},
    )

    value = apply_emotion_draft(session)

    assert value == "стыд: 0.33, страх: 1.0"
    assert session.target_index == 6
    assert active_target(session) == "body"
    assert session.emotion_draft == {}
    assert session.observed["emotion"] == {
        "value": "стыд: 0.33, страх: 1.0",
        "source_quote": "стыд: 0.33, страх: 1.0",
        "items": [
            {"label": "стыд", "intensity": 0.33, "source_quote": "стыд: 0.33"},
            {"label": "страх", "intensity": 1.0, "source_quote": "страх: 1.0"},
        ],
    }


def test_apply_emotion_draft_writes_free_text_layer():
    session = LoopSession(
        chat_id=123,
        target_index=5,
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "behavior": {"value": "b", "source_quote": "b"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
        },
        emotion_draft={"fear": 3},
        emotion_free_text="растерянность",
    )

    value = apply_emotion_draft(session)

    assert value == "страх: 1.0; другое: растерянность"
    assert session.emotion_free_text is None
    assert session.observed["emotion"] == {
        "value": "страх: 1.0; другое: растерянность",
        "source_quote": "страх: 1.0; другое: растерянность",
        "items": [
            {"label": "страх", "intensity": 1.0, "source_quote": "страх: 1.0"},
        ],
        "free_text": "растерянность",
    }


def test_apply_emotion_draft_rejects_free_text_without_bucket():
    session = LoopSession(
        chat_id=123,
        target_index=5,
        emotion_free_text="растерянность",
    )

    try:
        apply_emotion_draft(session)
    except ValueError as exc:
        assert "empty emotion draft" in str(exc)
    else:
        raise AssertionError("Expected empty emotion draft to fail")


def test_empty_observed_reply_stays_on_current_target():
    session = LoopSession(chat_id=123, target_index=0, episode_date="2026-05-03")
    result = apply_user_reply(session, " ")

    assert "непустой" in result.reply
    assert active_target(session) == "situation"


def test_loop_completes_after_body_without_derived_targets():
    session = new_session(chat_id=123, episode_date="2026-04-30")

    for answer in (
        "Had a conversation.",
        "Answered directly.",
        "Felt relief.",
        "It was okay later.",
        "I can say this.",
        "Shame.",
    ):
        result = apply_user_reply(session, answer)
        assert not result.should_save

    result = apply_user_reply(session, "Chest pressure.")

    assert result.should_save
    assert active_target(session) == "complete"
    assert session.derived == {
        "atomic_thoughts": [],
        "cognitive_distortions": [],
    }


def test_full_loop_completes_after_expanded_body_target():
    session = new_session(
        chat_id=123, episode_date="2026-04-30", flow_mode=FLOW_FULL
    )

    for answer in (
        "Had a conversation.",
        "Sharp comment.",
        "Me and a colleague.",
        "They said no.",
        "Answered directly.",
        "Felt relief.",
        "It was okay later.",
        "I can say this.",
        "Shame.",
    ):
        result = apply_user_reply(session, answer)
        assert not result.should_save

    result = apply_user_reply(session, "Chest pressure.")

    assert result.should_save
    assert active_target(session) == "complete"
    assert completed_observed_count(session) == 10

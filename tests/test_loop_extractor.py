from app.loop_extractor import (
    LoopSession,
    active_target,
    apply_user_reply,
    completed_observed_count,
    new_session,
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

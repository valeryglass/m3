import json

from app.loop_extractor import LoopSession
from app.loop_extractor import FLOW_FULL
from app.storage import JsonStorage


def test_next_episode_id_uses_next_number(tmp_path):
    episode_dir = tmp_path / "episodes"
    storage = JsonStorage(episode_dir=episode_dir, state_dir=tmp_path / "state")
    (episode_dir / "episode-20260430-1.json").write_text("{}\n")
    (episode_dir / "episode-20260430-2.json").write_text("{}\n")

    assert storage.next_episode_id("2026-04-30") == "episode-20260430-3"


def test_session_round_trip(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    session = LoopSession(chat_id=123, episode_date="2026-04-30")

    storage.save_session(session)
    loaded = storage.load_session(123)

    assert loaded is not None
    assert loaded.chat_id == 123
    assert loaded.episode_date == "2026-04-30"


def test_episode_count_for_chat_counts_only_matching_source(tmp_path):
    episode_dir = tmp_path / "episodes"
    storage = JsonStorage(episode_dir=episode_dir, state_dir=tmp_path / "state")
    (episode_dir / "episode-20260430-1.json").write_text(
        '{"source": "telegram-chat:123"}\n',
        encoding="utf-8",
    )
    (episode_dir / "episode-20260430-2.json").write_text(
        '{"source": "telegram-chat:456"}\n',
        encoding="utf-8",
    )
    (episode_dir / "episode-20260430-3.json").write_text(
        '{"source": "telegram-chat:123"}\n',
        encoding="utf-8",
    )
    (episode_dir / "episode-20260430-4.json").write_text(
        '{broken',
        encoding="utf-8",
    )

    assert storage.episode_count_for_chat(123) == 2


def test_save_episode_persists_full_observed_fields(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    session = LoopSession(
        chat_id=123,
        flow_mode=FLOW_FULL,
        episode_date="2026-04-30",
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "tr", "source_quote": "tr"},
            "actors": {"value": "ac", "source_quote": "ac"},
            "speech": {"value": "sp", "source_quote": "sp"},
            "behavior": {"value": "b", "source_quote": "b"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {"value": "e", "source_quote": "e"},
            "body": {"value": "body", "source_quote": "body"},
        },
    )

    path = storage.save_episode(session)

    text = path.read_text(encoding="utf-8")
    assert '"trigger"' in text
    assert '"actors"' in text
    assert '"speech"' in text


def test_save_episode_keeps_plain_emotion_without_items(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    session = LoopSession(
        chat_id=123,
        episode_date="2026-04-30",
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "behavior": {"value": "b", "source_quote": "b"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {"value": "страх", "source_quote": "страх"},
            "body": {"value": "body", "source_quote": "body"},
        },
    )

    path = storage.save_episode(session)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["observed"]["emotion"] == {
        "value": "страх",
        "source_quote": "страх",
    }


def test_save_episode_persists_structured_emotion_items(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    session = LoopSession(
        chat_id=123,
        episode_date="2026-04-30",
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "behavior": {"value": "b", "source_quote": "b"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {
                "value": "страх: 1.0",
                "source_quote": "страх: 1.0",
                "items": [
                    {
                        "label": "страх",
                        "intensity": 1.0,
                        "source_quote": "страх: 1.0",
                    }
                ],
            },
            "body": {"value": "body", "source_quote": "body"},
        },
    )

    path = storage.save_episode(session)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["observed"]["emotion"]["items"] == [
        {"label": "страх", "intensity": 1.0, "source_quote": "страх: 1.0"}
    ]


def test_save_episode_persists_emotion_free_text(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes", state_dir=tmp_path / "state")
    session = LoopSession(
        chat_id=123,
        episode_date="2026-04-30",
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "behavior": {"value": "b", "source_quote": "b"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {
                "value": "страх: 1.0; другое: растерянность",
                "source_quote": "страх: 1.0; другое: растерянность",
                "items": [
                    {
                        "label": "страх",
                        "intensity": 1.0,
                        "source_quote": "страх: 1.0",
                    }
                ],
                "free_text": "растерянность",
            },
            "body": {"value": "body", "source_quote": "body"},
        },
    )

    path = storage.save_episode(session)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["observed"]["emotion"]["free_text"] == "растерянность"

import json

from app.loop_extractor import LoopSession
from app.schemas.episode import Episode
from app.session_store import LoopSessionStore
from app.storage import JsonStorage


def test_next_episode_id_uses_next_number(tmp_path):
    episode_dir = tmp_path / "episodes"
    storage = JsonStorage(episode_dir=episode_dir)
    (episode_dir / "episode-20260430-1.json").write_text("{}\n")
    (episode_dir / "episode-20260430-2.json").write_text("{}\n")

    assert storage.next_episode_id("2026-04-30") == "episode-20260430-3"


def test_session_round_trip(tmp_path):
    session_store = LoopSessionStore(tmp_path / "runtime-sessions")
    session = LoopSession(chat_id=123, episode_date="2026-04-30")

    session_store.save_session(session)
    loaded = session_store.load_session(123)

    assert loaded is not None
    assert loaded.chat_id == 123
    assert loaded.episode_date == "2026-04-30"


def test_json_storage_only_creates_episode_directory(tmp_path):
    JsonStorage(episode_dir=tmp_path / "episodes")

    assert (tmp_path / "episodes").is_dir()
    assert not (tmp_path / "runtime-sessions").exists()


def test_episode_count_for_chat_counts_only_matching_source(tmp_path):
    episode_dir = tmp_path / "episodes"
    storage = JsonStorage(episode_dir=episode_dir)
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
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    session = LoopSession(
        chat_id=123,
        episode_date="2026-04-30",
        observed={
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "tr", "source_quote": "tr"},
            "actor": {"value": "ac", "source_quote": "ac"},
            "quote": {"value": "sp", "source_quote": "sp"},
            "behavior": {"value": "b", "source_quote": "b"},
            "short_term_consequence": {"value": "st", "source_quote": "st"},
            "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            "automatic_thought": {"value": "at", "source_quote": "at"},
            "emotion": {"value": "e", "source_quote": "e"},
            "physical": {"value": "physical", "source_quote": "physical"},
        },
    )

    path = storage.save_episode(session)

    text = path.read_text(encoding="utf-8")
    assert '"trigger"' in text
    assert '"actor"' in text
    assert '"quote"' in text


def test_save_observed_episode_does_not_require_loop_session(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
    observed = {
        "situation": {"value": "s", "source_quote": "s"},
        "behavior": {"value": "b", "source_quote": "b"},
        "short_term_consequence": {"value": "st", "source_quote": "st"},
        "long_term_consequence": {"value": "lt", "source_quote": "lt"},
        "automatic_thought": {"value": "at", "source_quote": "at"},
        "emotion": {"value": "e", "source_quote": "e"},
        "physical": {"value": "p", "source_quote": "p"},
    }
    path = storage.save_observed_episode(
        chat_id=123,
        episode_date="2026-04-30",
        observed=observed,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["source"] == "telegram-chat:123"
    assert {
        key: value
        for key, value in data["observed"].items()
        if value is not None
    } == observed


def test_save_episode_keeps_plain_emotion_without_items(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
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
            "physical": {"value": "physical", "source_quote": "physical"},
        },
    )

    path = storage.save_episode(session)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["observed"]["emotion"] == {
        "value": "страх",
        "source_quote": "страх",
    }


def test_save_episode_omits_runtime_derived_annotations(tmp_path):
    storage = JsonStorage(episode_dir=tmp_path / "episodes")
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
            "physical": {"value": "physical", "source_quote": "physical"},
        },
        derived={
            "nodes": [
                {
                    "id": "node-1",
                    "kind": "cognition",
                    "text": "at",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "at",
                    "confidence": 0.8,
                }
            ],
            "trigger_annotations": [],
            "actor_annotations": [],
            "cognition_annotations": [
                {
                    "id": "cognition-annotation-1",
                    "node_id": "node-1",
                    "text": "at",
                    "kind": "evaluation",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "at",
                    "confidence": 0.8,
                }
            ],
            "emotion_annotations": [
                {
                    "id": "emotion-annotation-1",
                    "label": "страх",
                    "intensity": None,
                    "valence": -0.8,
                    "arousal": 0.9,
                    "source_field": "observed.emotion",
                    "source_quote": "страх",
                    "confidence": 0.9,
                }
            ],
            "behavior_annotations": [],
            "relations": [
                {
                    "id": "relation-1",
                    "type": "belongs_to",
                    "from_ref": "node-1",
                    "to_ref": "episode",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "at",
                    "confidence": 1.0,
                }
            ],
        },
    )

    path = storage.save_episode(session)

    data = json.loads(path.read_text(encoding="utf-8"))
    episode = Episode.model_validate(data)
    assert "derived" not in data
    assert "current_derived" not in data
    assert episode.derived.nodes == []

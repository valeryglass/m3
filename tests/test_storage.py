from app.loop_extractor import LoopSession
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

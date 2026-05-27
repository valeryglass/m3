import json

from app.profile_brief import render_profile_brief, write_profile_briefs
from app.graph_report import build_report, load_episodes
from app.schemas.episode import Episode


def test_profile_brief_renders_maturity_patterns_and_gaps():
    report = build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
            _load_episode(_episode("episode-20260430-3", graph_ready=False)),
        ]
    )

    text = render_profile_brief(report, title="telegram-chat:123", min_count=2)

    assert "# Derived CBT Pattern Brief" in text
    assert "- scope: telegram-chat:123" in text
    assert "- episodes: 3" in text
    assert "- profile_eligible: 2" in text
    assert "## Profile Maturity" in text
    assert "- quantity: 2" in text
    assert "## Top Trigger Patterns" in text
    assert "- social: 2 episodes" in text
    assert "- страх: 2 episodes" in text
    assert "- prediction: 2 episodes" in text
    assert "- avoid: 2 episodes" in text
    assert "- prediction -> avoid: 2 episodes" in text
    assert "## Gaps" in text
    assert "- episode-20260430-3: empty_derived" in text


def test_profile_brief_writes_all_and_source_reports(tmp_path):
    episodes = [
        _load_episode(_episode("episode-20260430-1", source="telegram-chat:123")),
        _load_episode(_episode("episode-20260430-2", source="telegram-chat:456")),
    ]

    paths = write_profile_briefs(
        episodes,
        tmp_path / "profile",
        min_count=1,
        by_source=True,
    )

    names = sorted(path.name for path in paths)
    assert names == ["all.md", "telegram-chat-123.md", "telegram-chat-456.md"]
    assert (tmp_path / "profile" / "all.md").read_text(encoding="utf-8").startswith(
        "# Derived CBT Pattern Brief"
    )
    source_text = (tmp_path / "profile" / "telegram-chat-123.md").read_text(
        encoding="utf-8"
    )
    assert "- scope: telegram-chat:123" in source_text
    assert "- episodes: 1" in source_text


def test_profile_brief_loads_real_episode_files(tmp_path):
    path = tmp_path / "episode-20260430-1.json"
    path.write_text(
        json.dumps(_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )

    episodes = load_episodes(tmp_path)
    paths = write_profile_briefs(episodes, tmp_path / "profile", min_count=1)

    assert len(paths) == 1
    assert "Derived CBT Pattern Brief" in paths[0].read_text(encoding="utf-8")


def _load_episode(data):
    return Episode.model_validate(data)


def _episode(
    episode_id,
    *,
    graph_ready=True,
    source="telegram-chat:123",
):
    derived = {
        "nodes": [],
        "trigger_annotations": [],
        "actor_annotations": [],
        "cognition_annotations": [],
        "emotion_annotations": [],
        "behavior_annotations": [],
        "relations": [],
    }
    if graph_ready:
        derived = {
            "nodes": [
                {
                    "id": "node-1",
                    "node_origin": "observed",
                    "kind": "cognition",
                    "text": "They will judge me.",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "they will judge me",
                    "confidence": 0.9,
                }
            ],
            "trigger_annotations": [
                {
                    "id": "trigger-annotation-1",
                    "type": "social",
                    "source_field": "observed.situation",
                    "source_quote": "group chat",
                    "confidence": 0.8,
                }
            ],
            "actor_annotations": [],
            "cognition_annotations": [
                {
                    "id": "cognition-annotation-1",
                    "node_id": "node-1",
                    "text": "They will judge me.",
                    "kind": "prediction",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "they will judge me",
                    "confidence": 0.85,
                }
            ],
            "emotion_annotations": [
                {
                    "id": "emotion-annotation-1",
                    "label": "страх",
                    "intensity": 0.66,
                    "valence": -0.8,
                    "arousal": 0.8,
                    "source_field": "observed.emotion",
                    "source_quote": "страх",
                    "confidence": 0.9,
                }
            ],
            "behavior_annotations": [
                {
                    "id": "behavior-annotation-1",
                    "type": "avoid",
                    "source_field": "observed.behavior",
                    "source_quote": "closed the chat",
                    "confidence": 0.9,
                }
            ],
            "relations": [
                {
                    "id": "relation-1",
                    "type": "belongs_to",
                    "from_ref": "node-1",
                    "to_ref": "episode",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "they will judge me",
                    "confidence": 1.0,
                },
                {
                    "id": "relation-2",
                    "type": "leads_to",
                    "from_ref": "node-1",
                    "to_ref": "observed.behavior",
                    "source_field": "observed.behavior",
                    "source_quote": "closed the chat",
                    "confidence": 0.75,
                },
            ],
        }
    return {
        "id": episode_id,
        "date": "2026-04-30",
        "source": source,
        "observed": {
            "situation": {"value": "Group chat.", "source_quote": "group chat"},
            "automatic_thought": {
                "value": "They will judge me.",
                "source_quote": "they will judge me",
            },
            "emotion": {"value": "страх", "source_quote": "страх"},
            "physical": {"value": "Tight chest.", "source_quote": "tight chest"},
            "behavior": {"value": "Closed the chat.", "source_quote": "closed the chat"},
            "short_term_consequence": {"value": "Relief.", "source_quote": "relief"},
            "long_term_consequence": {
                "value": "Still unresolved.",
                "source_quote": "still unresolved",
            },
        },
        "derived": derived,
    }

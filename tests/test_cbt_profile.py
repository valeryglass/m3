import json

from app.cbt_profile import render_cbt_profile, write_cbt_profiles
from app.graph_report import build_report, load_episodes
from app.schemas.episode import Episode


def test_domain_report_renders_v02_user_sections_and_hides_rank_dump():
    report = build_report(
        [
            _load_episode(_episode("episode-20260430-1")),
            _load_episode(_episode("episode-20260430-2")),
            _load_episode(_episode("episode-20260508-1", behavior_type="approach")),
            _load_episode(_episode("episode-20260508-2", graph_ready=False)),
        ]
    )

    text = render_cbt_profile(report, title="telegram-chat:123", min_count=2)

    assert text.startswith("# Domain Report")
    assert "- scope: telegram-chat:123" in text
    assert "- timespan_quant: 1week" in text
    assert "## Observations" in text
    assert "## Patterns" in text
    assert "## Exceptions" in text
    assert "## Changes" in text
    assert "## Questions" in text
    assert "## Insights" in text
    assert "## Gaps" in text
    assert "Repeated loops" in text
    assert "social -> страх -> avoid" in text
    assert "Temporal grouping uses fixed 1week buckets." in text
    assert "- episode-20260508-2: empty_derived" in text
    assert "### Trigger Frequency" not in text
    assert "## L0 Descriptive Analytics" not in text


def test_domain_report_writes_all_and_source_reports(tmp_path):
    episodes = [
        _load_episode(_episode("episode-20260430-1", source="telegram-chat:123")),
        _load_episode(_episode("episode-20260430-2", source="telegram-chat:456")),
    ]

    paths = write_cbt_profiles(
        episodes,
        tmp_path / "profile",
        min_count=1,
        by_source=True,
    )

    names = sorted(path.name for path in paths)
    assert names == ["all.md", "telegram-chat-123.md", "telegram-chat-456.md"]
    assert (tmp_path / "profile" / "all.md").read_text(encoding="utf-8").startswith(
        "# Domain Report"
    )
    source_text = (tmp_path / "profile" / "telegram-chat-123.md").read_text(
        encoding="utf-8"
    )
    assert "- scope: telegram-chat:123" in source_text
    assert "- episodes: 1" in source_text


def test_domain_report_loads_real_episode_files(tmp_path):
    path = tmp_path / "episode-20260430-1.json"
    path.write_text(
        json.dumps(_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )

    episodes = load_episodes(tmp_path)
    paths = write_cbt_profiles(episodes, tmp_path / "profile", min_count=1)

    assert len(paths) == 1
    assert "Domain Report" in paths[0].read_text(encoding="utf-8")


def _load_episode(data):
    return Episode.model_validate(data)


def _episode(
    episode_id,
    *,
    graph_ready=True,
    source="telegram-chat:123",
    behavior="Closed the chat.",
    behavior_type="avoid",
    stc="Relief.",
    ltc="Still unresolved.",
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
                    "type": behavior_type,
                    "source_field": "observed.behavior",
                    "source_quote": behavior,
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
                    "source_quote": behavior,
                    "confidence": 0.75,
                },
            ],
        }
    return {
        "id": episode_id,
        "date": f"{episode_id[8:12]}-{episode_id[12:14]}-{episode_id[14:16]}",
        "source": source,
        "observed": {
            "situation": {"value": "Group chat.", "source_quote": "group chat"},
            "automatic_thought": {
                "value": "They will judge me.",
                "source_quote": "they will judge me",
            },
            "emotion": {"value": "страх", "source_quote": "страх"},
            "physical": {"value": "Tight chest.", "source_quote": "tight chest"},
            "behavior": {"value": behavior, "source_quote": behavior},
            "short_term_consequence": {"value": stc, "source_quote": stc},
            "long_term_consequence": {"value": ltc, "source_quote": ltc},
        },
        "derived": derived,
    }

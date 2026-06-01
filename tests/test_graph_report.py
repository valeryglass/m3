import json

from app.graph_report import (
    build_report,
    load_episodes,
    render_markdown,
    write_markdown_reports,
)


def _episode(
    episode_id,
    *,
    graph_ready=True,
    emotion="страх",
    behavior="avoid",
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
                    "label": emotion,
                    "intensity": 0.66,
                    "valence": -0.8,
                    "arousal": 0.8,
                    "source_field": "observed.emotion",
                    "source_quote": emotion,
                    "confidence": 0.9,
                }
            ],
            "behavior_annotations": [
                {
                    "id": "behavior-annotation-1",
                    "type": behavior,
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
            "emotion": {"value": emotion, "source_quote": emotion},
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


def test_graph_report_skips_non_graph_ready_episodes():
    report = build_report(
        [
            load_episode(_episode("episode-20260430-1", graph_ready=True)),
            load_episode(_episode("episode-20260430-2", graph_ready=False)),
        ]
    )

    assert report.total_episodes == 2
    assert [item.episode_id for item in report.graph_ready] == ["episode-20260430-1"]
    assert report.skipped == ("episode-20260430-2",)
    assert report.readiness[0].graph_ready is True
    assert report.readiness[1].gap_reasons == ("empty_derived",)


def test_graph_report_counts_signature_clusters():
    report = build_report(
        [
            load_episode(_episode("episode-20260430-1", emotion="страх", behavior="avoid")),
            load_episode(_episode("episode-20260430-2", emotion="страх", behavior="avoid")),
            load_episode(_episode("episode-20260430-3", emotion="грусть", behavior="freeze")),
        ]
    )

    assert report.emotion_signatures[("страх",)] == 2
    assert report.behavior_signatures[("avoid",)] == 2
    assert report.cognition_behavior_signatures[("prediction", "avoid")] == 2
    assert report.emotion_behavior_signatures[("страх", "avoid")] == 2
    assert report.trigger_emotion_signatures[("social", "страх")] == 2


def test_graph_report_renders_markdown_summary_and_per_episode():
    report = build_report(
        [
            load_episode(_episode("episode-20260430-1", emotion="страх", behavior="avoid")),
            load_episode(_episode("episode-20260430-2", emotion="страх", behavior="avoid")),
        ]
    )

    text = render_markdown(report, min_count=2)

    assert "# Graph Report" in text
    assert "- episodes: 2" in text
    assert "- graph_ready: 2" in text
    assert "- report_ready: 2" in text
    assert "- payload_eligible: 2" in text
    assert "## State Snapshots" in text
    assert "- complete: 2" in text
    assert "## Profile Maturity" not in text
    assert "## Top Emotion Signatures" not in text
    assert "## Top Behavior Signatures" not in text
    assert "## Top Cognition Signatures" not in text
    assert "## Trigger + Emotion Signatures" not in text
    assert "## Cognition + Behavior Signatures" not in text
    assert "## Emotion + Behavior Signatures" not in text
    assert "## Relation Type Patterns" in text
    assert "- belongs_to + leads_to: 2 episodes" in text
    assert (
        "- episode-20260430-1: trigger=social; cognition=prediction; "
        "emotion=страх; behavior=avoid"
    ) in text


def test_graph_report_loads_episode_files_from_directory(tmp_path):
    path = tmp_path / "episode-20260430-1.json"
    path.write_text(
        json.dumps(_episode("episode-20260430-1"), ensure_ascii=False),
        encoding="utf-8",
    )

    episodes = load_episodes(tmp_path)

    assert len(episodes) == 1
    assert episodes[0].id == "episode-20260430-1"


def test_graph_report_writes_all_and_source_reports(tmp_path):
    episodes = [
        load_episode(_episode("episode-20260430-1", source="telegram-chat:123")),
        load_episode(_episode("episode-20260430-2", source="telegram-chat:456")),
    ]

    paths = write_markdown_reports(
        episodes,
        tmp_path / "reports",
        min_count=1,
        by_source=True,
    )

    names = sorted(path.name for path in paths)
    assert names == ["all.md", "telegram-chat-123.md", "telegram-chat-456.md"]
    assert (tmp_path / "reports" / "all.md").read_text(encoding="utf-8").startswith(
        "# Graph Report"
    )
    source_text = (tmp_path / "reports" / "telegram-chat-123.md").read_text(
        encoding="utf-8"
    )
    assert "- episodes: 1" in source_text


def load_episode(data):
    from app.schemas.episode import Episode

    return Episode.model_validate(data)

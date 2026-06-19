import json

from app.analytics_loader import AnnotationCoverage
from app.graph_report import build_report
from app.insight_payload import build_insight_payload
from app.schemas.episode import Episode


def test_insight_payload_collects_target_agnostic_entities():
    report = build_report(
        [
            _load(_episode("episode-20260430-1", behavior_type="avoid")),
            _load(_episode("episode-20260430-2", behavior_type="avoid")),
            _load(_episode("episode-20260430-3", behavior_type="avoid")),
            _load(_episode("episode-20260430-4", behavior_type="approach")),
        ],
        coverage=AnnotationCoverage(
            observed_count=4,
            annotation_row_count=4,
            annotated_count=4,
            pending_count=0,
            pending_episode_ids=(),
            coverage="full",
        ),
    )

    payload = build_insight_payload(report)

    assert payload.kind == "insight_payload"
    assert payload.sample.total_episodes == 4
    assert payload.background.trigger == "social"
    assert payload.dominant_motif is not None
    assert payload.dominant_motif.support_count == 3
    assert payload.main_fork is not None
    assert payload.main_fork.support_count == 4
    assert payload.counterexample is not None
    assert payload.counterexample.dominant.behavior == "avoid"
    assert payload.counterexample.alternative.behavior == "approach"
    assert payload.outcome_patterns[0].horizon == "short_term"
    assert payload.outcome_patterns[0].total_count == 3


def test_insight_payload_to_dict_is_json_serializable_and_raw():
    report = build_report([_load(_episode("episode-20260430-1"))])

    payload_dict = build_insight_payload(report).to_dict()

    json.dumps(payload_dict, ensure_ascii=False)
    assert payload_dict["kind"] == "insight_payload"
    assert "Развилка реакций" not in json.dumps(payload_dict, ensure_ascii=False)
    assert "контакт с людьми" not in json.dumps(payload_dict, ensure_ascii=False)


def _load(data):
    return Episode.model_validate(data)


def _episode(
    episode_id,
    *,
    behavior_type="avoid",
    outcome_type="relief",
    emotion_label="страх",
):
    return {
        "id": episode_id,
        "date": f"{episode_id[8:12]}-{episode_id[12:14]}-{episode_id[14:16]}",
        "source": "telegram-chat:123",
        "observed": {
            "situation": {"value": "Group chat.", "source_quote": "group chat"},
            "automatic_thought": {
                "value": "They will judge me.",
                "source_quote": "they will judge me",
            },
            "emotion": {"value": emotion_label, "source_quote": emotion_label},
            "physical": {"value": "Tight chest.", "source_quote": "tight chest"},
            "behavior": {"value": "Closed the chat.", "source_quote": "Closed the chat."},
            "short_term_consequence": {"value": "Relief.", "source_quote": "Relief."},
            "long_term_consequence": {
                "value": "Still unresolved.",
                "source_quote": "Still unresolved.",
            },
        },
        "derived": {
            "nodes": [
                {
                    "id": "node-1",
                    "node_origin": "observed",
                    "kind": "cognition",
                    "text": "They will judge me.",
                    "source_field": "observed.automatic_thought",
                    "source_quote": "they will judge me",
                    "confidence": 0.9,
                },
                {
                    "id": "node-2",
                    "node_origin": "observed",
                    "kind": "short_outcome",
                    "text": "Relief.",
                    "source_field": "observed.short_term_consequence",
                    "source_quote": "Relief.",
                    "confidence": 0.85,
                },
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
                    "label": emotion_label,
                    "intensity": 0.66,
                    "valence": -0.8,
                    "arousal": 0.8,
                    "source_field": "observed.emotion",
                    "source_quote": emotion_label,
                    "confidence": 0.9,
                }
            ],
            "behavior_annotations": [
                {
                    "id": "behavior-annotation-1",
                    "type": behavior_type,
                    "source_field": "observed.behavior",
                    "source_quote": "Closed the chat.",
                    "confidence": 0.9,
                }
            ],
            "outcome_annotations": [
                {
                    "id": "outcome-annotation-1",
                    "node_id": "node-2",
                    "horizon": "short_term",
                    "type": outcome_type,
                    "source_field": "observed.short_term_consequence",
                    "source_quote": "Relief.",
                    "confidence": 0.85,
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
                }
            ],
        },
    }

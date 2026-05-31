import json

import pytest
from pydantic import ValidationError

from app.schemas.episode import Episode


def _empty_derived():
    return {
        "nodes": [],
        "trigger_annotations": [],
        "actor_annotations": [],
        "cognition_annotations": [],
        "emotion_annotations": [],
        "behavior_annotations": [],
        "relations": [],
    }


def _valid_episode(**overrides):
    episode = {
        "id": "episode-20260430-1",
        "date": "2026-04-30",
        "source": "telegram-chat:123",
        "observed": {
            "situation": {
                "value": "Asked a question.",
                "source_quote": "I asked a question",
            },
            "automatic_thought": {
                "value": "They will judge me.",
                "source_quote": "they will judge me",
            },
            "emotion": {"value": "Anxiety.", "source_quote": "anxious"},
            "physical": {"value": "Tight chest.", "source_quote": "tight chest"},
            "behavior": {
                "value": "Closed the chat.",
                "source_quote": "closed the chat",
            },
            "short_term_consequence": {
                "value": "Relief.",
                "source_quote": "relieved",
            },
            "long_term_consequence": {
                "value": "Question stayed unresolved.",
                "source_quote": "still did not know",
            },
        },
        "derived": _empty_derived(),
    }
    episode.update(overrides)
    return episode


def test_episode_schema_accepts_valid_episode():
    episode = Episode.model_validate(_valid_episode())

    assert episode.id == "episode-20260430-1"
    assert episode.derived.cognition_annotations == []


def test_episode_schema_accepts_optional_full_observed_fields():
    data = _valid_episode()
    data["observed"].update(
        {
            "trigger": {"value": "tr", "source_quote": "tr"},
            "actor": {"value": "ac", "source_quote": "ac"},
            "quote": {"value": "sp", "source_quote": "sp"},
        }
    )

    episode = Episode.model_validate(data)

    assert episode.observed.trigger is not None
    assert episode.observed.trigger.value == "tr"


def test_episode_schema_rejects_emotion_appendixes():
    data = _valid_episode()
    data["observed"]["emotion"] = {
        "value": "страх: 1.0, стыд: 0.33; другое: растерянность",
        "source_quote": "страх: 1.0, стыд: 0.33; другое: растерянность",
        "it" + "ems": [
            {
                "label": "страх",
                "intensity": 1.0,
                "source_quote": "страх высокий",
            },
            {
                "label": "стыд",
                "intensity": 0.33,
                "source_quote": "стыд низкий",
            },
        ],
        "free" + "_text": "растерянность",
    }

    with pytest.raises(ValidationError):
        Episode.model_validate(data)


def test_episode_schema_accepts_derived_annotations():
    data = _valid_episode()
    data["observed"].update(
        {
            "trigger": {"value": "comment", "source_quote": "comment"},
            "actor": {"value": "me and colleague", "source_quote": "me and colleague"},
            "quote": {"value": "not good", "source_quote": "not good"},
        }
    )
    data["derived"] = {
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
                "source_field": "observed.trigger",
                "source_quote": "comment",
                "confidence": 0.9,
            }
        ],
        "actor_annotations": [
            {
                "id": "actor-annotation-1",
                "role": "self",
                "label": "me",
                "source_field": "observed.actor",
                "source_quote": "me",
                "confidence": 1.0,
            }
        ],
        "cognition_annotations": [
            {
                "id": "cognition-annotation-1",
                "node_id": "node-1",
                "text": "They will judge me.",
                "kind": "prediction",
                "source_field": "observed.automatic_thought",
                "source_quote": "they will judge me",
                "confidence": 0.8,
            }
        ],
        "emotion_annotations": [
            {
                "id": "emotion-annotation-1",
                "label": "страх",
                "intensity": 1.0,
                "valence": -0.8,
                "arousal": 0.9,
                "source_field": "observed.emotion",
                "source_quote": "anxious",
                "confidence": 0.85,
            }
        ],
        "behavior_annotations": [
            {
                "id": "behavior-annotation-1",
                "type": "avoid",
                "source_field": "observed.behavior",
                "source_quote": "closed the chat",
                "confidence": 0.95,
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
                "type": "precedes",
                "from_ref": "observed.situation",
                "to_ref": "observed.behavior",
                "source_field": "observed.situation",
                "source_quote": "comment",
                "confidence": 0.7,
            },
        ],
    }

    episode = Episode.model_validate(data)

    assert episode.derived.trigger_annotations[0].type == "social"
    assert episode.derived.nodes[0].node_origin == "observed"
    assert episode.derived.cognition_annotations[0].node_id == "node-1"
    assert episode.derived.emotion_annotations[0].valence == -0.8
    assert episode.derived.relations[0].from_ref == "node-1"


def test_episode_schema_rejects_legacy_derived_keys():
    data = _valid_episode(
        derived={
            "atomic_thoughts": [],
            "cognitive_distortions": [],
        }
    )

    with pytest.raises(ValidationError):
        Episode.model_validate(data)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    (
        ("nodes", "kind", "event"),
        ("nodes", "node_origin", "direct"),
        ("nodes", "confidence", 1.1),
        ("trigger_annotations", "type", "weather"),
        ("behavior_annotations", "type", "run"),
        ("cognition_annotations", "kind", "distortion"),
        ("emotion_annotations", "label", "паника"),
        ("trigger_annotations", "confidence", 1.1),
        ("emotion_annotations", "valence", -1.1),
        ("emotion_annotations", "arousal", 1.1),
        ("relations", "type", "causes"),
        ("relations", "from_ref", "observed.money"),
        ("relations", "confidence", 1.1),
    ),
)
def test_episode_schema_rejects_invalid_annotation_values(section, field, value):
    data = _valid_episode()
    data["derived"] = {
        "nodes": [
            {
                "id": "node-1",
                "node_origin": "observed",
                "kind": "cognition",
                "text": "They will judge me.",
                "source_field": "observed.automatic_thought",
                "source_quote": "they will judge me",
                "confidence": 0.8,
            }
        ],
        "trigger_annotations": [
            {
                "id": "trigger-annotation-1",
                "type": "social",
                "source_field": "observed.situation",
                "source_quote": "chat",
                "confidence": 0.8,
            }
        ],
        "actor_annotations": [],
        "cognition_annotations": [
            {
                "id": "cognition-annotation-1",
                "text": "They will judge me.",
                "kind": "prediction",
                "source_field": "observed.automatic_thought",
                "source_quote": "they will judge me",
                "confidence": 0.8,
            }
        ],
        "emotion_annotations": [
            {
                "id": "emotion-annotation-1",
                "label": "страх",
                "intensity": 1.0,
                "valence": -0.8,
                "arousal": 0.9,
                "source_field": "observed.emotion",
                "source_quote": "anxious",
                "confidence": 0.85,
            }
        ],
        "behavior_annotations": [
            {
                "id": "behavior-annotation-1",
                "type": "avoid",
                "source_field": "observed.behavior",
                "source_quote": "closed the chat",
                "confidence": 0.95,
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
                "confidence": 0.8,
            }
        ],
    }
    data["derived"][section][0][field] = value

    with pytest.raises(ValidationError):
        Episode.model_validate(data)


def test_episode_schema_defaults_old_node_origin_to_observed():
    data = _valid_episode()
    data["derived"]["nodes"] = [
        {
            "id": "node-1",
            "kind": "emotion",
            "text": "страх",
            "source_field": "observed.emotion",
            "source_quote": "anxious",
            "confidence": 0.9,
        }
    ]

    episode = Episode.model_validate(data)

    assert episode.derived.nodes[0].node_origin == "observed"


def test_episode_schema_accepts_support_node_origin():
    data = _valid_episode()
    data["derived"]["nodes"] = [
        {
            "id": "node-1",
            "node_origin": "support",
            "kind": "cognition",
            "text": "fear of social evaluation",
            "source_field": "observed.automatic_thought",
            "source_quote": "they will judge me",
            "confidence": 0.75,
        }
    ]

    episode = Episode.model_validate(data)

    assert episode.derived.nodes[0].node_origin == "support"


def test_episode_schema_defaults_old_derived_relations_to_empty_list():
    data = _valid_episode()
    data["derived"].pop("relations")

    episode = Episode.model_validate(data)

    assert episode.derived.relations == []


def test_json_schema_describes_plain_emotion_and_full_fields():
    schema = json.loads(open("model/episode.schema.json", encoding="utf-8").read())
    observed = schema["properties"]["observed"]["properties"]

    assert observed["trigger"] == {"$ref": "#/$defs/observed_field"}
    assert observed["actor"] == {"$ref": "#/$defs/observed_field"}
    assert observed["quote"] == {"$ref": "#/$defs/observed_field"}
    assert observed["emotion"] == {"$ref": "#/$defs/observed_field"}
    assert "emotion_item" not in schema["$defs"]
    assert "emotion_field" not in schema["$defs"]


def test_json_schema_describes_derived_annotations():
    schema = json.loads(open("model/episode.schema.json", encoding="utf-8").read())
    derived = schema["properties"]["derived"]

    assert derived["required"] == [
        "nodes",
        "trigger_annotations",
        "actor_annotations",
        "cognition_annotations",
        "emotion_annotations",
        "behavior_annotations",
    ]
    assert "atomic_thought" not in schema["$defs"]
    assert "cognitive_distortion" not in schema["$defs"]
    assert schema["$defs"]["confidence"] == {
        "type": "number",
        "minimum": 0.0,
        "maximum": 1.0,
    }
    assert schema["$defs"]["node"]["properties"]["kind"]["enum"] == [
        "actor",
        "cognition",
        "emotion",
        "quote",
        "behavior",
    ]
    assert schema["$defs"]["node"]["properties"]["node_origin"] == {
        "type": "string",
        "enum": ["observed", "support"],
        "default": "observed",
    }
    assert schema["$defs"]["cognition_annotation"]["properties"]["node_id"] == {
        "anyOf": [
            {"type": "string", "pattern": "^node-[0-9]+$"},
            {"type": "null"},
        ],
        "default": None,
    }
    assert schema["$defs"]["emotion_annotation"]["properties"]["valence"] == {
        "type": "number",
        "minimum": -1.0,
        "maximum": 1.0,
    }
    assert schema["$defs"]["emotion_annotation"]["properties"]["arousal"] == {
        "type": "number",
        "minimum": 0.0,
        "maximum": 1.0,
    }
    relation = schema["$defs"]["graph_relation"]
    assert relation["properties"]["type"]["enum"] == [
        "belongs_to",
        "derived_from",
        "precedes",
        "leads_to",
        "co_occurs_with",
        "elicits",
        "expressed_as",
        "reinforces",
        "contrasts_with",
        "acts_in",
        "occurs_in",
    ]
    assert "relations" in derived["properties"]


def test_episode_example_matches_schema_model():
    data = json.loads(open("model/episode.example.json", encoding="utf-8").read())

    episode = Episode.model_validate(data)

    assert episode.derived.cognition_annotations[0].id == "cognition-annotation-1"


def test_episode_template_uses_current_derived_keys():
    data = json.loads(open("model/episode.template.json", encoding="utf-8").read())

    assert data["derived"] == _empty_derived()

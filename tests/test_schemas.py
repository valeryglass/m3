import json

import pytest
from pydantic import ValidationError

from app.schemas.episode import Episode


def test_episode_schema_accepts_valid_episode():
    episode = Episode.model_validate(
        {
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
                "body": {"value": "Tight chest.", "source_quote": "tight chest"},
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
            "derived": {
                "atomic_thoughts": [
                    {
                        "id": "atomic-thought-1",
                        "text": "They will judge me.",
                        "source_field": "observed.automatic_thought",
                        "source_quote": "they will judge me",
                        "confidence": "medium",
                    }
                ],
                "cognitive_distortions": [],
            },
        }
    )

    assert episode.id == "episode-20260430-1"


def test_episode_schema_accepts_optional_full_observed_fields():
    episode = Episode.model_validate(
        {
            "id": "episode-20260430-1",
            "date": "2026-04-30",
            "source": "telegram-chat:123",
            "observed": {
                "situation": {"value": "s", "source_quote": "s"},
                "trigger": {"value": "tr", "source_quote": "tr"},
                "actors": {"value": "ac", "source_quote": "ac"},
                "speech": {"value": "sp", "source_quote": "sp"},
                "automatic_thought": {"value": "at", "source_quote": "at"},
                "emotion": {"value": "e", "source_quote": "e"},
                "body": {"value": "body", "source_quote": "body"},
                "behavior": {"value": "b", "source_quote": "b"},
                "short_term_consequence": {"value": "st", "source_quote": "st"},
                "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            },
            "derived": {
                "atomic_thoughts": [],
                "cognitive_distortions": [],
            },
        }
    )

    assert episode.observed.trigger is not None
    assert episode.observed.trigger.value == "tr"


def test_episode_schema_accepts_structured_emotions():
    episode = Episode.model_validate(
        {
            "id": "episode-20260430-1",
            "date": "2026-04-30",
            "source": "telegram-chat:123",
            "observed": {
                "situation": {"value": "s", "source_quote": "s"},
                "trigger": {"value": "tr", "source_quote": "tr"},
                "actors": {"value": "ac", "source_quote": "ac"},
                "speech": {"value": "sp", "source_quote": "sp"},
                "automatic_thought": {"value": "at", "source_quote": "at"},
                "emotion": {
                    "value": "страх: 1.0, стыд: 0.33; другое: растерянность",
                    "source_quote": "страх: 1.0, стыд: 0.33; другое: растерянность",
                    "items": [
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
                    "free_text": "растерянность",
                },
                "body": {"value": "body", "source_quote": "body"},
                "behavior": {"value": "b", "source_quote": "b"},
                "short_term_consequence": {"value": "st", "source_quote": "st"},
                "long_term_consequence": {"value": "lt", "source_quote": "lt"},
            },
            "derived": {
                "atomic_thoughts": [],
                "cognitive_distortions": [],
            },
        }
    )

    assert episode.observed.emotion.items is not None
    assert episode.observed.emotion.items[0].label == "страх"
    assert episode.observed.emotion.items[0].intensity == 1.0
    assert episode.observed.emotion.free_text == "растерянность"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("label", "паника"),
        ("intensity", 1.1),
        ("free_text", 3),
    ),
)
def test_episode_schema_rejects_invalid_structured_emotion(field, value):
    emotion_item = {
        "label": "страх",
        "intensity": 1.0,
        "source_quote": "страх высокий",
    }
    emotion = {
        "value": "страх высокий",
        "source_quote": "страх высокий",
        "items": [emotion_item],
    }
    if field == "free_text":
        emotion[field] = value
    else:
        emotion_item[field] = value

    with pytest.raises(ValidationError):
        Episode.model_validate(
            {
                "id": "episode-20260430-1",
                "date": "2026-04-30",
                "source": "telegram-chat:123",
                "observed": {
                    "situation": {"value": "s", "source_quote": "s"},
                    "automatic_thought": {"value": "at", "source_quote": "at"},
                    "emotion": emotion,
                    "body": {"value": "body", "source_quote": "body"},
                    "behavior": {"value": "b", "source_quote": "b"},
                    "short_term_consequence": {"value": "st", "source_quote": "st"},
                    "long_term_consequence": {"value": "lt", "source_quote": "lt"},
                },
                "derived": {
                    "atomic_thoughts": [],
                    "cognitive_distortions": [],
                },
            }
        )


def test_json_schema_describes_emotion_items_and_full_fields():
    schema = json.loads(open("model/episode.schema.json", encoding="utf-8").read())
    observed = schema["properties"]["observed"]["properties"]
    emotion_item = schema["$defs"]["emotion_item"]

    assert observed["trigger"] == {"$ref": "#/$defs/observed_field"}
    assert observed["actors"] == {"$ref": "#/$defs/observed_field"}
    assert observed["speech"] == {"$ref": "#/$defs/observed_field"}
    assert observed["emotion"] == {"$ref": "#/$defs/emotion_field"}
    assert emotion_item["properties"]["label"]["enum"] == [
        "нейтраль/мешанные",
        "любовь/тепло",
        "радость",
        "отвращение",
        "стыд",
        "грусть",
        "злость",
        "страх",
    ]
    assert emotion_item["properties"]["intensity"] == {
        "type": "number",
        "minimum": 0.0,
        "maximum": 1.0,
    }
    assert schema["$defs"]["emotion_field"]["properties"]["free_text"] == {
        "type": "string"
    }

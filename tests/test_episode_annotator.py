from copy import deepcopy

from app.episode_annotator import annotate_episode
from app.schemas.episode import Derived, Episode


def test_episode_annotator_builds_minimal_derived():
    episode = Episode.model_validate(_episode())

    derived = annotate_episode(episode)

    assert derived.nodes
    assert derived.cognition_annotations[0].kind == "evaluation"
    assert derived.emotion_annotations[0].label == "страх"
    assert derived.behavior_annotations[0].type == "avoid"
    assert len(derived.outcome_annotations) == 2
    assert derived.relations


def test_episode_annotator_preserves_observed_boundary():
    raw = _episode()
    episode = Episode.model_validate(raw)
    before = deepcopy(episode.observed.model_dump(mode="json"))

    annotate_episode(episode)

    assert episode.observed.model_dump(mode="json") == before


def test_episode_annotator_emits_schema_valid_payload():
    derived = annotate_episode(Episode.model_validate(_episode()))

    assert Derived.model_validate(derived.model_dump(mode="json")) == derived
    for node in derived.nodes:
        assert node.source_quote
        assert node.source_field.startswith("observed.")
        assert 0 <= node.confidence <= 1


def _episode():
    return {
        "id": "episode-20260503-1",
        "date": "2026-05-03",
        "source": "telegram-chat:123",
        "observed": {
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "коллега в чате", "source_quote": "коллега в чате"},
            "actor": {"value": "коллега", "source_quote": "коллега"},
            "quote": {"value": "цитата", "source_quote": "цитата"},
            "automatic_thought": {"value": "я все испортил", "source_quote": "я все испортил"},
            "emotion": {"value": "страх", "source_quote": "страх"},
            "behavior": {"value": "дистанцироваться", "source_quote": "дистанцироваться"},
            "physical": {"value": "напряжение", "source_quote": "напряжение"},
            "short_term_consequence": {"value": "стало легче", "source_quote": "стало легче"},
            "long_term_consequence": {"value": "цена избегания", "source_quote": "цена избегания"},
        },
    }

import pytest
from pydantic import ValidationError

from app.domain_classifier import (
    classify_episode_domains,
    reviewed_domain_annotations,
)
from app.schemas.episode import Derived, Episode
from tests.test_annotation_producer import _episode


def test_domain_classifier_direct_work_match_uses_situation_evidence():
    episode = _load(
        _episode_with_situation(
            "На работе обсуждал задачу с коллегой.",
            "на работе обсуждал задачу",
        )
    )

    decision = classify_episode_domains(episode)

    assert decision.needs_review is False
    assert decision.annotations[0].domain == "work_study"
    assert decision.annotations[0].role == "primary"
    assert decision.annotations[0].method == "deterministic_rule"
    assert decision.annotations[0].source_field == "observed.situation"
    assert decision.annotations[0].source_quote == "на работе обсуждал задачу"


def test_domain_classifier_routes_tied_domains_to_review():
    episode = _load(
        _episode_with_situation(
            "Дома говорил с семьёй.",
            "дома говорил с семьёй",
        )
    )

    decision = classify_episode_domains(episode)

    assert decision.needs_review is True
    assert decision.annotations[0].domain == "unknown"
    assert set(decision.candidate_domains[:2]) == {
        "close_relationships_family",
        "home_daily_life",
    }


def test_domain_classifier_routes_unsupported_situation_to_review():
    episode = _load(_episode_with_situation("Произошло событие.", "произошло событие"))

    decision = classify_episode_domains(episode)

    assert decision.needs_review is True
    assert decision.candidate_domains == ()
    assert decision.annotations[0].domain == "unknown"


def test_reviewed_override_keeps_selected_evidence_and_confidence():
    episode = _load(
        _episode_with_situation(
            "Обсуждал вопрос с партнёром.",
            "обсуждал вопрос с партнёром",
        )
    )

    annotations = reviewed_domain_annotations(
        episode,
        primary_domain="close_relationships_family",
        primary_source_field="observed.situation",
    )

    assert annotations[0].method == "explicit_review"
    assert annotations[0].source_quote == "обсуждал вопрос с партнёром"
    assert annotations[0].confidence == 0.9


def test_domain_annotation_cardinality_and_unknown_rules():
    base = _load(_episode()).derived.model_dump(mode="json")
    base["domain_annotations"] = [
        _annotation("domain-annotation-1", "unknown", "primary"),
        _annotation("domain-annotation-2", "work_study", "secondary"),
    ]

    with pytest.raises(ValidationError, match="unknown primary"):
        Derived.model_validate(base)


def _load(data):
    return Episode.model_validate(data)


def _episode_with_situation(value, quote):
    data = _episode()
    data["observed"]["situation"] = {"value": value, "source_quote": quote}
    return data


def _annotation(annotation_id, domain, role):
    return {
        "id": annotation_id,
        "domain": domain,
        "role": role,
        "method": "explicit_review",
        "source_field": "observed.situation",
        "source_quote": "evidence",
        "confidence": 0.9,
    }

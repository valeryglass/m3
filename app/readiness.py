from __future__ import annotations

from dataclasses import dataclass

from app.schemas.episode import Episode


ANNOTATION_FIELDS = (
    "trigger_annotations",
    "actor_annotations",
    "cognition_annotations",
    "emotion_annotations",
    "behavior_annotations",
    "outcome_annotations",
)
REQUIRED_OBSERVED_FIELDS = (
    "situation",
    "automatic_thought",
    "emotion",
    "behavior",
    "physical",
    "short_term_consequence",
    "long_term_consequence",
)
MIN_USABLE_CONFIDENCE = 0.5


@dataclass(frozen=True)
class EpisodeReadiness:
    episode_id: str
    observed_ready: bool
    annotation_ready: bool
    graph_ready: bool
    report_ready: bool
    payload_eligible: bool
    gap_reasons: tuple[str, ...]


def classify_episode_readiness(episode: Episode) -> EpisodeReadiness:
    derived = episode.derived
    annotations_present = any(
        getattr(derived, field) for field in ANNOTATION_FIELDS
    )
    observed_ready = _observed_ready(episode)
    annotation_ready = bool(derived.nodes) and annotations_present
    graph_ready = annotation_ready and bool(derived.relations)
    usable_confidence = _has_usable_confidence(episode)
    report_ready = graph_ready and usable_confidence
    payload_eligible = (
        report_ready
        and bool(derived.cognition_annotations)
        and bool(derived.emotion_annotations)
        and bool(derived.behavior_annotations)
    )

    gaps: list[str] = []
    if not observed_ready:
        gaps.append("missing_observed")
    if not derived.nodes and not annotations_present and not derived.relations:
        gaps.append("empty_derived")
    else:
        if not derived.nodes or not annotations_present:
            gaps.append("ambiguous_episode")
        if not derived.relations:
            gaps.append("insufficient_relations")
    if graph_ready and not usable_confidence:
        gaps.append("low_confidence")

    return EpisodeReadiness(
        episode_id=episode.id,
        observed_ready=observed_ready,
        annotation_ready=annotation_ready,
        graph_ready=graph_ready,
        report_ready=report_ready,
        payload_eligible=payload_eligible,
        gap_reasons=tuple(gaps),
    )


def _observed_ready(episode: Episode) -> bool:
    return all(
        _field_ready(getattr(episode.observed, field, None))
        for field in REQUIRED_OBSERVED_FIELDS
    )


def _field_ready(value) -> bool:
    return (
        value is not None
        and bool(str(getattr(value, "value", "")).strip())
        and bool(str(getattr(value, "source_quote", "")).strip())
    )


def _has_usable_confidence(episode: Episode) -> bool:
    values = []
    derived = episode.derived
    values.extend(item.confidence for item in derived.nodes)
    values.extend(item.confidence for item in derived.relations)
    for field in ANNOTATION_FIELDS:
        values.extend(item.confidence for item in getattr(derived, field))
    return bool(values) and min(values) >= MIN_USABLE_CONFIDENCE

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import mean

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
STATE_SNAPSHOT_FIELDS = (
    ("cognitive", "automatic_thought"),
    ("emotional", "emotion"),
    ("physiological", "physical"),
    ("behavioral", "behavior"),
)
MIN_USABLE_CONFIDENCE = 0.5


@dataclass(frozen=True)
class EpisodeReadiness:
    episode_id: str
    observed_ready: bool
    graph_ready: bool
    report_ready: bool
    profile_eligible: bool
    gap_reasons: tuple[str, ...]


@dataclass(frozen=True)
class StateSnapshot:
    episode_id: str
    kind: str
    cognitive: bool
    emotional: bool
    physiological: bool
    behavioral: bool
    confidence: float


@dataclass(frozen=True)
class StateSnapshotSummary:
    total: int
    complete: int
    partial: int
    average_confidence: float


@dataclass(frozen=True)
class ProfileMaturity:
    quantity: int
    diversity: int
    recurrence: str
    stability_percent: int
    coverage_percent: int
    freshness: str
    confidence_band: str


def classify_episode_readiness(episode: Episode) -> EpisodeReadiness:
    derived = episode.derived
    annotations_present = any(
        getattr(derived, field) for field in ANNOTATION_FIELDS
    )
    observed_ready = _observed_ready(episode)
    graph_ready = bool(derived.nodes) and annotations_present and bool(derived.relations)
    usable_confidence = _has_usable_confidence(episode)
    report_ready = graph_ready and usable_confidence
    profile_eligible = (
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
        graph_ready=graph_ready,
        report_ready=report_ready,
        profile_eligible=profile_eligible,
        gap_reasons=tuple(gaps),
    )


def build_state_snapshot(episode: Episode) -> StateSnapshot:
    availability = {
        name: _field_ready(getattr(episode.observed, field_name, None))
        for name, field_name in STATE_SNAPSHOT_FIELDS
    }
    confidence = round(sum(1 for value in availability.values() if value) / 4, 2)
    return StateSnapshot(
        episode_id=episode.id,
        kind="activated_main_state",
        cognitive=availability["cognitive"],
        emotional=availability["emotional"],
        physiological=availability["physiological"],
        behavioral=availability["behavioral"],
        confidence=confidence,
    )


def summarize_state_snapshots(episodes: list[Episode]) -> StateSnapshotSummary:
    snapshots = [build_state_snapshot(episode) for episode in episodes]
    if not snapshots:
        return StateSnapshotSummary(
            total=0,
            complete=0,
            partial=0,
            average_confidence=0.0,
        )
    complete = sum(1 for item in snapshots if item.confidence == 1.0)
    partial = sum(1 for item in snapshots if 0.0 < item.confidence < 1.0)
    return StateSnapshotSummary(
        total=len(snapshots),
        complete=complete,
        partial=partial,
        average_confidence=round(mean(item.confidence for item in snapshots), 2),
    )


def summarize_profile_maturity(
    episodes: list[Episode],
    readiness: tuple[EpisodeReadiness, ...],
) -> ProfileMaturity:
    eligible_ids = {item.episode_id for item in readiness if item.profile_eligible}
    eligible = [episode for episode in episodes if episode.id in eligible_ids]
    quantity = len(eligible)
    signatures = Counter(_profile_signature(episode) for episode in eligible)
    diversity = len(signatures)
    repeated = sum(count for count in signatures.values() if count > 1)
    stability_percent = round((repeated / quantity) * 100) if quantity else 0
    coverage_percent = round((quantity / len(episodes)) * 100) if episodes else 0
    recurrence = "stable" if repeated >= max(2, quantity // 3) else "emerging"

    return ProfileMaturity(
        quantity=quantity,
        diversity=diversity,
        recurrence=recurrence,
        stability_percent=stability_percent,
        coverage_percent=coverage_percent,
        freshness=_freshness(episodes),
        confidence_band=_confidence_band(quantity, coverage_percent, stability_percent),
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


def _profile_signature(episode: Episode) -> tuple[str, ...]:
    derived = episode.derived
    return (
        ",".join(sorted(item.kind for item in derived.cognition_annotations)),
        ",".join(sorted(item.label for item in derived.emotion_annotations)),
        ",".join(sorted(item.type for item in derived.behavior_annotations)),
    )


def _freshness(episodes: list[Episode]) -> str:
    if not episodes:
        return "none"
    latest = max(episode.date for episode in episodes)
    return latest.isoformat()


def _confidence_band(quantity: int, coverage: int, stability: int) -> str:
    score = 0
    if quantity >= 30:
        score += 2
    elif quantity >= 15:
        score += 1
    if coverage >= 80:
        score += 2
    elif coverage >= 50:
        score += 1
    if stability >= 50:
        score += 2
    elif stability >= 25:
        score += 1
    return ("low", "low-medium", "medium", "medium-high", "high")[min(score, 4)]

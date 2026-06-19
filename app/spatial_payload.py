from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.insight_payload import InsightPayload


VERSION = "0.1"


@dataclass(frozen=True)
class SpatialPathPayload:
    role: str
    signature: dict[str, str]
    support_count: int
    episode_ids: tuple[str, ...]


@dataclass(frozen=True)
class SpatialForkMarkerPayload:
    role: str
    base: dict[str, str]
    behaviors: tuple[dict[str, Any], ...]
    support_count: int
    episode_ids: tuple[str, ...]


@dataclass(frozen=True)
class SpatialOutcomeLinkPayload:
    role: str
    behavior: str
    horizon: str
    outcome: str
    support_count: int
    total_count: int
    episode_ids: tuple[str, ...]


@dataclass(frozen=True)
class SpatialPayload:
    kind: str
    version: str
    source_kind: str
    paths: tuple[SpatialPathPayload, ...]
    markers: tuple[SpatialForkMarkerPayload, ...]
    outcome_links: tuple[SpatialOutcomeLinkPayload, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_spatial_payload(payload: InsightPayload) -> SpatialPayload:
    paths: list[SpatialPathPayload] = []
    if payload.dominant_motif:
        paths.append(_path("dominant_motif", payload.dominant_motif))
    paths.extend(_path("stable_motif", motif) for motif in payload.stable_motifs)

    markers: list[SpatialForkMarkerPayload] = []
    if payload.main_fork:
        markers.append(
            SpatialForkMarkerPayload(
                role="fork",
                base={
                    "trigger": payload.main_fork.trigger,
                    "emotion": payload.main_fork.emotion,
                },
                behaviors=tuple(
                    {
                        "behavior": variant.behavior,
                        "support_count": variant.support_count,
                        "episode_ids": list(variant.episode_ids),
                    }
                    for variant in payload.main_fork.variants
                ),
                support_count=payload.main_fork.support_count,
                episode_ids=payload.main_fork.episode_ids,
            )
        )
    if payload.counterexample:
        markers.append(
            SpatialForkMarkerPayload(
                role="counterexample",
                base={
                    "trigger": payload.counterexample.trigger,
                    "emotion": payload.counterexample.emotion,
                },
                behaviors=(
                    {
                        "behavior": payload.counterexample.dominant.behavior,
                        "support_count": payload.counterexample.dominant.support_count,
                        "episode_ids": list(payload.counterexample.dominant.episode_ids),
                    },
                    {
                        "behavior": payload.counterexample.alternative.behavior,
                        "support_count": payload.counterexample.alternative.support_count,
                        "episode_ids": list(payload.counterexample.alternative.episode_ids),
                    },
                ),
                support_count=payload.counterexample.support_count,
                episode_ids=payload.counterexample.episode_ids,
            )
        )

    return SpatialPayload(
        kind="spatial_payload",
        version=VERSION,
        source_kind=payload.kind,
        paths=tuple(paths),
        markers=tuple(markers),
        outcome_links=tuple(
            SpatialOutcomeLinkPayload(
                role="outcome_pattern",
                behavior=pattern.behavior,
                horizon=pattern.horizon,
                outcome=pattern.outcome,
                support_count=pattern.support_count,
                total_count=pattern.total_count,
                episode_ids=pattern.episode_ids,
            )
            for pattern in payload.outcome_patterns
        ),
    )


def _path(role, motif) -> SpatialPathPayload:
    return SpatialPathPayload(
        role=role,
        signature={
            "trigger": motif.trigger,
            "emotion": motif.emotion,
            "behavior": motif.behavior,
        },
        support_count=motif.support_count,
        episode_ids=motif.episode_ids,
    )

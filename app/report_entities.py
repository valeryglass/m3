from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.insight_payload import InsightPayload


VERSION = "0.1"
REPORT_ENTITY_KINDS = (
    "evidence",
    "pattern",
    "exception",
    "change",
    "finding",
    "question",
    "gap",
)


@dataclass(frozen=True)
class ReportEntity:
    kind: str
    role: str
    title: str
    priority: int
    claim: str
    support_count: int | None = None
    episode_ids: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    question: str | None = None
    source: str = "insight_payload"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReportEntityPayload:
    kind: str
    version: str
    source_kind: str
    entities: tuple[ReportEntity, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "version": self.version,
            "source_kind": self.source_kind,
            "entities": tuple(entity.to_dict() for entity in self.entities),
        }


def build_report_entities(payload: InsightPayload) -> ReportEntityPayload:
    entities: list[ReportEntity] = []
    entities.append(_evidence_entity(payload))
    if payload.coverage.state == "partial" and payload.coverage.pending_count > 0:
        entities.append(_gap_entity(payload))
    if payload.dominant_motif:
        entities.append(
            ReportEntity(
                kind="pattern",
                role="dominant_motif",
                title="Главный повторяющийся сценарий",
                priority=100,
                claim="repeated trigger-emotion-behavior motif",
                support_count=payload.dominant_motif.support_count,
                episode_ids=payload.dominant_motif.episode_ids,
            )
        )
        entities.append(
            ReportEntity(
                kind="finding",
                role="dominant_motif_observation",
                title="Наблюдение",
                priority=95,
                claim="dominant motif is supported in the current sample",
                support_count=payload.dominant_motif.support_count,
                episode_ids=payload.dominant_motif.episode_ids,
            )
        )
    if payload.main_fork:
        entities.append(
            ReportEntity(
                kind="exception",
                role="fork",
                title="Точка выбора",
                priority=90,
                claim="same trigger-emotion base has multiple behaviors",
                support_count=payload.main_fork.support_count,
                episode_ids=payload.main_fork.episode_ids,
            )
        )
    if payload.counterexample:
        entities.append(
            ReportEntity(
                kind="exception",
                role="counterexample",
                title="Менее частый вариант",
                priority=80,
                claim="less frequent alternative behavior is present",
                support_count=payload.counterexample.support_count,
                episode_ids=payload.counterexample.episode_ids,
            )
        )
    if payload.contrast:
        entities.append(
            ReportEntity(
                kind="exception",
                role="contrast",
                title="Контраст",
                priority=75,
                claim="one behavior appears with different emotions",
                support_count=payload.contrast.support_count,
                episode_ids=payload.contrast.episode_ids,
            )
        )
    if payload.outcome_patterns:
        episode_ids = tuple(
            sorted({episode_id for item in payload.outcome_patterns for episode_id in item.episode_ids})
        )
        entities.append(
            ReportEntity(
                kind="pattern",
                role="outcome_pattern",
                title="Что обычно получается после реакции",
                priority=70,
                claim="repeated behavior-outcome patterns are present",
                support_count=len(episode_ids),
                episode_ids=episode_ids,
            )
        )
    if payload.sample.graph_ready_count > 0:
        entities.append(
            ReportEntity(
                kind="question",
                role="next_observation",
                title="Что понаблюдать дальше",
                priority=5,
                claim="next useful observation question",
                support_count=payload.sample.graph_ready_count,
                episode_ids=payload.sample.graph_ready_episode_ids,
                question="Что обычно происходит прямо перед повторяющейся реакцией?",
            )
        )
    return ReportEntityPayload(
        kind="report_entities",
        version=VERSION,
        source_kind=payload.kind,
        entities=tuple(sorted(entities, key=lambda item: (-item.priority, item.kind, item.role))),
    )


def _evidence_entity(payload: InsightPayload) -> ReportEntity:
    return ReportEntity(
        kind="evidence",
        role="sample",
        title="О данных",
        priority=110,
        claim="sample coverage and readiness",
        support_count=payload.sample.report_ready_count,
        episode_ids=payload.sample.graph_ready_episode_ids,
        evidence=(
            f"coverage:{payload.coverage.state}",
            f"observed:{payload.coverage.observed_count}",
            f"annotated:{payload.coverage.annotated_count}",
            f"payload_eligible:{payload.sample.payload_eligible_count}",
        ),
    )


def _gap_entity(payload: InsightPayload) -> ReportEntity:
    return ReportEntity(
        kind="gap",
        role="coverage_gap",
        title="Ограничение выборки",
        priority=10,
        claim="some observed episodes are not in the selected annotation-run",
        support_count=payload.coverage.pending_count,
        episode_ids=payload.coverage.pending_episode_ids,
        evidence=(f"pending:{payload.coverage.pending_count}",),
    )

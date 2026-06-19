from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.analytics_loader import annotation_coverage_for_episode_ids
from app.graph_report import GraphReport, build_report, load_episodes
from app.pattern_metrics import (
    behavior_fork_episode_ids,
    contrast_candidates,
    counterexample_candidates,
    loop_episode_ids,
    outcome_episode_ids,
    safe_filename,
    sorted_counter_items,
    trigger_counter,
)


VERSION = "0.1"


@dataclass(frozen=True)
class CoveragePayload:
    observed_count: int
    annotation_row_count: int
    annotated_count: int
    pending_count: int
    pending_episode_ids: tuple[str, ...]
    state: str


@dataclass(frozen=True)
class SamplePayload:
    total_episodes: int
    graph_ready_count: int
    report_ready_count: int
    payload_eligible_count: int
    graph_ready_episode_ids: tuple[str, ...]
    skipped_episode_ids: tuple[str, ...]


@dataclass(frozen=True)
class BackgroundPayload:
    trigger: str | None
    emotions: tuple[str, ...]
    behaviors: tuple[str, ...]


@dataclass(frozen=True)
class MotifPayload:
    trigger: str
    emotion: str
    behavior: str
    support_count: int
    episode_ids: tuple[str, ...]


@dataclass(frozen=True)
class ForkVariantPayload:
    behavior: str
    support_count: int
    episode_ids: tuple[str, ...]


@dataclass(frozen=True)
class ForkPayload:
    trigger: str
    emotion: str
    support_count: int
    episode_ids: tuple[str, ...]
    variants: tuple[ForkVariantPayload, ...]


@dataclass(frozen=True)
class CounterexamplePayload:
    trigger: str
    emotion: str
    dominant: ForkVariantPayload
    alternative: ForkVariantPayload
    support_count: int
    episode_ids: tuple[str, ...]


@dataclass(frozen=True)
class ContrastSidePayload:
    emotion: str
    support_count: int
    episode_ids: tuple[str, ...]


@dataclass(frozen=True)
class ContrastPayload:
    trigger: str
    behavior: str
    left: ContrastSidePayload
    right: ContrastSidePayload
    support_count: int
    episode_ids: tuple[str, ...]


@dataclass(frozen=True)
class OutcomePatternPayload:
    behavior: str
    horizon: str
    outcome: str
    support_count: int
    total_count: int
    episode_ids: tuple[str, ...]
    total_episode_ids: tuple[str, ...]


@dataclass(frozen=True)
class InsightPayload:
    kind: str
    version: str
    coverage: CoveragePayload
    sample: SamplePayload
    background: BackgroundPayload
    dominant_motif: MotifPayload | None
    stable_motifs: tuple[MotifPayload, ...]
    main_fork: ForkPayload | None
    counterexample: CounterexamplePayload | None
    contrast: ContrastPayload | None
    outcome_patterns: tuple[OutcomePatternPayload, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_insight_payload(report: GraphReport) -> InsightPayload:
    return InsightPayload(
        kind="insight_payload",
        version=VERSION,
        coverage=_coverage_payload(report),
        sample=_sample_payload(report),
        background=_background_payload(report),
        dominant_motif=_dominant_motif(report),
        stable_motifs=_stable_motifs(report),
        main_fork=_main_fork(report),
        counterexample=_counterexample(report),
        contrast=_contrast(report),
        outcome_patterns=_outcome_patterns(report),
    )


def _coverage_payload(report: GraphReport) -> CoveragePayload:
    coverage = report.coverage
    return CoveragePayload(
        observed_count=coverage.observed_count,
        annotation_row_count=coverage.annotation_row_count,
        annotated_count=coverage.annotated_count,
        pending_count=coverage.pending_count,
        pending_episode_ids=tuple(sorted(coverage.pending_episode_ids)),
        state=coverage.coverage,
    )


def _sample_payload(report: GraphReport) -> SamplePayload:
    return SamplePayload(
        total_episodes=report.total_episodes,
        graph_ready_count=len(report.graph_ready),
        report_ready_count=sum(1 for item in report.readiness if item.report_ready),
        payload_eligible_count=sum(
            1 for item in report.readiness if item.payload_eligible
        ),
        graph_ready_episode_ids=tuple(sorted(sig.episode_id for sig in report.graph_ready)),
        skipped_episode_ids=tuple(sorted(report.skipped)),
    )


def _background_payload(report: GraphReport) -> BackgroundPayload:
    trigger = _top_value(trigger_counter(report))
    emotion = _top_signature(report.emotion_signatures) or ()
    behavior = _top_signature(report.behavior_signatures) or ()
    return BackgroundPayload(trigger=trigger, emotions=emotion, behaviors=behavior)


def _dominant_motif(report: GraphReport) -> MotifPayload | None:
    items = sorted_counter_items(_motif_counter(report))
    if not items:
        return None
    loop, count = items[0]
    return _motif_payload(loop, count, report)


def _stable_motifs(report: GraphReport) -> tuple[MotifPayload, ...]:
    motifs = [
        _motif_payload(loop, count, report)
        for loop, count in sorted_counter_items(_motif_counter(report))
        if count >= 2
    ][:3]
    return tuple(motifs)


def _motif_counter(report: GraphReport):
    from collections import Counter

    return Counter(
        {loop: len(episode_ids) for loop, episode_ids in loop_episode_ids(report).items()}
    )


def _motif_payload(
    loop: tuple[str, str, str],
    count: int,
    report: GraphReport,
) -> MotifPayload:
    trigger, emotion, behavior = loop
    ids = loop_episode_ids(report).get(loop, frozenset())
    return MotifPayload(
        trigger=trigger,
        emotion=emotion,
        behavior=behavior,
        support_count=count,
        episode_ids=tuple(sorted(ids)),
    )


def _main_fork(report: GraphReport) -> ForkPayload | None:
    forks = [
        _fork_payload(base, variants)
        for base, variants in behavior_fork_episode_ids(report).items()
        if len(variants) > 1
    ]
    if not forks:
        return None
    return sorted(
        forks,
        key=lambda item: (-item.support_count, item.trigger, item.emotion),
    )[0]


def _fork_payload(
    base: tuple[str, str],
    variants: dict[str, frozenset[str]],
) -> ForkPayload:
    trigger, emotion = base
    all_episode_ids = set().union(*variants.values()) if variants else set()
    fork_variants = tuple(
        ForkVariantPayload(
            behavior=behavior,
            support_count=len(episode_ids),
            episode_ids=tuple(sorted(episode_ids)),
        )
        for behavior, episode_ids in sorted(
            variants.items(), key=lambda item: (-len(item[1]), item[0])
        )
    )
    return ForkPayload(
        trigger=trigger,
        emotion=emotion,
        support_count=len(all_episode_ids),
        episode_ids=tuple(sorted(all_episode_ids)),
        variants=fork_variants,
    )


def _counterexample(report: GraphReport) -> CounterexamplePayload | None:
    candidates = counterexample_candidates(report)
    if not candidates:
        return None
    candidate = candidates[0]
    trigger, emotion = candidate.base
    episode_ids = set(candidate.dominant_episode_ids) | set(
        candidate.alternative_episode_ids
    )
    return CounterexamplePayload(
        trigger=trigger,
        emotion=emotion,
        dominant=ForkVariantPayload(
            behavior=candidate.dominant_behavior,
            support_count=candidate.dominant_count,
            episode_ids=candidate.dominant_episode_ids,
        ),
        alternative=ForkVariantPayload(
            behavior=candidate.alternative_behavior,
            support_count=candidate.alternative_count,
            episode_ids=candidate.alternative_episode_ids,
        ),
        support_count=len(episode_ids),
        episode_ids=tuple(sorted(episode_ids)),
    )


def _contrast(report: GraphReport) -> ContrastPayload | None:
    candidates = contrast_candidates(report)
    if not candidates:
        return None
    candidate = candidates[0]
    episode_ids = set(candidate.left_episode_ids) | set(candidate.right_episode_ids)
    return ContrastPayload(
        trigger=candidate.trigger,
        behavior=candidate.behavior,
        left=ContrastSidePayload(
            emotion=candidate.left_emotion,
            support_count=candidate.left_count,
            episode_ids=candidate.left_episode_ids,
        ),
        right=ContrastSidePayload(
            emotion=candidate.right_emotion,
            support_count=candidate.right_count,
            episode_ids=candidate.right_episode_ids,
        ),
        support_count=len(episode_ids),
        episode_ids=tuple(sorted(episode_ids)),
    )


def _outcome_patterns(report: GraphReport) -> tuple[OutcomePatternPayload, ...]:
    support = outcome_episode_ids(report)
    totals: dict[tuple[str, str], set[str]] = {}
    for (behavior, horizon, _outcome), ids in support.items():
        totals.setdefault((behavior, horizon), set()).update(ids)
    patterns = []
    for (behavior, horizon, outcome), ids in sorted(
        support.items(), key=lambda item: (-len(item[1]), str(item[0]))
    )[:3]:
        total_ids = totals[(behavior, horizon)]
        patterns.append(
            OutcomePatternPayload(
                behavior=behavior,
                horizon=horizon,
                outcome=outcome,
                support_count=len(ids),
                total_count=len(total_ids),
                episode_ids=tuple(sorted(ids)),
                total_episode_ids=tuple(sorted(total_ids)),
            )
        )
    return tuple(patterns)


def _top_value(counter) -> str | None:
    items = sorted_counter_items(counter)
    return items[0][0] if items else None


def _top_signature(counter) -> tuple[str, ...] | None:
    items = sorted_counter_items(counter)
    return items[0][0] if items else None


def write_insight_payload(payload: InsightPayload, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Write deterministic insight payload JSON.")
    parser.add_argument("--episode-dir", default="data/episodes")
    parser.add_argument("--annotation-run-dir")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    episode_dir = Path(args.episode_dir)
    annotation_run_dir = Path(args.annotation_run_dir) if args.annotation_run_dir else None
    episodes = [
        episode
        for episode in load_episodes(episode_dir, annotation_run_dir=annotation_run_dir)
        if episode.source == args.source
    ]
    coverage = annotation_coverage_for_episode_ids(
        {episode.id for episode in episodes},
        annotation_run_dir=annotation_run_dir,
        known_episode_ids={episode.id for episode in episodes},
    )
    payload = build_insight_payload(build_report(episodes, coverage=coverage))
    output = (
        Path(args.output)
        if args.output
        else Path("data/exports/insight-payload") / f"{safe_filename(args.source)}.json"
    )
    path = write_insight_payload(payload, output)
    print(path.as_posix())


if __name__ == "__main__":
    main()

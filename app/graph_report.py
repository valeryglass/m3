from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

from app.analytics_loader import (
    AnnotationCoverage,
    annotation_coverage,
    load_analytics_episodes,
    require_full_coverage,
)
from app.readiness import (
    EpisodeReadiness,
    classify_episode_readiness,
)
from app.schemas.episode import Episode


ANNOTATION_FIELDS = (
    "trigger_annotations",
    "actor_annotations",
    "cognition_annotations",
    "emotion_annotations",
    "behavior_annotations",
    "outcome_annotations",
)


@dataclass(frozen=True)
class EpisodeSignature:
    episode_id: str
    source: str
    triggers: tuple[str, ...]
    cognitions: tuple[str, ...]
    emotions: tuple[str, ...]
    behaviors: tuple[str, ...]
    short_outcomes: tuple[str, ...]
    long_outcomes: tuple[str, ...]
    relation_types: tuple[str, ...]
    short_term_consequence: str
    long_term_consequence: str
    primary_domain: str = "unknown"
    secondary_domains: tuple[str, ...] = ()


@dataclass(frozen=True)
class GraphReport:
    total_episodes: int
    coverage: AnnotationCoverage
    graph_ready: tuple[EpisodeSignature, ...]
    readiness: tuple[EpisodeReadiness, ...]
    emotion_signatures: Counter[tuple[str, ...]]
    behavior_signatures: Counter[tuple[str, ...]]
    cognition_signatures: Counter[tuple[str, ...]]
    trigger_emotion_signatures: Counter[tuple[str, str]]
    cognition_behavior_signatures: Counter[tuple[str, str]]
    emotion_behavior_signatures: Counter[tuple[str, str]]
    relation_type_signatures: Counter[tuple[str, ...]]

    @property
    def skipped(self) -> tuple[str, ...]:
        return tuple(
            item.episode_id for item in self.readiness if not item.graph_ready
        )


def load_episodes(
    episode_dir: Path,
    annotation_run_dir: Path | None = None,
    annotation_run_root: Path | None = None,
) -> list[Episode]:
    return load_analytics_episodes(
        episode_dir,
        annotation_run_dir=annotation_run_dir,
        annotation_run_root=annotation_run_root,
    )


def is_graph_ready(episode: Episode) -> bool:
    return classify_episode_readiness(episode).graph_ready


def build_signature(episode: Episode) -> EpisodeSignature:
    derived = episode.derived
    return EpisodeSignature(
        episode_id=episode.id,
        source=episode.source,
        triggers=_sorted_unique(item.type for item in derived.trigger_annotations),
        cognitions=_sorted_unique(item.kind for item in derived.cognition_annotations),
        emotions=_sorted_unique(item.label for item in derived.emotion_annotations),
        behaviors=_sorted_unique(item.type for item in derived.behavior_annotations),
        short_outcomes=_sorted_unique(
            item.type
            for item in derived.outcome_annotations
            if item.horizon == "short_term"
        ),
        long_outcomes=_sorted_unique(
            item.type
            for item in derived.outcome_annotations
            if item.horizon == "long_term"
        ),
        relation_types=_sorted_unique(item.type for item in derived.relations),
        short_term_consequence=episode.observed.short_term_consequence.value.strip(),
        long_term_consequence=episode.observed.long_term_consequence.value.strip(),
        primary_domain=next(
            (
                item.domain
                for item in derived.domain_annotations
                if item.role == "primary"
            ),
            "unknown",
        ),
        secondary_domains=_sorted_unique(
            item.domain
            for item in derived.domain_annotations
            if item.role == "secondary"
        ),
    )


def build_report(
    episodes: list[Episode],
    *,
    coverage: AnnotationCoverage | None = None,
) -> GraphReport:
    if coverage is None:
        coverage = AnnotationCoverage(
            observed_count=len(episodes),
            annotation_row_count=0,
            annotated_count=len(episodes),
            pending_count=0,
            pending_episode_ids=(),
            coverage="full",
        )
    readiness = tuple(classify_episode_readiness(episode) for episode in episodes)
    graph_ready_ids = {item.episode_id for item in readiness if item.graph_ready}
    signatures = tuple(
        build_signature(episode) for episode in episodes if episode.id in graph_ready_ids
    )

    return _report_from_signatures(
        total_episodes=len(episodes),
        coverage=coverage,
        readiness=readiness,
        signatures=signatures,
    )


def subset_report(report: GraphReport, episode_ids: set[str]) -> GraphReport:
    readiness = tuple(
        item for item in report.readiness if item.episode_id in episode_ids
    )
    signatures = tuple(
        item for item in report.graph_ready if item.episode_id in episode_ids
    )
    return _report_from_signatures(
        total_episodes=len(episode_ids),
        coverage=AnnotationCoverage(
            observed_count=len(episode_ids),
            annotation_row_count=len(episode_ids),
            annotated_count=len(episode_ids),
            pending_count=0,
            pending_episode_ids=(),
            coverage="full",
        ),
        readiness=readiness,
        signatures=signatures,
    )


def _report_from_signatures(
    *,
    total_episodes: int,
    coverage: AnnotationCoverage,
    readiness: tuple[EpisodeReadiness, ...],
    signatures: tuple[EpisodeSignature, ...],
) -> GraphReport:
    return GraphReport(
        total_episodes=total_episodes,
        coverage=coverage,
        graph_ready=signatures,
        readiness=readiness,
        emotion_signatures=_count_tuple_signatures(sig.emotions for sig in signatures),
        behavior_signatures=_count_tuple_signatures(sig.behaviors for sig in signatures),
        cognition_signatures=_count_tuple_signatures(sig.cognitions for sig in signatures),
        trigger_emotion_signatures=_count_pairs(
            (trigger, emotion)
            for sig in signatures
            for trigger in sig.triggers
            for emotion in sig.emotions
        ),
        cognition_behavior_signatures=_count_pairs(
            (cognition, behavior)
            for sig in signatures
            for cognition in sig.cognitions
            for behavior in sig.behaviors
        ),
        emotion_behavior_signatures=_count_pairs(
            (emotion, behavior)
            for sig in signatures
            for emotion in sig.emotions
            for behavior in sig.behaviors
        ),
        relation_type_signatures=_count_tuple_signatures(
            sig.relation_types for sig in signatures
        ),
    )


def render_markdown(report: GraphReport, min_count: int = 2) -> str:
    skipped = tuple(item for item in report.readiness if not item.graph_ready)
    lines = [
        "# Graph Report",
        "",
        "## Summary",
        f"- episodes: {report.total_episodes}",
        f"- annotation_ready: {sum(1 for item in report.readiness if item.annotation_ready)}",
        f"- graph_ready: {len(report.graph_ready)}",
        f"- report_ready: {sum(1 for item in report.readiness if item.report_ready)}",
        f"- payload_eligible: {sum(1 for item in report.readiness if item.payload_eligible)}",
        "- coverage: "
        f"{report.coverage.annotated_count}/{report.coverage.observed_count} "
        f"annotated episodes ({report.coverage.coverage}); "
        f"pending: {report.coverage.pending_count}",
        f"- skipped: {len(skipped)}",
        "",
    ]

    lines.extend(_render_counter("## Relation Type Patterns", report.relation_type_signatures, min_count))

    lines.extend(["## Per Episode"])
    for sig in sorted(report.graph_ready, key=lambda item: item.episode_id):
        lines.append(
            "- "
            + sig.episode_id
            + ": trigger="
            + _join_values(sig.triggers)
            + "; cognition="
            + _join_values(sig.cognitions)
            + "; emotion="
            + _join_values(sig.emotions)
            + "; behavior="
            + _join_values(sig.behaviors)
        )

    if skipped:
        lines.extend(["", "## Gaps", f"- not_graph_ready: {len(skipped)}"])
        for item in sorted(skipped, key=lambda value: value.episode_id)[:10]:
            reasons = ", ".join(item.gap_reasons) or "unknown"
            lines.append(f"- {item.episode_id}: {reasons}")

    return "\n".join(lines).rstrip() + "\n"


def write_markdown_reports(
    episodes: list[Episode],
    output_dir: Path,
    *,
    min_count: int = 2,
    by_source: bool = False,
    coverage: AnnotationCoverage | None = None,
) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = [
        _write_report(
            output_dir / "all.md",
            build_report(episodes, coverage=coverage),
            min_count=min_count,
        )
    ]

    if by_source:
        for source, group in groupby(sorted(episodes, key=lambda item: item.source), key=lambda item: item.source):
            written.append(
                _write_report(
                    output_dir / f"{_safe_filename(source)}.md",
                    build_report(list(group)),
                    min_count=min_count,
                )
            )

    return tuple(written)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print or write Markdown graph signature reports for episode JSON files."
    )
    parser.add_argument(
        "--episode-dir",
        default="data/episodes",
        help="Directory containing episode-*.json files.",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=2,
        help="Minimum cluster count to show in top signature sections.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for Markdown report files. Prints to stdout when omitted.",
    )
    parser.add_argument(
        "--annotation-run-dir",
        help="Optional annotation-run directory with manifest.json and annotations.jsonl.",
    )
    parser.add_argument(
        "--by-source",
        action="store_true",
        help="When writing files, also create one report per episode source.",
    )
    parser.add_argument(
        "--require-full-coverage",
        action="store_true",
        help="Fail when the selected annotation-run has missing episode rows.",
    )
    args = parser.parse_args()

    coverage = annotation_coverage(
        Path(args.episode_dir),
        annotation_run_dir=Path(args.annotation_run_dir)
        if args.annotation_run_dir
        else None,
    )
    if args.require_full_coverage:
        require_full_coverage(coverage)
    episodes = load_episodes(
        Path(args.episode_dir),
        annotation_run_dir=Path(args.annotation_run_dir)
        if args.annotation_run_dir
        else None,
    )
    if args.output_dir:
        written = write_markdown_reports(
            episodes,
            Path(args.output_dir),
            min_count=args.min_count,
            by_source=args.by_source,
            coverage=coverage,
        )
        for path in written:
            print(path.as_posix())
    else:
        print(
            render_markdown(
                build_report(episodes, coverage=coverage),
                min_count=args.min_count,
            ),
            end="",
        )


def _sorted_unique(values) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values}))


def _count_tuple_signatures(signatures) -> Counter[tuple[str, ...]]:
    return Counter(tuple(signature) for signature in signatures if signature)


def _count_pairs(pairs) -> Counter[tuple[str, str]]:
    return Counter(pairs)


def _render_counter(
    title: str,
    counter: Counter,
    min_count: int,
    *,
    separator: str = " + ",
) -> list[str]:
    lines = [title]
    items = [
        (signature, count)
        for signature, count in counter.most_common()
        if count >= min_count
    ]
    if not items:
        lines.extend(["- none", ""])
        return lines
    for signature, count in items:
        lines.append(f"- {_join_values(signature, separator=separator)}: {count} episodes")
    lines.append("")
    return lines


def _join_values(values: tuple[str, ...], *, separator: str = " + ") -> str:
    return separator.join(values) if values else "none"


def _write_report(path: Path, report: GraphReport, *, min_count: int) -> Path:
    path.write_text(render_markdown(report, min_count=min_count), encoding="utf-8")
    return path


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return name or "unknown"


if __name__ == "__main__":
    main()

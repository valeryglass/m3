from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.schemas.episode import Episode


ANNOTATION_FIELDS = (
    "trigger_annotations",
    "actor_annotations",
    "cognition_annotations",
    "emotion_annotations",
    "behavior_annotations",
)


@dataclass(frozen=True)
class EpisodeSignature:
    episode_id: str
    source: str
    triggers: tuple[str, ...]
    cognitions: tuple[str, ...]
    emotions: tuple[str, ...]
    behaviors: tuple[str, ...]
    relation_types: tuple[str, ...]


@dataclass(frozen=True)
class GraphReport:
    total_episodes: int
    graph_ready: tuple[EpisodeSignature, ...]
    skipped: tuple[str, ...]
    emotion_signatures: Counter[tuple[str, ...]]
    behavior_signatures: Counter[tuple[str, ...]]
    cognition_signatures: Counter[tuple[str, ...]]
    trigger_emotion_signatures: Counter[tuple[str, str]]
    cognition_behavior_signatures: Counter[tuple[str, str]]
    emotion_behavior_signatures: Counter[tuple[str, str]]
    relation_type_signatures: Counter[tuple[str, ...]]


def load_episodes(episode_dir: Path) -> list[Episode]:
    episodes = []
    for path in sorted(episode_dir.glob("episode-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        episodes.append(Episode.model_validate(data))
    return episodes


def is_graph_ready(episode: Episode) -> bool:
    derived = episode.derived
    return (
        bool(derived.decompositions)
        and any(getattr(derived, field) for field in ANNOTATION_FIELDS)
        and bool(derived.relations)
    )


def build_signature(episode: Episode) -> EpisodeSignature:
    derived = episode.derived
    return EpisodeSignature(
        episode_id=episode.id,
        source=episode.source,
        triggers=_sorted_unique(item.type for item in derived.trigger_annotations),
        cognitions=_sorted_unique(item.kind for item in derived.cognition_annotations),
        emotions=_sorted_unique(item.label for item in derived.emotion_annotations),
        behaviors=_sorted_unique(item.type for item in derived.behavior_annotations),
        relation_types=_sorted_unique(item.type for item in derived.relations),
    )


def build_report(episodes: list[Episode]) -> GraphReport:
    signatures = tuple(build_signature(episode) for episode in episodes if is_graph_ready(episode))
    skipped = tuple(episode.id for episode in episodes if not is_graph_ready(episode))

    return GraphReport(
        total_episodes=len(episodes),
        graph_ready=signatures,
        skipped=skipped,
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
    lines = [
        "# Graph Report",
        "",
        "## Summary",
        f"- episodes: {report.total_episodes}",
        f"- graph_ready: {len(report.graph_ready)}",
        f"- skipped: {len(report.skipped)}",
        "",
    ]

    lines.extend(_render_counter("## Top Emotion Signatures", report.emotion_signatures, min_count))
    lines.extend(_render_counter("## Top Behavior Signatures", report.behavior_signatures, min_count))
    lines.extend(_render_counter("## Top Cognition Signatures", report.cognition_signatures, min_count))
    lines.extend(
        _render_counter(
            "## Trigger + Emotion Signatures",
            report.trigger_emotion_signatures,
            min_count,
            separator=" -> ",
        )
    )
    lines.extend(
        _render_counter(
            "## Cognition + Behavior Signatures",
            report.cognition_behavior_signatures,
            min_count,
            separator=" -> ",
        )
    )
    lines.extend(
        _render_counter(
            "## Emotion + Behavior Signatures",
            report.emotion_behavior_signatures,
            min_count,
            separator=" -> ",
        )
    )
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

    if report.skipped:
        lines.extend(["", "## Gaps", f"- not_graph_ready: {len(report.skipped)}"])
        lines.extend(f"- {episode_id}" for episode_id in sorted(report.skipped)[:10])

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a Markdown graph signature report for episode JSON files."
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
    args = parser.parse_args()

    episodes = load_episodes(Path(args.episode_dir))
    print(render_markdown(build_report(episodes), min_count=args.min_count), end="")


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


if __name__ == "__main__":
    main()

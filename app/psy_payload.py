from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from itertools import groupby
from pathlib import Path

from app.graph_report import GraphReport, build_report, load_episodes
from app.schemas.episode import Episode


WEEK_QUANT = "1week"


def render_psy_payload(
    report: GraphReport,
    *,
    title: str = "All Sources",
    min_count: int = 2,
) -> str:
    skipped = tuple(item for item in report.readiness if not item.graph_ready)
    lines = [
        "# Psy Payload",
        "",
        f"- scope: {title}",
        f"- episodes: {report.total_episodes}",
        f"- report_ready: {sum(1 for item in report.readiness if item.report_ready)}",
        f"- payload_eligible: {sum(1 for item in report.readiness if item.payload_eligible)}",
        f"- timespan_quant: {WEEK_QUANT}",
        "",
        "## Frequency",
        "",
    ]
    lines.extend(render_section("### Trigger Frequency", counter_from_signatures(sig.triggers for sig in report.graph_ready), min_count))
    lines.extend(render_section("### Emotion Frequency", report.emotion_signatures, min_count))
    lines.extend(render_section("### Cognition Frequency", report.cognition_signatures, min_count))
    lines.extend(render_section("### Behavior Frequency", report.behavior_signatures, min_count))
    lines.extend(render_section("## Ranking", loop_counter(report), min_count, separator=" -> "))
    lines.extend(render_section("## Contrast", contrast_counter(report), min_count, separator=" / "))
    lines.extend(render_behavior_forks(report, min_count, title="## Fork"))
    lines.extend(render_section("## Convergence", convergence_counter(report), min_count, separator=" -> "))
    lines.extend(render_section("## Outcome", outcome_counter(report, "short") + outcome_counter(report, "long"), min_count, separator=" -> "))
    lines.extend(render_section("## Counterpattern", counterpattern_counter(report), 1, separator=" -> "))
    lines.extend(render_section("## Drift", drift_counter(report), 1, separator=" -> "))
    lines.extend(render_section("## Novelty", novelty_counter(report), 1, separator=" -> "))
    lines.extend(render_section("## Stability", stability_counter(report), min_count, separator=" -> "))
    lines.extend(render_section("## Rarity", rarity_counter(report), 1, separator=" -> "))
    lines.extend(render_section("## Surprise", surprise_counter(report), 1, separator=" -> "))
    lines.extend(["## Gaps"])
    if not skipped:
        lines.extend(["- none", ""])
    else:
        lines.append(f"- not_graph_ready: {len(skipped)}")
        for item in sorted(skipped, key=lambda value: value.episode_id)[:12]:
            reasons = ", ".join(item.gap_reasons) or "unknown"
            lines.append(f"- {item.episode_id}: {reasons}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_psy_payload(
    episodes: list[Episode],
    output_dir: Path,
    *,
    min_count: int = 2,
    by_source: bool = False,
) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = [
        _write_report(
            output_dir / "all.md",
            build_report(episodes),
            title="All Sources",
            min_count=min_count,
        )
    ]
    if by_source:
        for source, group in groupby(sorted(episodes, key=lambda item: item.source), key=lambda item: item.source):
            written.append(
                _write_report(
                    output_dir / f"{safe_filename(source)}.md",
                    build_report(list(group)),
                    title=source,
                    min_count=min_count,
                )
            )
    return tuple(written)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write psy payload reports.")
    parser.add_argument("--episode-dir", default="data/episodes")
    parser.add_argument("--output-dir", default="data/reports/psy-payload")
    parser.add_argument("--by-source", action="store_true")
    parser.add_argument("--min-count", type=int, default=2)
    args = parser.parse_args()

    paths = write_psy_payload(
        load_episodes(Path(args.episode_dir)),
        Path(args.output_dir),
        min_count=args.min_count,
        by_source=args.by_source,
    )
    for path in paths:
        print(path.as_posix())


def counter_from_signatures(signatures) -> Counter[tuple[str, ...]]:
    return Counter(tuple(signature) for signature in signatures if signature)


def loop_counter(report: GraphReport) -> Counter[tuple[str, str, str]]:
    counter: Counter[tuple[str, str, str]] = Counter()
    for sig in report.graph_ready:
        for trigger in sig.triggers:
            for emotion in sig.emotions:
                for behavior in sig.behaviors:
                    counter[(trigger, emotion, behavior)] += 1
    return counter


def outcome_counter(report: GraphReport, outcome: str) -> Counter[tuple[str, str]]:
    counter: Counter[tuple[str, str]] = Counter()
    for sig in report.graph_ready:
        outcomes = sig.short_outcomes if outcome == "short" else sig.long_outcomes
        for behavior in sig.behaviors:
            for outcome_type in outcomes:
                counter[(behavior, outcome_type)] += 1
    return counter


def contrast_counter(report: GraphReport) -> Counter[tuple[str, str]]:
    counter: Counter[tuple[str, str]] = Counter()
    for sig in report.graph_ready:
        for emotion in sig.emotions:
            for behavior in sig.behaviors:
                counter[(emotion, behavior)] += 1
    return counter


def convergence_counter(report: GraphReport) -> Counter[tuple[str, str]]:
    counter: Counter[tuple[str, str]] = Counter()
    for sig in report.graph_ready:
        for trigger in sig.triggers:
            for outcome_type in sig.long_outcomes:
                counter[(trigger, outcome_type)] += 1
    return counter


def counterpattern_counter(report: GraphReport) -> Counter[tuple[str, str, str]]:
    counter: Counter[tuple[str, str, str]] = Counter()
    forks = behavior_forks(report)
    for (trigger, emotion), behaviors in forks.items():
        if len(behaviors) > 1:
            for behavior, count in behaviors.items():
                if count == 1:
                    counter[(trigger, emotion, behavior)] += 1
    return counter


def drift_counter(report: GraphReport) -> Counter[tuple[str, str]]:
    weeks = weekly_loop_sets(report)
    if len(weeks) < 2:
        return Counter()
    ordered = sorted(weeks)
    previous = set().union(*(weeks[week] for week in ordered[:-1]))
    latest = weeks[ordered[-1]]
    faded = previous - latest
    appeared = latest - previous
    counter: Counter[tuple[str, str]] = Counter()
    for signature in appeared:
        counter[("appeared", join_values(signature, separator=" -> "))] += 1
    for signature in faded:
        counter[("faded", join_values(signature, separator=" -> "))] += 1
    return counter


def novelty_counter(report: GraphReport) -> Counter[tuple[str, ...]]:
    weeks = weekly_loop_sets(report)
    if not weeks:
        return Counter()
    ordered = sorted(weeks)
    previous = set().union(*(weeks[week] for week in ordered[:-1])) if len(ordered) > 1 else set()
    return Counter({signature: 1 for signature in weeks[ordered[-1]] - previous})


def stability_counter(report: GraphReport) -> Counter[tuple[str, ...]]:
    by_loop: defaultdict[tuple[str, ...], set[str]] = defaultdict(set)
    for sig in report.graph_ready:
        week = week_key(sig.episode_id, report)
        for loop in loops_for_signature(sig):
            by_loop[loop].add(week)
    return Counter({loop: len(weeks) for loop, weeks in by_loop.items() if len(weeks) > 1})


def rarity_counter(report: GraphReport) -> Counter[tuple[str, ...]]:
    return Counter({loop: count for loop, count in loop_counter(report).items() if count == 1})


def surprise_counter(report: GraphReport) -> Counter[tuple[str, ...]]:
    loops = loop_counter(report)
    triggers: Counter[str] = Counter()
    emotions: Counter[str] = Counter()
    behaviors: Counter[str] = Counter()
    for (trigger, emotion, behavior), count in loops.items():
        triggers[trigger] += count
        emotions[emotion] += count
        behaviors[behavior] += count
    surprising = Counter()
    for loop, count in loops.items():
        trigger, emotion, behavior = loop
        if count == 1 and triggers[trigger] >= 2 and emotions[emotion] >= 2 and behaviors[behavior] >= 2:
            surprising[loop] = 1
    return surprising


def behavior_forks(report: GraphReport) -> dict[tuple[str, str], Counter[str]]:
    forks: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for sig in report.graph_ready:
        for trigger in sig.triggers:
            for emotion in sig.emotions:
                for behavior in sig.behaviors:
                    forks[(trigger, emotion)][behavior] += 1
    return forks


def weekly_loop_sets(report: GraphReport) -> dict[str, set[tuple[str, str, str]]]:
    weeks: defaultdict[str, set[tuple[str, str, str]]] = defaultdict(set)
    for sig in report.graph_ready:
        weeks[week_key(sig.episode_id, report)].update(loops_for_signature(sig))
    return dict(weeks)


def week_key(episode_id: str, report: GraphReport) -> str:
    # EpisodeSignature does not carry date yet; the id has the canonical YYYYMMDD.
    match = re.match(r"episode-(\d{4})(\d{2})(\d{2})-\d+", episode_id)
    if not match:
        return "unknown-week"
    from datetime import date

    year, month, day = (int(part) for part in match.groups())
    iso = date(year, month, day).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def loops_for_signature(sig) -> set[tuple[str, str, str]]:
    return {
        (trigger, emotion, behavior)
        for trigger in sig.triggers
        for emotion in sig.emotions
        for behavior in sig.behaviors
    }


def render_behavior_forks(report: GraphReport, min_count: int, *, title: str) -> list[str]:
    items = []
    for context, behaviors in behavior_forks(report).items():
        if sum(behaviors.values()) >= min_count and len(behaviors) > 1:
            items.append((context, behaviors))
    items.sort(key=lambda item: (-sum(item[1].values()), item[0]))
    lines = [title]
    if not items:
        lines.extend(["- none", ""])
        return lines
    for (trigger, emotion), behaviors in items:
        behavior_text = ", ".join(
            f"{behavior} ({count})" for behavior, count in behaviors.most_common()
        )
        lines.append(f"- {trigger} -> {emotion}: {behavior_text}")
    lines.append("")
    return lines


def render_section(
    title: str,
    counter,
    min_count: int,
    *,
    separator: str = " + ",
) -> list[str]:
    lines = [title]
    items = [(signature, count) for signature, count in counter.most_common() if count >= min_count]
    if not items:
        lines.extend(["- none", ""])
        return lines
    for signature, count in items:
        lines.append(f"- {join_values(signature, separator=separator)}: {count} episodes")
    lines.append("")
    return lines


def join_values(values, *, separator: str = " + ") -> str:
    if isinstance(values, str):
        return values
    return separator.join(str(value) for value in values) if values else "none"


def safe_filename(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return name or "unknown"


def _write_report(path: Path, report: GraphReport, *, title: str, min_count: int) -> Path:
    path.write_text(
        render_psy_payload(report, title=title, min_count=min_count),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    main()

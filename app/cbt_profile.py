from __future__ import annotations

import argparse
from collections import Counter
from itertools import groupby
from pathlib import Path

from app.cbt_analytics import (
    behavior_forks,
    loop_counter,
    novelty_counter,
    outcome_counter,
    render_section,
    safe_filename,
    stability_counter,
    WEEK_QUANT,
)
from app.graph_report import GraphReport, build_report, load_episodes
from app.schemas.episode import Episode


def render_cbt_profile(
    report: GraphReport,
    *,
    title: str = "All Sources",
    min_count: int = 2,
) -> str:
    skipped = tuple(item for item in report.readiness if not item.graph_ready)
    lines = [
        "# Domain Report",
        "",
        f"- scope: {title}",
        f"- episodes: {report.total_episodes}",
        f"- report_ready: {sum(1 for item in report.readiness if item.report_ready)}",
        f"- profile_eligible: {sum(1 for item in report.readiness if item.profile_eligible)}",
        f"- timespan_quant: {WEEK_QUANT}",
        "",
        "## Observations",
        f"- Evidence base: {report.profile_maturity.quantity} profile-eligible episodes.",
        f"- Coverage: {report.profile_maturity.coverage_percent}% of collected episodes are report-ready.",
        f"- Pattern diversity: {report.profile_maturity.diversity} distinct graph signatures.",
        f"- Freshness: latest episode is {report.profile_maturity.freshness}.",
        f"- Confidence band: {report.profile_maturity.confidence_band}.",
        "",
        "## Patterns",
    ]
    lines.extend(_top_lines(loop_counter(report), min_count, "Repeated loops"))
    lines.extend(
        _top_lines(
            outcome_counter(report, "short") + outcome_counter(report, "long"),
            min_count,
            "Behavior to outcome contours",
        )
    )
    lines.extend(["", "## Exceptions"])
    lines.extend(_fork_lines(report, min_count))
    lines.extend(_top_lines(_rare_loop_counter(report), 1, "Rare loops"))
    lines.extend(["", "## Changes"])
    lines.extend(_change_lines(report))
    lines.extend(["", "## Questions"])
    lines.extend(_question_lines(report))
    lines.extend(["", "## Insights"])
    lines.extend(_insight_lines(report, skipped))
    lines.extend(["", "## Gaps"])
    if not skipped:
        lines.extend(["- none", ""])
    else:
        lines.append(f"- not_graph_ready: {len(skipped)}")
        for item in sorted(skipped, key=lambda value: value.episode_id)[:12]:
            reasons = ", ".join(item.gap_reasons) or "unknown"
            lines.append(f"- {item.episode_id}: {reasons}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_cbt_profiles(
    episodes: list[Episode],
    output_dir: Path,
    *,
    min_count: int = 2,
    by_source: bool = False,
) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = [
        _write_profile(
            output_dir / "all.md",
            build_report(episodes),
            title="All Sources",
            min_count=min_count,
        )
    ]
    if by_source:
        for source, group in groupby(sorted(episodes, key=lambda item: item.source), key=lambda item: item.source):
            written.append(
                _write_profile(
                    output_dir / f"{safe_filename(source)}.md",
                    build_report(list(group)),
                    title=source,
                    min_count=min_count,
                )
            )
    return tuple(written)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write user-facing evidence-bound CBT domain reports."
    )
    parser.add_argument("--episode-dir", default="data/episodes")
    parser.add_argument("--output-dir", default="data/reports/cbt-profile")
    parser.add_argument("--by-source", action="store_true")
    parser.add_argument("--min-count", type=int, default=2)
    args = parser.parse_args()

    paths = write_cbt_profiles(
        load_episodes(Path(args.episode_dir)),
        Path(args.output_dir),
        min_count=args.min_count,
        by_source=args.by_source,
    )
    for path in paths:
        print(path.as_posix())


def _top_lines(counter, min_count: int, label: str) -> list[str]:
    items = [(signature, count) for signature, count in counter.most_common(5) if count >= min_count]
    if not items:
        return [f"- {label}: no repeated pattern yet."]
    lines = [f"- {label}:"]
    for signature, count in items:
        lines.append(f"  - {' -> '.join(signature)}: {count} episodes")
    return lines


def _fork_lines(report: GraphReport, min_count: int) -> list[str]:
    forks = []
    for context, behaviors in behavior_forks(report).items():
        if sum(behaviors.values()) >= min_count and len(behaviors) > 1:
            forks.append((context, behaviors))
    forks.sort(key=lambda item: (-sum(item[1].values()), item[0]))
    if not forks:
        return ["- No repeated behavioral forks yet."]
    lines = ["- Same context can lead to different behaviors:"]
    for (trigger, emotion), behaviors in forks[:5]:
        behavior_text = ", ".join(f"{name} ({count})" for name, count in behaviors.most_common())
        lines.append(f"  - {trigger} -> {emotion}: {behavior_text}")
    return lines


def _change_lines(report: GraphReport) -> list[str]:
    novelty = novelty_counter(report)
    stability = stability_counter(report)
    lines = [f"- Temporal grouping uses fixed {WEEK_QUANT} buckets."]
    if novelty:
        newest = ", ".join(" -> ".join(item) for item, _count in novelty.most_common(3))
        lines.append(f"- New in latest week: {newest}.")
    else:
        lines.append("- New in latest week: none detected.")
    if stability:
        stable = ", ".join(" -> ".join(item) for item, _count in stability.most_common(3))
        lines.append(f"- Stable across weeks: {stable}.")
    else:
        lines.append("- Stable across weeks: not enough repeated weekly evidence yet.")
    return lines


def _question_lines(report: GraphReport) -> list[str]:
    loops = loop_counter(report)
    outcomes = outcome_counter(report, "long")
    questions = []
    if loops:
        top_loop = " -> ".join(loops.most_common(1)[0][0])
        questions.append(f"- When `{top_loop}` appears, what usually changes the next action?")
    if outcomes:
        top_outcome = " -> ".join(outcomes.most_common(1)[0][0])
        questions.append(f"- What makes `{top_outcome}` more or less likely?")
    if not questions:
        questions.append("- Which episode should be captured next to make patterns clearer?")
    return questions


def _insight_lines(report: GraphReport, skipped) -> list[str]:
    lines = []
    if report.profile_maturity.quantity:
        lines.append(
            "- The report is evidence-bound: it summarizes repeated episode patterns, not stable traits or diagnoses."
        )
    if report.profile_maturity.recurrence == "stable":
        lines.append("- Some patterns recur enough to treat them as working hypotheses.")
    else:
        lines.append("- Most patterns should be treated as emerging hypotheses.")
    if skipped:
        lines.append("- Some episodes are excluded from profile claims until graph-ready.")
    return lines


def _rare_loop_counter(report: GraphReport) -> Counter[tuple[str, ...]]:
    return Counter({loop: count for loop, count in loop_counter(report).items() if count == 1})


def _write_profile(path: Path, report: GraphReport, *, title: str, min_count: int) -> Path:
    path.write_text(
        render_cbt_profile(report, title=title, min_count=min_count),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    main()

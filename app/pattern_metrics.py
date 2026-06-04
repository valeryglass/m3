from __future__ import annotations

import re
from collections import Counter, defaultdict

from app.graph_report import EpisodeSignature, GraphReport


WEEK_QUANT = "1week"


def loop_counter(report: GraphReport) -> Counter[tuple[str, str, str]]:
    counter: Counter[tuple[str, str, str]] = Counter()
    for sig in report.graph_ready:
        for trigger in sig.triggers:
            for emotion in sig.emotions:
                for behavior in sig.behaviors:
                    counter[(trigger, emotion, behavior)] += 1
    return counter


def novelty_counter(report: GraphReport) -> Counter[tuple[str, ...]]:
    weeks = weekly_loop_sets(report)
    if not weeks:
        return Counter()
    ordered = sorted(weeks)
    previous = (
        set().union(*(weeks[week] for week in ordered[:-1]))
        if len(ordered) > 1
        else set()
    )
    return Counter({signature: 1 for signature in weeks[ordered[-1]] - previous})


def stability_counter(report: GraphReport) -> Counter[tuple[str, ...]]:
    by_loop: defaultdict[tuple[str, ...], set[str]] = defaultdict(set)
    for sig in report.graph_ready:
        week = week_key(sig.episode_id, report)
        for loop in loops_for_signature(sig):
            by_loop[loop].add(week)
    return Counter(
        {loop: len(weeks) for loop, weeks in by_loop.items() if len(weeks) > 1}
    )


def rarity_counter(report: GraphReport) -> Counter[tuple[str, ...]]:
    return Counter(
        {loop: count for loop, count in loop_counter(report).items() if count == 1}
    )


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
        if (
            count == 1
            and triggers[trigger] >= 2
            and emotions[emotion] >= 2
            and behaviors[behavior] >= 2
        ):
            surprising[loop] = 1
    return surprising


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


def loops_for_signature(sig: EpisodeSignature) -> set[tuple[str, str, str]]:
    return {
        (trigger, emotion, behavior)
        for trigger in sig.triggers
        for emotion in sig.emotions
        for behavior in sig.behaviors
    }


def safe_filename(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return name or "unknown"

from __future__ import annotations

import re
from collections import Counter, defaultdict

from app.graph_report import EpisodeSignature, GraphReport


WEEK_QUANT = "1week"


def loop_counter(report: GraphReport) -> Counter[tuple[str, str, str]]:
    return Counter(
        {
            loop: len(episode_ids)
            for loop, episode_ids in loop_episode_ids(report).items()
        }
    )


def loop_episode_ids(
    report: GraphReport,
) -> dict[tuple[str, str, str], frozenset[str]]:
    support: defaultdict[tuple[str, str, str], set[str]] = defaultdict(set)
    for sig in report.graph_ready:
        for loop in loops_for_signature(sig):
            support[loop].add(sig.episode_id)
    return {loop: frozenset(episode_ids) for loop, episode_ids in support.items()}


def trigger_counter(report: GraphReport) -> Counter[str]:
    return Counter(
        {
            trigger: len(episode_ids)
            for trigger, episode_ids in trigger_episode_ids(report).items()
        }
    )


def trigger_episode_ids(report: GraphReport) -> dict[str, frozenset[str]]:
    support: defaultdict[str, set[str]] = defaultdict(set)
    for sig in report.graph_ready:
        for trigger in sig.triggers:
            support[trigger].add(sig.episode_id)
    return {
        trigger: frozenset(episode_ids) for trigger, episode_ids in support.items()
    }


def behavior_forks(report: GraphReport) -> dict[tuple[str, str], Counter[str]]:
    return {
        base: Counter(
            {
                behavior: len(episode_ids)
                for behavior, episode_ids in behaviors.items()
            }
        )
        for base, behaviors in behavior_fork_episode_ids(report).items()
    }


def behavior_fork_episode_ids(
    report: GraphReport,
) -> dict[tuple[str, str], dict[str, frozenset[str]]]:
    support: defaultdict[
        tuple[str, str], defaultdict[str, set[str]]
    ] = defaultdict(lambda: defaultdict(set))
    for sig in report.graph_ready:
        for trigger in sig.triggers:
            for emotion in sig.emotions:
                for behavior in sig.behaviors:
                    support[(trigger, emotion)][behavior].add(sig.episode_id)
    return {
        base: {
            behavior: frozenset(episode_ids)
            for behavior, episode_ids in behaviors.items()
        }
        for base, behaviors in support.items()
    }


def outcome_episode_ids(
    report: GraphReport,
) -> dict[tuple[str, str, str], frozenset[str]]:
    support: defaultdict[tuple[str, str, str], set[str]] = defaultdict(set)
    for sig in report.graph_ready:
        for behavior in sig.behaviors:
            for horizon, outcomes in (
                ("short_term", sig.short_outcomes),
                ("long_term", sig.long_outcomes),
            ):
                for outcome in outcomes:
                    support[(behavior, horizon, outcome)].add(sig.episode_id)
    return {
        pattern: frozenset(episode_ids) for pattern, episode_ids in support.items()
    }


def outcome_pattern_counter(report: GraphReport) -> Counter[tuple[str, str]]:
    support: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for (behavior, _horizon, outcome), episode_ids in outcome_episode_ids(
        report
    ).items():
        support[(behavior, outcome)].update(episode_ids)
    return Counter(
        {
            pattern: len(episode_ids)
            for pattern, episode_ids in support.items()
        }
    )


def top_loop(report: GraphReport) -> tuple[tuple[str, str, str] | None, int]:
    items = sorted_counter_items(loop_counter(report))
    return items[0] if items else (None, 0)


def sorted_counter_items(counter) -> list[tuple]:
    return sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))


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

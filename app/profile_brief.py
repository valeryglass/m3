from __future__ import annotations

import argparse
import re
from itertools import groupby
from pathlib import Path

from app.graph_report import (
    GraphReport,
    build_report,
    load_episodes,
)
from app.schemas.episode import Episode


def render_profile_brief(
    report: GraphReport,
    *,
    title: str = "All Sources",
    min_count: int = 2,
) -> str:
    skipped = tuple(item for item in report.readiness if not item.graph_ready)
    lines = [
        "# Derived CBT Pattern Brief",
        "",
        f"- scope: {title}",
        f"- episodes: {report.total_episodes}",
        f"- report_ready: {sum(1 for item in report.readiness if item.report_ready)}",
        f"- profile_eligible: {sum(1 for item in report.readiness if item.profile_eligible)}",
        "",
        "## Profile Maturity",
        f"- quantity: {report.profile_maturity.quantity}",
        f"- diversity: {report.profile_maturity.diversity}",
        f"- recurrence: {report.profile_maturity.recurrence}",
        f"- stability: {report.profile_maturity.stability_percent}%",
        f"- coverage: {report.profile_maturity.coverage_percent}%",
        f"- freshness: {report.profile_maturity.freshness}",
        f"- confidence: {report.profile_maturity.confidence_band}",
        "",
    ]

    lines.extend(
        _render_section(
            "## Top Trigger Patterns",
            _counter_from_signatures(sig.triggers for sig in report.graph_ready),
            min_count,
        )
    )
    lines.extend(
        _render_section(
            "## Top Emotion Patterns",
            report.emotion_signatures,
            min_count,
        )
    )
    lines.extend(
        _render_section(
            "## Top Cognition Patterns",
            report.cognition_signatures,
            min_count,
        )
    )
    lines.extend(
        _render_section(
            "## Top Behavior Patterns",
            report.behavior_signatures,
            min_count,
        )
    )
    lines.extend(
        _render_section(
            "## Top Pairings",
            report.trigger_emotion_signatures
            + report.cognition_behavior_signatures
            + report.emotion_behavior_signatures,
            min_count,
            separator=" -> ",
        )
    )

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


def write_profile_briefs(
    episodes: list[Episode],
    output_dir: Path,
    *,
    min_count: int = 2,
    by_source: bool = False,
) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = [
        _write_brief(
            output_dir / "all.md",
            build_report(episodes),
            title="All Sources",
            min_count=min_count,
        )
    ]

    if by_source:
        grouped = groupby(
            sorted(episodes, key=lambda item: item.source),
            key=lambda item: item.source,
        )
        for source, group in grouped:
            written.append(
                _write_brief(
                    output_dir / f"{_safe_filename(source)}.md",
                    build_report(list(group)),
                    title=source,
                    min_count=min_count,
                )
            )

    return tuple(written)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write evidence-bound CBT profile brief reports for episode JSON files."
    )
    parser.add_argument(
        "--episode-dir",
        default="data/episodes",
        help="Directory containing episode-*.json files.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/reports/profile",
        help="Directory for Markdown profile brief files.",
    )
    parser.add_argument(
        "--by-source",
        action="store_true",
        help="Also create one profile brief per episode source.",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=2,
        help="Minimum count to show in repeated pattern sections.",
    )
    args = parser.parse_args()

    paths = write_profile_briefs(
        load_episodes(Path(args.episode_dir)),
        Path(args.output_dir),
        min_count=args.min_count,
        by_source=args.by_source,
    )
    for path in paths:
        print(path.as_posix())


def _counter_from_signatures(signatures):
    from collections import Counter

    return Counter(tuple(signature) for signature in signatures if signature)


def _render_section(
    title: str,
    counter,
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


def _write_brief(
    path: Path,
    report: GraphReport,
    *,
    title: str,
    min_count: int,
) -> Path:
    path.write_text(
        render_profile_brief(report, title=title, min_count=min_count),
        encoding="utf-8",
    )
    return path


def _join_values(values: tuple[str, ...], *, separator: str = " + ") -> str:
    return separator.join(values) if values else "none"


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return name or "unknown"


if __name__ == "__main__":
    main()

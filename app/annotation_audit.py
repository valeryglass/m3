from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.analytics_loader import (
    AnnotationCoverage,
    annotation_coverage,
    require_full_coverage,
)
from app.graph_report import load_episodes
from app.readiness import classify_episode_readiness
from app.schemas.episode import Episode


DEFAULT_EPISODE_DIR = Path("data/episodes")
ANNOTATION_FIELDS = (
    "trigger_annotations",
    "actor_annotations",
    "cognition_annotations",
    "emotion_annotations",
    "behavior_annotations",
    "outcome_annotations",
)


@dataclass(frozen=True)
class AuditSummary:
    total: int = 0
    observed_count: int = 0
    annotation_row_count: int = 0
    annotated_count: int = 0
    pending_count: int = 0
    pending_episode_ids: tuple[str, ...] = field(default_factory=tuple)
    coverage: str = "full"
    valid: int = 0
    invalid: int = 0
    empty_derived: int = 0
    with_nodes: int = 0
    with_annotations: int = 0
    with_relations: int = 0
    observed_ready: int = 0
    annotation_ready: int = 0
    graph_ready: int = 0
    report_ready: int = 0
    payload_eligible: int = 0
    gap_reasons: dict[str, int] = field(default_factory=dict)
    nodes_total: int = 0
    trigger_annotations_total: int = 0
    actor_annotations_total: int = 0
    cognition_annotations_total: int = 0
    emotion_annotations_total: int = 0
    behavior_annotations_total: int = 0
    outcome_annotations_total: int = 0
    relations_total: int = 0
    invalid_files: tuple[str, ...] = field(default_factory=tuple)


def audit_episode_dir(
    episode_dir: Path = DEFAULT_EPISODE_DIR,
    *,
    annotation_run_dir: Path | None = None,
    annotation_run_root: Path | None = None,
    require_full: bool = False,
) -> AuditSummary:
    paths = _episode_paths(episode_dir)
    valid_raw_episodes, invalid_files = _load_valid_raw_episodes(paths)
    if invalid_files:
        return audit_episodes(
            valid_raw_episodes,
            total=len(paths),
            invalid_files=tuple(invalid_files),
        )
    coverage = annotation_coverage(
        episode_dir,
        annotation_run_dir=annotation_run_dir,
        annotation_run_root=annotation_run_root,
    )
    if require_full:
        require_full_coverage(coverage)
    return audit_episodes(
        load_episodes(
            episode_dir,
            annotation_run_dir=annotation_run_dir,
            annotation_run_root=annotation_run_root,
        ),
        coverage=coverage,
    )


def audit_episodes(
    episodes: list[Episode],
    *,
    total: int | None = None,
    invalid_files: tuple[str, ...] = (),
    coverage: AnnotationCoverage | None = None,
) -> AuditSummary:
    empty_derived = with_nodes = with_annotations = with_relations = 0
    observed_ready = annotation_ready = graph_ready = report_ready = payload_eligible = 0
    gap_reasons: dict[str, int] = {}
    totals = {
        "nodes_total": 0,
        "trigger_annotations_total": 0,
        "actor_annotations_total": 0,
        "cognition_annotations_total": 0,
        "emotion_annotations_total": 0,
        "behavior_annotations_total": 0,
        "outcome_annotations_total": 0,
        "relations_total": 0,
    }

    if coverage is None:
        observed_count = len(episodes) if total is None else total - len(invalid_files)
        coverage = AnnotationCoverage(
            observed_count=observed_count,
            annotation_row_count=0,
            annotated_count=observed_count,
            pending_count=0,
            pending_episode_ids=(),
            coverage="full",
        )

    for episode in episodes:
        derived = episode.derived
        annotations = [getattr(derived, field) for field in ANNOTATION_FIELDS]
        if not derived.nodes and not any(annotations) and not derived.relations:
            empty_derived += 1
        if derived.nodes:
            with_nodes += 1
        if any(annotations):
            with_annotations += 1
        if derived.relations:
            with_relations += 1

        readiness = classify_episode_readiness(episode)
        if readiness.observed_ready:
            observed_ready += 1
        if readiness.annotation_ready:
            annotation_ready += 1
        if readiness.graph_ready:
            graph_ready += 1
        if readiness.report_ready:
            report_ready += 1
        if readiness.payload_eligible:
            payload_eligible += 1
        for reason in readiness.gap_reasons:
            gap_reasons[reason] = gap_reasons.get(reason, 0) + 1

        totals["nodes_total"] += len(derived.nodes)
        totals["trigger_annotations_total"] += len(derived.trigger_annotations)
        totals["actor_annotations_total"] += len(derived.actor_annotations)
        totals["cognition_annotations_total"] += len(derived.cognition_annotations)
        totals["emotion_annotations_total"] += len(derived.emotion_annotations)
        totals["behavior_annotations_total"] += len(derived.behavior_annotations)
        totals["outcome_annotations_total"] += len(derived.outcome_annotations)
        totals["relations_total"] += len(derived.relations)

    return AuditSummary(
        total=len(episodes) if total is None else total,
        observed_count=coverage.observed_count,
        annotation_row_count=coverage.annotation_row_count,
        annotated_count=coverage.annotated_count,
        pending_count=coverage.pending_count,
        pending_episode_ids=coverage.pending_episode_ids,
        coverage=coverage.coverage,
        valid=len(episodes),
        invalid=len(invalid_files),
        empty_derived=empty_derived,
        with_nodes=with_nodes,
        with_annotations=with_annotations,
        with_relations=with_relations,
        observed_ready=observed_ready,
        annotation_ready=annotation_ready,
        graph_ready=graph_ready,
        report_ready=report_ready,
        payload_eligible=payload_eligible,
        gap_reasons=gap_reasons,
        invalid_files=invalid_files,
        **totals,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only audit for observed episodes plus selected annotation-runs."
    )
    parser.add_argument("--episode-dir", default=str(DEFAULT_EPISODE_DIR))
    parser.add_argument("--annotation-run-dir")
    parser.add_argument("--annotation-run-root")
    parser.add_argument(
        "--require-full-coverage",
        action="store_true",
        help="Fail when the selected annotation-run has missing episode rows.",
    )
    args = parser.parse_args()

    summary = audit_episode_dir(
        Path(args.episode_dir),
        annotation_run_dir=Path(args.annotation_run_dir)
        if args.annotation_run_dir
        else None,
        annotation_run_root=Path(args.annotation_run_root)
        if args.annotation_run_root
        else None,
        require_full=args.require_full_coverage,
    )
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))


def _load_valid_raw_episodes(paths: list[Path]) -> tuple[list[Episode], list[str]]:
    valid: list[Episode] = []
    invalid_files: list[str] = []
    for path in paths:
        try:
            valid.append(Episode.model_validate(_read_json(path)))
        except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            invalid_files.append(f"{path.name}: {type(exc).__name__}")
    return valid, invalid_files


def _episode_paths(episode_dir: Path) -> list[Path]:
    return sorted(episode_dir.glob("episode-*.json"))


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON file must contain an object")
    return data


if __name__ == "__main__":
    main()

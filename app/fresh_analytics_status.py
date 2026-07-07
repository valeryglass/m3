from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

from app.analytics_loader import selected_annotation_run
from app.annotation_audit import audit_episode_dir
from app.annotation_producer import AnnotationProducerSummary, produce_annotation_run
from app.journal import DEFAULT_JOURNAL_LOG, JournalLog, journal_event, record_journal_event

RECOMMENDATION_NO_OP_EMPTY = "no_op_empty"
RECOMMENDATION_NO_OP_FULL_COVERAGE = "no_op_full_coverage"
RECOMMENDATION_MISSING_ONLY = "missing_only"
RECOMMENDATION_FULL_SNAPSHOT = "full_snapshot"
RECOMMENDATION_BLOCKED = "blocked"


def build_status(
    episode_dir: Path,
    annotation_run_root: Path,
    *,
    annotation_run_dir: Path | None = None,
    source: str | None = None,
    journal_log: JournalLog | Path | None = None,
) -> dict[str, Any]:
    try:
        status = _build_status(
            episode_dir,
            annotation_run_root,
            annotation_run_dir=annotation_run_dir,
            source=source,
        )
    except Exception as exc:
        status = {
            "recommendation": RECOMMENDATION_BLOCKED,
            "recommended_command": "",
            "blocker": str(exc),
            "selected_annotation_run_path": None,
            "selected_annotation_run_id": None,
            "observed_episode_count": 0,
            "annotation_row_count": 0,
            "coverage": "blocked",
            "pending_count": 0,
            "pending_episode_ids": [],
            "readiness": {},
            "gap_reasons": {},
            "dry_run": None,
        }
        _record_status_journal(journal_log, status, episode_dir, annotation_run_root)
        return status
    _record_status_journal(journal_log, status, episode_dir, annotation_run_root)
    return status


def _build_status(
    episode_dir: Path,
    annotation_run_root: Path,
    *,
    annotation_run_dir: Path | None,
    source: str | None,
) -> dict[str, Any]:
    selected_run = selected_annotation_run(
        episode_dir,
        annotation_run_dir,
        annotation_run_root,
    )
    selected_run_dir = selected_run.path if selected_run is not None else None
    dry_run = produce_annotation_run(
        episode_dir,
        annotation_run_root,
        source=source,
        only_missing=selected_run is not None,
        annotation_run_dir=selected_run_dir,
        write=False,
    )
    audit = audit_episode_dir(
        episode_dir,
        annotation_run_dir=selected_run_dir,
        annotation_run_root=annotation_run_root,
    )
    recommendation = _recommendation(dry_run, selected_run_dir)
    blocker = (
        "fresh analytics status cannot produce full annotation coverage"
        if recommendation == RECOMMENDATION_BLOCKED
        else None
    )
    return {
        "recommendation": recommendation,
        "recommended_command": _recommended_command(
            recommendation,
            episode_dir=episode_dir,
            annotation_run_root=annotation_run_root,
            annotation_run_dir=selected_run_dir,
            source=source,
        ),
        "blocker": blocker,
        "selected_annotation_run_path": (
            selected_run_dir.as_posix() if selected_run_dir is not None else None
        ),
        "selected_annotation_run_id": (
            selected_run.manifest.annotation_run_id if selected_run is not None else None
        ),
        "observed_episode_count": audit.observed_count,
        "annotation_row_count": audit.annotation_row_count,
        "coverage": audit.coverage,
        "pending_count": audit.pending_count,
        "pending_episode_ids": list(audit.pending_episode_ids),
        "readiness": {
            "observed_ready": audit.observed_ready,
            "annotation_ready": audit.annotation_ready,
            "graph_ready": audit.graph_ready,
            "report_ready": audit.report_ready,
            "payload_eligible": audit.payload_eligible,
        },
        "gap_reasons": dict(sorted(audit.gap_reasons.items())),
        "dry_run": dry_run.as_dict(),
    }


def _recommendation(
    dry_run: AnnotationProducerSummary,
    selected_run_dir: Path | None,
) -> str:
    if dry_run.episode_count == 0:
        return RECOMMENDATION_NO_OP_EMPTY
    if selected_run_dir is None:
        return RECOMMENDATION_FULL_SNAPSHOT
    if dry_run.coverage_after != "full":
        return RECOMMENDATION_BLOCKED
    if dry_run.generated_count == 0 and dry_run.coverage_before == "full":
        return RECOMMENDATION_NO_OP_FULL_COVERAGE
    return RECOMMENDATION_MISSING_ONLY


def _recommended_command(
    recommendation: str,
    *,
    episode_dir: Path,
    annotation_run_root: Path,
    annotation_run_dir: Path | None,
    source: str | None,
) -> str:
    if recommendation == RECOMMENDATION_FULL_SNAPSHOT:
        return _make_command(
            "annotation-full",
            episode_dir=episode_dir,
            annotation_run_root=annotation_run_root,
            source=source,
        )
    if recommendation == RECOMMENDATION_MISSING_ONLY and annotation_run_dir is not None:
        return _make_command(
            "annotation-missing",
            episode_dir=episode_dir,
            annotation_run_root=annotation_run_root,
            annotation_run_dir=annotation_run_dir,
            source=source,
        )
    if (
        recommendation == RECOMMENDATION_NO_OP_FULL_COVERAGE
        and annotation_run_dir is not None
    ):
        return _make_command(
            "beta-analytics",
            episode_dir=episode_dir,
            annotation_run_dir=annotation_run_dir,
            source=source,
        )
    return ""


def _record_status_journal(
    journal_log: JournalLog | Path | None,
    status: dict[str, Any],
    episode_dir: Path,
    annotation_run_root: Path,
) -> None:
    recommendation = status["recommendation"]
    blocked = recommendation == RECOMMENDATION_BLOCKED
    dry_run = status.get("dry_run") or {}
    record_journal_event(
        journal_log,
        journal_event(
            component="fresh_analytics_status",
            event_type="fresh_analytics.status_checked",
            stage="blocked" if blocked else "checked",
            level="error" if blocked else "info",
            reason=status.get("blocker"),
            refs={
                "episode_dir": episode_dir.as_posix(),
                "annotation_run_root": annotation_run_root.as_posix(),
                "selected_annotation_run_path": status.get(
                    "selected_annotation_run_path"
                ),
            },
            counts={
                "observed_episode_count": status.get("observed_episode_count", 0),
                "annotation_row_count": status.get("annotation_row_count", 0),
                "pending_count": status.get("pending_count", 0),
                "dry_run_generated_count": dry_run.get("generated_count", 0),
            },
            details={
                "recommendation": recommendation,
                "coverage": status.get("coverage"),
                "selected_annotation_run_id": status.get(
                    "selected_annotation_run_id"
                ),
            },
        ),
    )


def _make_command(
    target: str,
    *,
    episode_dir: Path,
    annotation_run_root: Path | None = None,
    annotation_run_dir: Path | None = None,
    source: str | None = None,
) -> str:
    parts = ["make", target, f"EPISODE_DIR={_quote(episode_dir.as_posix())}"]
    if annotation_run_root is not None:
        parts.append(f"ANNOTATION_RUN_ROOT={_quote(annotation_run_root.as_posix())}")
    if annotation_run_dir is not None:
        parts.append(f"ANNOTATION_RUN_DIR={_quote(annotation_run_dir.as_posix())}")
    if source:
        parts.append(f"ANNOTATION_SOURCE={_quote(source)}")
    return " ".join(parts)


def _quote(value: str) -> str:
    return shlex.quote(value)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Recommend the next fresh analytics annotation-run action."
    )
    parser.add_argument("--episode-dir", type=Path, default=Path("data/episodes"))
    parser.add_argument(
        "--annotation-run-root", type=Path, default=Path("data/annotation-runs")
    )
    parser.add_argument("--annotation-run-dir", type=Path)
    parser.add_argument("--source")
    parser.add_argument("--journal-log", type=Path, default=DEFAULT_JOURNAL_LOG)
    args = parser.parse_args(argv)
    status = build_status(
        args.episode_dir,
        args.annotation_run_root,
        annotation_run_dir=args.annotation_run_dir,
        source=args.source,
        journal_log=args.journal_log,
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if status["recommendation"] == RECOMMENDATION_BLOCKED:
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()

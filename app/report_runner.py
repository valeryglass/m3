from __future__ import annotations

from typing import Any

from app.analytics_loader import (
    DEFAULT_ANNOTATION_RUN_ROOT,
    annotation_coverage,
    selected_annotation_run,
)
from app.analytics_refresh import inspect_analytics_freshness
from app.annotation_audit import audit_episode_dir
from app.config import Settings
from app.graph_report import build_report, load_episodes
from app.ux_analytics import load_user_records, render_markdown, summarize_events
from app.ux_events import UxEventLog


def build_graph_report_summary(settings: Settings) -> dict[str, Any]:
    configured_run_dir = getattr(settings, "annotation_run_dir", None)
    run_root = getattr(settings, "annotation_run_root", None) or DEFAULT_ANNOTATION_RUN_ROOT
    selected_run = selected_annotation_run(
        settings.episode_dir,
        annotation_run_dir=configured_run_dir,
        annotation_run_root=run_root,
    )
    selected_run_dir = selected_run.path if selected_run is not None else None
    freshness = inspect_analytics_freshness(
        settings.episode_dir,
        run_root,
        annotation_run_dir=configured_run_dir,
    )
    audit = audit_episode_dir(
        settings.episode_dir,
        annotation_run_dir=selected_run_dir,
        annotation_run_root=run_root,
    )
    episodes = load_episodes(
        settings.episode_dir,
        annotation_run_dir=selected_run_dir,
        annotation_run_root=run_root,
    )
    coverage = annotation_coverage(
        settings.episode_dir,
        annotation_run_dir=selected_run_dir,
        annotation_run_root=run_root,
    )
    report = build_report(episodes, coverage=coverage)

    return {
        "episodes": report.total_episodes,
        "observed_count": coverage.observed_count,
        "annotation_row_count": coverage.annotation_row_count,
        "annotated_count": coverage.annotated_count,
        "pending_count": coverage.pending_count,
        "coverage": coverage.coverage,
        "freshness": freshness.state,
        "selected_annotation_run_id": freshness.selected_run_id,
        "invalid": audit.invalid,
        "empty_derived": sum(
            1 for item in report.readiness if "empty_derived" in item.gap_reasons
        ),
        "annotation_ready": sum(1 for item in report.readiness if item.annotation_ready),
        "graph_ready": len(report.graph_ready),
        "report_ready": sum(1 for item in report.readiness if item.report_ready),
        "payload_eligible": sum(
            1 for item in report.readiness if item.payload_eligible
        ),
    }


def build_ux_report_text(settings: Settings) -> str:
    summary: dict[str, Any] = summarize_events(
        UxEventLog(settings.ux_event_log).read(),
        idle_after_sec=settings.ux_idle_after_sec,
        user_records=load_user_records(settings.userlist_path),
    )
    return render_markdown(summary)

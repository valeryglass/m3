from __future__ import annotations

from pathlib import Path
from typing import Any

from app.annotation_workflow import audit_episode_dir
from app.config import Settings
from app.graph_report import build_report, load_episodes, write_markdown_reports
from app.psy_payload import write_psy_payload
from app.ux_analytics import load_user_records, summarize_events, write_reports
from app.ux_events import UxEventLog


def profile_report_path(settings: Settings, chat_id: int) -> Path:
    return settings.psy_payload_dir / f"telegram-chat-{chat_id}.md"


def regenerate_graph_and_payload_reports(settings: Settings) -> dict[str, int | str]:
    audit = audit_episode_dir(settings.episode_dir)
    episodes = load_episodes(settings.episode_dir)
    report = build_report(episodes)
    write_markdown_reports(
        episodes,
        settings.graph_report_dir,
        min_count=settings.report_min_count,
        by_source=True,
    )
    write_psy_payload(
        episodes,
        settings.psy_payload_dir,
        min_count=settings.report_min_count,
        by_source=True,
    )

    return {
        "episodes": report.total_episodes,
        "invalid": audit.invalid,
        "empty_derived": audit.empty_derived,
        "graph_ready": len(report.graph_ready),
        "report_ready": sum(1 for item in report.readiness if item.report_ready),
        "payload_eligible": sum(
            1 for item in report.readiness if item.payload_eligible
        ),
        "graph_path": (settings.graph_report_dir / "all.md").as_posix(),
        "payload_path": (settings.psy_payload_dir / "all.md").as_posix(),
    }


def regenerate_ux_report(settings: Settings) -> tuple[Path, Path]:
    summary: dict[str, Any] = summarize_events(
        UxEventLog(settings.ux_event_log).read(),
        idle_after_sec=settings.ux_idle_after_sec,
        user_records=load_user_records(settings.userlist_path),
    )
    return write_reports(summary, settings.ux_report_dir)

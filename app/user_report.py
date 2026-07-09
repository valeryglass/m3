from __future__ import annotations

from dataclasses import dataclass

from app.graph_report import GraphReport
from app.insight_payload import InsightPayload, build_insight_payload
from app.report_view_model import (
    build_report_view_model,
    render_details_view,
    render_summary_view,
)


INTERNAL_TERMS = (
    "payload",
    "graph_ready",
    "profile_eligible",
    "annotation",
    "signature",
)


@dataclass(frozen=True)
class UserReport:
    summary_text: str
    details_text: str


def build_user_report(report: GraphReport) -> UserReport:
    payload = build_insight_payload(report)
    return UserReport(
        summary_text=render_summary_from_payload(payload),
        details_text=render_details_from_payload(payload),
    )


def render_summary(report: GraphReport) -> str:
    return render_summary_from_payload(build_insight_payload(report))


def render_details(report: GraphReport) -> str:
    return render_details_from_payload(build_insight_payload(report))


def render_summary_from_payload(payload: InsightPayload) -> str:
    return render_summary_view(build_report_view_model(payload))


def render_details_from_payload(payload: InsightPayload) -> str:
    return render_details_view(build_report_view_model(payload))

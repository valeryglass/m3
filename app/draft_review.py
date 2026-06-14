from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

from app.messages import FIELD_GUIDES, TARGETS


@dataclass(frozen=True)
class DraftReviewLine:
    field_name: str
    label: str
    value: str


def draft_review_lines(
    observed: dict[str, dict[str, Any]],
    targets: tuple[str, ...] = TARGETS,
) -> tuple[DraftReviewLine, ...]:
    return tuple(
        DraftReviewLine(
            field_name=target,
            label=str(FIELD_GUIDES[target]["label"]),
            value=_observed_value(observed, target),
        )
        for target in targets
    )


def render_draft_review_overview(
    observed: dict[str, dict[str, Any]],
    targets: tuple[str, ...] = TARGETS,
) -> str:
    return "\n".join(
        f"{line.label}: {escape(line.value)}"
        for line in draft_review_lines(observed, targets)
    )


def _observed_value(observed: dict[str, dict[str, Any]], target: str) -> str:
    item = observed.get(target, {})
    value = item.get("value") or item.get("source_quote") or ""
    return str(value)

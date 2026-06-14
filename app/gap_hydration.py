from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.episode_drafts import next_missing_draft_field


GAP_REASON_MISSING = "missing"


@dataclass(frozen=True)
class DraftGap:
    field_name: str
    reason: str = GAP_REASON_MISSING


def missing_draft_gaps(
    observed: Mapping[str, Mapping[str, Any]],
    fields: Sequence[str],
) -> tuple[DraftGap, ...]:
    return tuple(
        DraftGap(field_name)
        for field_name in fields
        if field_name not in observed
    )


def select_next_gap(
    observed: Mapping[str, Mapping[str, Any]],
    fields: Sequence[str],
    *,
    target_index: int | None = None,
    current_order_only: bool = True,
) -> DraftGap | None:
    gaps = missing_draft_gaps(observed, fields)
    if not gaps:
        return None

    if current_order_only and target_index is not None:
        current_field = _field_at_index(fields, target_index)
        if current_field is not None and current_field in {gap.field_name for gap in gaps}:
            return DraftGap(current_field)

    missing_field = next_missing_draft_field(observed, fields)
    if missing_field is None:
        return None
    return DraftGap(missing_field)


def _field_at_index(fields: Sequence[str], target_index: int) -> str | None:
    if target_index < 0 or target_index >= len(fields):
        return None
    return fields[target_index]

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


DRAFT_STATUS_PARTIAL = "partial"
DRAFT_STATUS_COMPLETE = "complete"
COMPLETE_TARGET = "complete"

ObservedDraft = Mapping[str, Mapping[str, Any]]


def completed_draft_field_count(
    observed: ObservedDraft,
    fields: Sequence[str],
) -> int:
    return sum(1 for field_name in fields if field_name in observed)


def next_missing_draft_field(
    observed: ObservedDraft,
    fields: Sequence[str],
) -> str | None:
    for field_name in fields:
        if field_name not in observed:
            return field_name
    return None


def draft_status(
    observed: ObservedDraft,
    fields: Sequence[str],
) -> str:
    if next_missing_draft_field(observed, fields) is None:
        return DRAFT_STATUS_COMPLETE
    return DRAFT_STATUS_PARTIAL


def is_draft_complete(
    observed: ObservedDraft,
    fields: Sequence[str],
) -> bool:
    return draft_status(observed, fields) == DRAFT_STATUS_COMPLETE


def next_draft_target(
    observed: ObservedDraft,
    fields: Sequence[str],
    target_index: int,
) -> str:
    if is_draft_complete(observed, fields):
        return COMPLETE_TARGET
    if target_index >= len(fields):
        return COMPLETE_TARGET
    return fields[target_index]

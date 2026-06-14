from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.input_funnels import InputArtifact, artifact_text


DRAFT_STATUS_PARTIAL = "partial"
DRAFT_STATUS_COMPLETE = "complete"
COMPLETE_TARGET = "complete"

ObservedDraft = Mapping[str, Mapping[str, Any]]
MutableObservedDraft = dict[str, dict[str, str]]
THREE_BLOCK_DEFAULT_FIELDS = ("situation", "automatic_thought", "behavior")


@dataclass(frozen=True)
class EpisodeDraft:
    observed: MutableObservedDraft = field(default_factory=dict)


def observed_text_field(value: str) -> dict[str, str]:
    return {"value": value, "source_quote": value}


def draft_from_text(
    text: str,
    *,
    field_name: str = "situation",
) -> EpisodeDraft:
    value = text.strip()
    if not value:
        return EpisodeDraft()
    return EpisodeDraft(observed={field_name: observed_text_field(value)})



def draft_from_three_blocks(
    happened: str,
    inside: str,
    response: str,
    *,
    field_names: Sequence[str] = THREE_BLOCK_DEFAULT_FIELDS,
) -> EpisodeDraft:
    if len(field_names) != 3:
        raise ValueError("three-block field mapping must contain exactly three fields")

    observed = {}
    for field_name, value in zip(field_names, (happened, inside, response)):
        stripped = value.strip()
        if stripped:
            observed[field_name] = observed_text_field(stripped)
    return EpisodeDraft(observed=observed)

def draft_from_input_artifact(
    artifact: InputArtifact,
    *,
    field_name: str = "situation",
) -> EpisodeDraft:
    return draft_from_text(artifact_text(artifact), field_name=field_name)


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

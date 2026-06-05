from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.annotation_runs import load_annotation_run
from app.derived_normalizer import empty_derived, normalize_episode
from app.schemas.episode import Episode


def load_analytics_episodes(
    episode_dir: Path,
    annotation_run_dir: Path | None = None,
) -> list[Episode]:
    records = [_read_json(path) for path in _episode_paths(episode_dir)]
    episode_ids = {_episode_id(record) for record in records}
    annotation_run = (
        load_annotation_run(annotation_run_dir, episode_ids=episode_ids)
        if annotation_run_dir is not None
        else None
    )

    episodes: list[Episode] = []
    for record in records:
        selected_derived = None
        if annotation_run is not None:
            selected_derived = annotation_run.derived_by_episode_id.get(
                _episode_id(record)
            )
        normalized = _episode_with_selected_derived(
            record,
            selected_derived,
            annotation_run_supplied=annotation_run is not None,
        )
        normalized, _ = normalize_episode(normalized)
        try:
            episodes.append(Episode.model_validate(normalized))
        except ValidationError as exc:
            raise ValueError(f"invalid analytics episode: {_episode_id(record)}") from exc
    return episodes


def _episode_with_selected_derived(
    record: dict[str, Any],
    selected_derived,
    *,
    annotation_run_supplied: bool,
) -> dict[str, Any]:
    normalized = deepcopy(record)
    normalized["id"] = _episode_id(record)
    normalized.pop("episode_id", None)
    normalized.pop("metadata", None)
    normalized.pop("current_derived", None)

    if selected_derived is not None:
        normalized["derived"] = selected_derived.model_dump(mode="json")
    elif annotation_run_supplied:
        normalized["derived"] = empty_derived()
    elif "derived" in record:
        normalized["derived"] = record["derived"]
    elif isinstance(record.get("current_derived"), dict):
        normalized["derived"] = record["current_derived"]
    else:
        normalized["derived"] = empty_derived()
    return normalized


def _episode_id(record: dict[str, Any]) -> str:
    value = record.get("id", record.get("episode_id"))
    if not isinstance(value, str) or not value:
        raise ValueError("episode id is required")
    return value


def _episode_paths(episode_dir: Path) -> list[Path]:
    return sorted(episode_dir.glob("episode-*.json"))


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"episode JSON must be an object: {path}")
    return data

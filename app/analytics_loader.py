from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.annotation_runs import (
    AnnotationRun,
    load_annotation_run,
    load_latest_annotation_run,
)
from app.derived_normalizer import empty_derived, normalize_episode
from app.schemas.episode import Episode


DEFAULT_ANNOTATION_RUN_ROOT = Path("data/annotation-runs")


@dataclass(frozen=True)
class AnnotationCoverage:
    observed_count: int = 0
    annotation_row_count: int = 0
    annotated_count: int = 0
    pending_count: int = 0
    pending_episode_ids: tuple[str, ...] = field(default_factory=tuple)
    coverage: str = "full"


def annotation_coverage(
    episode_dir: Path,
    annotation_run_dir: Path | None = None,
    annotation_run_root: Path | None = None,
) -> AnnotationCoverage:
    records = [_read_json(path) for path in _episode_paths(episode_dir)]
    episode_ids = {_episode_id(record) for record in records}
    return annotation_coverage_for_episode_ids(
        episode_ids,
        annotation_run_dir=annotation_run_dir,
        annotation_run_root=annotation_run_root,
    )


def annotation_coverage_for_episode_ids(
    episode_ids: set[str],
    *,
    annotation_run_dir: Path | None = None,
    annotation_run_root: Path | None = None,
    known_episode_ids: set[str] | None = None,
) -> AnnotationCoverage:
    annotation_run = _select_annotation_run(
        annotation_run_dir,
        annotation_run_root,
        episode_ids=known_episode_ids or episode_ids,
    )
    if annotation_run is None:
        return AnnotationCoverage(
            observed_count=len(episode_ids),
            annotation_row_count=0,
            annotated_count=len(episode_ids),
            pending_count=0,
            pending_episode_ids=(),
            coverage="full",
        )
    row_ids = set(annotation_run.derived_by_episode_id)
    annotated_ids = episode_ids & row_ids
    pending_ids = tuple(sorted(episode_ids - annotated_ids))
    return AnnotationCoverage(
        observed_count=len(episode_ids),
        annotation_row_count=len(row_ids),
        annotated_count=len(annotated_ids),
        pending_count=len(pending_ids),
        pending_episode_ids=pending_ids,
        coverage="full" if not pending_ids else "partial",
    )


def require_full_coverage(coverage: AnnotationCoverage) -> None:
    if coverage.pending_count:
        raise ValueError(
            "annotation coverage is partial: "
            f"{coverage.annotated_count}/{coverage.observed_count} annotated; "
            f"pending={coverage.pending_count}"
        )


def load_analytics_episodes(
    episode_dir: Path,
    annotation_run_dir: Path | None = None,
    annotation_run_root: Path | None = None,
) -> list[Episode]:
    records = [_read_json(path) for path in _episode_paths(episode_dir)]
    episode_ids = {_episode_id(record) for record in records}
    annotation_run = selected_annotation_run(
        episode_dir,
        annotation_run_dir,
        annotation_run_root,
        episode_ids=episode_ids,
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


def selected_annotation_run(
    episode_dir: Path,
    annotation_run_dir: Path | None = None,
    annotation_run_root: Path | None = None,
    *,
    episode_ids: set[str] | None = None,
) -> AnnotationRun | None:
    if episode_ids is None:
        records = [_read_json(path) for path in _episode_paths(episode_dir)]
        episode_ids = {_episode_id(record) for record in records}
    return _select_annotation_run(
        annotation_run_dir,
        annotation_run_root,
        episode_ids=episode_ids,
    )


def _select_annotation_run(
    annotation_run_dir: Path | None,
    annotation_run_root: Path | None,
    *,
    episode_ids: set[str],
) -> AnnotationRun | None:
    selected_dir = annotation_run_dir or _env_path("M3_ANNOTATION_RUN_DIR")
    if selected_dir is not None:
        return load_annotation_run(selected_dir, episode_ids=episode_ids)

    root = (
        annotation_run_root
        or _env_path("M3_ANNOTATION_RUN_ROOT")
        or DEFAULT_ANNOTATION_RUN_ROOT
    )
    return load_latest_annotation_run(root, episode_ids=episode_ids)


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


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value) if value else None

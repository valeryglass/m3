from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.schemas.annotation_run import AnnotationRunManifest, AnnotationRunRow
from app.schemas.episode import Derived


@dataclass(frozen=True)
class AnnotationRun:
    path: Path
    manifest: AnnotationRunManifest
    rows: tuple[AnnotationRunRow, ...]
    derived_by_episode_id: dict[str, Derived]


def load_annotation_run(
    run_dir: Path,
    *,
    episode_ids: set[str] | None = None,
) -> AnnotationRun:
    manifest = _load_manifest(run_dir / "manifest.json")
    rows = _load_rows(run_dir / "annotations.jsonl")
    derived_by_episode_id: dict[str, Derived] = {}

    for row in rows:
        if row.episode_id in derived_by_episode_id:
            raise ValueError(f"duplicate annotation row: {row.episode_id}")
        if episode_ids is not None and row.episode_id not in episode_ids:
            raise ValueError(
                f"annotation row references unknown episode: {row.episode_id}"
            )
        derived_by_episode_id[row.episode_id] = row.derived

    return AnnotationRun(
        path=run_dir,
        manifest=manifest,
        rows=tuple(rows),
        derived_by_episode_id=derived_by_episode_id,
    )


def load_latest_annotation_run(
    run_root: Path,
    *,
    episode_ids: set[str] | None = None,
) -> AnnotationRun | None:
    if not run_root.exists():
        return None

    for run_dir in sorted(run_root.glob("run-*"), reverse=True):
        if not run_dir.is_dir():
            continue
        try:
            return load_annotation_run(run_dir, episode_ids=episode_ids)
        except ValueError:
            continue
    return None


def _load_manifest(path: Path) -> AnnotationRunManifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AnnotationRunManifest.model_validate(data)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid annotation run manifest: {path}") from exc


def _load_rows(path: Path) -> list[AnnotationRunRow]:
    rows: list[AnnotationRunRow] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"invalid annotation run rows: {path}") from exc

    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            rows.append(AnnotationRunRow.model_validate(data))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"invalid annotation run row {path}:{line_no}") from exc
    return rows

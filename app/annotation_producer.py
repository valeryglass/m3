from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.analytics_loader import selected_annotation_run
from app.derived_normalizer import normalize_episode
from app.episode_annotator import annotate_episode
from app.schemas.annotation_run import (
    AnnotationProducerProvenance,
    AnnotationRunManifest,
    AnnotationRunRow,
)
from app.schemas.episode import Episode

SCHEMA_VERSION = "episode-v1"
TAXONOMY_VERSION = "graph-v1"
PROMPT_VERSION = "deterministic-observed-v1"
COMPOSED_PROMPT_VERSION = "composed-snapshot-v1"
PRODUCER_NAME = "app.annotation_producer"
PRODUCER_STRATEGY = "deterministic_observed"


@dataclass(frozen=True)
class AnnotationProducerSummary:
    dry_run: bool
    episode_count: int
    scanned_count: int
    skipped_existing_count: int
    row_count: int
    run_dir: str
    run_id: str
    source: str | None
    annotated_before: int
    annotated_after: int
    pending_before: int
    pending_after: int
    coverage_before: str
    coverage_after: str
    carried_forward_count: int
    generated_count: int
    final_snapshot_count: int
    snapshot_written: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "episode_count": self.episode_count,
            "scanned_count": self.scanned_count,
            "skipped_existing_count": self.skipped_existing_count,
            "row_count": self.row_count,
            "run_dir": self.run_dir,
            "run_id": self.run_id,
            "source": self.source,
            "annotated_before": self.annotated_before,
            "annotated_after": self.annotated_after,
            "pending_before": self.pending_before,
            "pending_after": self.pending_after,
            "coverage_before": self.coverage_before,
            "coverage_after": self.coverage_after,
            "carried_forward_count": self.carried_forward_count,
            "generated_count": self.generated_count,
            "final_snapshot_count": self.final_snapshot_count,
            "snapshot_written": self.snapshot_written,
        }


def produce_annotation_run(
    episode_dir: Path,
    output_root: Path,
    *,
    run_id: str | None = None,
    source: str | None = None,
    only_missing: bool = False,
    annotation_run_dir: Path | None = None,
    annotation_run_root: Path | None = None,
    write: bool = False,
    timestamp: str | None = None,
) -> AnnotationProducerSummary:
    created_at = _created_at(timestamp)
    selected_run_id = run_id or f"run-{created_at.strftime('%Y%m%d-%H%M%S')}-deterministic"
    run_dir = output_root / selected_run_id
    records = _read_episode_records(episode_dir)
    all_episode_ids = {_episode_id(record) for record in records}
    selected_run = selected_annotation_run(
        episode_dir,
        annotation_run_dir,
        annotation_run_root or output_root,
        episode_ids=all_episode_ids,
    )
    existing_ids = (
        set(selected_run.derived_by_episode_id) if selected_run is not None else set()
    )
    source_episode_ids = {
        episode.id for episode in _episodes_matching_source(records, source)
    }
    before_ids = source_episode_ids & existing_ids
    skipped_ids = before_ids if only_missing else set()

    episodes = _episodes_to_annotate(records, source=source, existing_ids=skipped_ids)
    generated_rows = tuple(
        AnnotationRunRow(episode_id=episode.id, derived=annotate_episode(episode))
        for episode in episodes
    )
    carried_rows = (
        tuple(selected_run.rows)
        if only_missing and selected_run is not None
        else ()
    )
    rows = _snapshot_rows(
        carried_rows,
        generated_rows,
        known_episode_ids=all_episode_ids,
    )
    if only_missing and set(row.episode_id for row in rows) != all_episode_ids:
        missing_ids = sorted(all_episode_ids - {row.episode_id for row in rows})
        raise ValueError(
            "missing-only annotation snapshot is incomplete: "
            f"final={len(rows)}/{len(all_episode_ids)}; "
            f"missing={len(missing_ids)}"
        )
    snapshot_written = bool(write and (not only_missing or generated_rows))
    prompt_version = (
        COMPOSED_PROMPT_VERSION
        if carried_rows and generated_rows
        else (
            selected_run.manifest.prompt_version
            if carried_rows and selected_run is not None
            else PROMPT_VERSION
        )
    )
    manifest = AnnotationRunManifest(
        annotation_run_id=selected_run_id,
        schema_version=SCHEMA_VERSION,
        taxonomy_version=TAXONOMY_VERSION,
        prompt_version=prompt_version,
        created_at=created_at,
        source_episode_count=len(rows),
        carried_forward_count=len(carried_rows),
        generated_count=len(generated_rows),
        final_snapshot_count=len(rows),
        producer_provenance=AnnotationProducerProvenance(
            producer=PRODUCER_NAME,
            mode="missing_only_snapshot" if only_missing else "full_snapshot",
            generated_strategy=PRODUCER_STRATEGY,
            generated_prompt_version=PROMPT_VERSION,
            base_annotation_run_id=(
                selected_run.manifest.annotation_run_id
                if selected_run is not None and only_missing
                else None
            ),
            base_prompt_version=(
                selected_run.manifest.prompt_version
                if selected_run is not None and only_missing
                else None
            ),
        ),
    )

    if snapshot_written:
        _write_run(run_dir, manifest, rows)

    final_ids = {row.episode_id for row in rows}
    return AnnotationProducerSummary(
        dry_run=not write,
        episode_count=len(records),
        scanned_count=len(episodes),
        skipped_existing_count=len(skipped_ids),
        row_count=len(generated_rows),
        run_dir=run_dir.as_posix(),
        run_id=selected_run_id,
        source=source,
        annotated_before=len(before_ids),
        annotated_after=len(source_episode_ids & final_ids),
        pending_before=len(source_episode_ids - before_ids),
        pending_after=len(source_episode_ids - final_ids),
        coverage_before=_coverage_label(source_episode_ids, before_ids),
        coverage_after=_coverage_label(source_episode_ids, source_episode_ids & final_ids),
        carried_forward_count=len(carried_rows),
        generated_count=len(generated_rows),
        final_snapshot_count=len(rows),
        snapshot_written=snapshot_written,
    )


def _coverage_label(episode_ids: set[str], annotated_ids: set[str]) -> str:
    if not episode_ids:
        return "empty"
    return "full" if episode_ids <= annotated_ids else "partial"


def _snapshot_rows(
    carried_rows: tuple[AnnotationRunRow, ...],
    generated_rows: tuple[AnnotationRunRow, ...],
    *,
    known_episode_ids: set[str],
) -> tuple[AnnotationRunRow, ...]:
    rows_by_id: dict[str, AnnotationRunRow] = {}
    for row in (*carried_rows, *generated_rows):
        if row.episode_id not in known_episode_ids:
            raise ValueError(
                f"annotation row references unknown episode: {row.episode_id}"
            )
        if row.episode_id in rows_by_id:
            raise ValueError(f"duplicate annotation row: {row.episode_id}")
        rows_by_id[row.episode_id] = row
    return tuple(rows_by_id[episode_id] for episode_id in sorted(rows_by_id))


def _episodes_to_annotate(
    records: list[dict[str, Any]],
    *,
    source: str | None,
    existing_ids: set[str],
) -> tuple[Episode, ...]:
    episodes: list[Episode] = []
    seen: set[str] = set()
    for record in records:
        episode_id = _episode_id(record)
        if episode_id in seen:
            raise ValueError(f"duplicate episode id: {episode_id}")
        seen.add(episode_id)
        normalized, _ = normalize_episode(record)
        try:
            episode = Episode.model_validate(normalized)
        except ValidationError as exc:
            raise ValueError(f"invalid episode: {episode_id}") from exc
        if source is not None and episode.source != source:
            continue
        if episode.id in existing_ids:
            continue
        episodes.append(episode)
    return tuple(episodes)


def _episodes_matching_source(records: list[dict[str, Any]], source: str | None) -> tuple[Episode, ...]:
    return tuple(
        episode
        for episode in _episodes_to_annotate(records, source=source, existing_ids=set())
    )


def _write_run(
    run_dir: Path,
    manifest: AnnotationRunManifest,
    rows: tuple[AnnotationRunRow, ...],
) -> None:
    if run_dir.exists():
        raise ValueError(f"annotation run already exists: {run_dir}")
    run_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=run_dir.parent) as tmp_name:
        tmp_dir = Path(tmp_name)
        (tmp_dir / "manifest.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        (tmp_dir / "annotations.jsonl").write_text(
            "".join(
                json.dumps(row.model_dump(mode="json"), ensure_ascii=False) + "\n"
                for row in rows
            ),
            encoding="utf-8",
        )
        tmp_dir.rename(run_dir)


def _read_episode_records(episode_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(episode_dir.glob("episode-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"episode JSON must be an object: {path}")
        records.append(data)
    return records


def _episode_id(record: dict[str, Any]) -> str:
    value = record.get("id", record.get("episode_id"))
    if not isinstance(value, str) or not value:
        raise ValueError("episode id is required")
    return value


def _created_at(timestamp: str | None) -> datetime:
    if timestamp is None:
        return datetime.now(timezone.utc)
    return datetime.strptime(timestamp, "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Produce deterministic annotation-runs")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--episode-dir", type=Path, default=Path("data/episodes"))
    run.add_argument("--output-root", type=Path, default=Path("data/annotation-runs"))
    run.add_argument("--run-id")
    run.add_argument("--source")
    run.add_argument("--only-missing", action="store_true")
    run.add_argument("--annotation-run-dir", type=Path)
    run.add_argument("--annotation-run-root", type=Path)
    run.add_argument("--write", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--timestamp")
    args = parser.parse_args(argv)
    if args.command != "run":  # pragma: no cover - argparse prevents this
        raise ValueError(args.command)
    summary = produce_annotation_run(
        args.episode_dir,
        args.output_root,
        run_id=args.run_id,
        source=args.source,
        only_missing=args.only_missing,
        annotation_run_dir=args.annotation_run_dir,
        annotation_run_root=args.annotation_run_root,
        write=args.write and not args.dry_run,
        timestamp=args.timestamp,
    )
    print(json.dumps(summary.as_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()

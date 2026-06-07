from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.analytics_loader import load_analytics_episodes
from app.annotation_runs import load_annotation_run
from app.derived_normalizer import empty_derived, normalize_episode
from app.graph_report import build_report
from app.schemas.annotation_run import AnnotationRunManifest, AnnotationRunRow
from app.schemas.episode import Episode


SCHEMA_VERSION = "episode-v1"
TAXONOMY_VERSION = "graph-v1"
PROMPT_VERSION = "embedded-derived-baseline"


@dataclass(frozen=True)
class BaselineSummary:
    episode_count: int
    row_count: int
    empty_derived_count: int
    embedded_readiness: dict[str, int]
    generated_run_readiness: dict[str, int]
    readiness_matches: bool
    run_dir: str
    dry_run: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "episode_count": self.episode_count,
            "row_count": self.row_count,
            "empty_derived_count": self.empty_derived_count,
            "embedded_readiness": self.embedded_readiness,
            "generated_run_readiness": self.generated_run_readiness,
            "readiness_matches": self.readiness_matches,
            "run_dir": self.run_dir,
            "dry_run": self.dry_run,
        }


@dataclass(frozen=True)
class StripDerivedSummary:
    dry_run: bool
    episode_count: int
    annotation_row_count: int
    would_strip_count: int
    stripped_count: int
    backup_dir: str | None
    annotation_run_dir: str
    readiness_before: dict[str, int]
    readiness_after: dict[str, int]
    readiness_matches: bool
    readiness_policy: str
    allow_readiness_improvement: bool
    readiness_delta: dict[str, int]
    restore_hint: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "episode_count": self.episode_count,
            "annotation_row_count": self.annotation_row_count,
            "would_strip_count": self.would_strip_count,
            "stripped_count": self.stripped_count,
            "backup_dir": self.backup_dir,
            "annotation_run_dir": self.annotation_run_dir,
            "readiness_before": self.readiness_before,
            "readiness_after": self.readiness_after,
            "readiness_matches": self.readiness_matches,
            "readiness_policy": self.readiness_policy,
            "allow_readiness_improvement": self.allow_readiness_improvement,
            "readiness_delta": self.readiness_delta,
            "restore_hint": self.restore_hint,
        }


def build_baseline_run(
    episode_dir: Path,
    output_root: Path,
    *,
    write: bool = False,
    timestamp: str | None = None,
) -> BaselineSummary:
    created_at = _created_at(timestamp)
    run_id = f"run-{created_at.strftime('%Y%m%d-%H%M%S')}-baseline"
    run_dir = output_root / run_id
    records = _read_episode_records(episode_dir)
    rows = _baseline_rows(records)
    manifest = AnnotationRunManifest(
        annotation_run_id=run_id,
        schema_version=SCHEMA_VERSION,
        taxonomy_version=TAXONOMY_VERSION,
        prompt_version=PROMPT_VERSION,
        created_at=created_at,
        source_episode_count=len(records),
    )
    episode_ids = {_episode_id(record) for record in records}
    empty_count = sum(1 for row in rows if _is_empty_derived(row.derived.model_dump()))

    embedded_readiness = _readiness_counts(_episodes_from_embedded_records(records))
    generated_readiness = _validate_generated_run(
        episode_dir,
        run_dir,
        manifest,
        rows,
        episode_ids=episode_ids,
        write=write,
    )

    return BaselineSummary(
        episode_count=len(records),
        row_count=len(rows),
        empty_derived_count=empty_count,
        embedded_readiness=embedded_readiness,
        generated_run_readiness=generated_readiness,
        readiness_matches=embedded_readiness == generated_readiness,
        run_dir=run_dir.as_posix(),
        dry_run=not write,
    )


def strip_embedded_derived(
    episode_dir: Path,
    annotation_run_dir: Path,
    backup_root: Path,
    *,
    write: bool = False,
    timestamp: str | None = None,
    allow_readiness_improvement: bool = False,
) -> StripDerivedSummary:
    records_by_path = _read_episode_records_by_path(episode_dir)
    records = list(records_by_path.values())
    episode_ids = _episode_ids(records)
    annotation_run = load_annotation_run(annotation_run_dir, episode_ids=episode_ids)
    if len(annotation_run.rows) != len(records):
        raise ValueError(
            "annotation row count does not match active episode count: "
            f"{len(annotation_run.rows)} != {len(records)}"
        )

    embedded_readiness = _strip_readiness_counts(_episodes_from_embedded_records(records))
    selected_readiness = _strip_readiness_counts(
        load_analytics_episodes(episode_dir, annotation_run_dir=annotation_run_dir)
    )
    readiness_delta = _readiness_delta(embedded_readiness, selected_readiness)
    readiness_policy = (
        "allow_improvement" if allow_readiness_improvement else "exact_match"
    )
    _validate_readiness_policy(
        embedded_readiness,
        selected_readiness,
        allow_readiness_improvement=allow_readiness_improvement,
    )

    stripped_by_path = _stripped_records(records_by_path)
    would_strip_count = sum(
        1
        for record in records
        if "derived" in record or "current_derived" in record
    )
    stripped_readiness = _validate_stripped_records(
        stripped_by_path,
        annotation_run_dir,
        expected_readiness=selected_readiness,
    )
    backup_dir = (
        backup_root
        / f"episodes-derived-migration-{_created_at(timestamp).strftime('%Y%m%d-%H%M%S')}"
    )
    if backup_dir.exists():
        raise ValueError(f"backup directory already exists: {backup_dir}")

    if not write:
        return StripDerivedSummary(
            dry_run=True,
            episode_count=len(records),
            annotation_row_count=len(annotation_run.rows),
            would_strip_count=would_strip_count,
            stripped_count=0,
            backup_dir=None,
            annotation_run_dir=annotation_run_dir.as_posix(),
            readiness_before=selected_readiness,
            readiness_after=stripped_readiness,
            readiness_matches=selected_readiness == stripped_readiness,
            readiness_policy=readiness_policy,
            allow_readiness_improvement=allow_readiness_improvement,
            readiness_delta=readiness_delta,
            restore_hint=None,
        )

    _create_and_verify_backup(records_by_path, backup_dir)
    _replace_episode_files(stripped_by_path)
    post_write_readiness = _strip_readiness_counts(
        load_analytics_episodes(episode_dir, annotation_run_dir=annotation_run_dir)
    )
    if post_write_readiness != selected_readiness:
        raise ValueError("post-strip readiness does not match annotation-run baseline")
    check_observed_only(episode_dir)

    return StripDerivedSummary(
        dry_run=False,
        episode_count=len(records),
        annotation_row_count=len(annotation_run.rows),
        would_strip_count=would_strip_count,
        stripped_count=would_strip_count,
        backup_dir=backup_dir.as_posix(),
        annotation_run_dir=annotation_run_dir.as_posix(),
        readiness_before=selected_readiness,
        readiness_after=post_write_readiness,
        readiness_matches=selected_readiness == post_write_readiness,
        readiness_policy=readiness_policy,
        allow_readiness_improvement=allow_readiness_improvement,
        readiness_delta=readiness_delta,
        restore_hint=(
            f"Copy files from {backup_dir.as_posix()}/ back into "
            f"{episode_dir.as_posix()} to restore original embedded derived."
        ),
    )


def check_observed_only(episode_dir: Path) -> tuple[Path, ...]:
    bad: list[Path] = []
    for path in _episode_paths(episode_dir):
        data = _read_json(path)
        if "derived" in data or "current_derived" in data:
            bad.append(path)
    if bad:
        raise ValueError(
            "episode files still contain top-level derived fields: "
            + ", ".join(path.name for path in bad)
        )
    return tuple()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build annotation-run migration artifacts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser("baseline")
    baseline.add_argument("--episode-dir", default="data/episodes")
    baseline.add_argument("--output-root", default="data/annotation-runs")
    mode = baseline.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write", action="store_true")

    strip = subparsers.add_parser("strip-derived")
    strip.add_argument("--episode-dir", required=True)
    strip.add_argument("--annotation-run-dir", required=True)
    strip.add_argument("--backup-root", required=True)
    strip.add_argument("--allow-readiness-improvement", action="store_true")
    strip_mode = strip.add_mutually_exclusive_group(required=True)
    strip_mode.add_argument("--dry-run", action="store_true")
    strip_mode.add_argument("--write", action="store_true")

    observed_only = subparsers.add_parser("check-observed-only")
    observed_only.add_argument("--episode-dir", required=True)

    args = parser.parse_args()
    if args.command == "baseline":
        summary = build_baseline_run(
            Path(args.episode_dir),
            Path(args.output_root),
            write=args.write,
        )
        print(json.dumps(summary.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "strip-derived":
        summary = strip_embedded_derived(
            Path(args.episode_dir),
            Path(args.annotation_run_dir),
            Path(args.backup_root),
            write=args.write,
            allow_readiness_improvement=args.allow_readiness_improvement,
        )
        print(json.dumps(summary.as_dict(), ensure_ascii=False, indent=2))
    elif args.command == "check-observed-only":
        check_observed_only(Path(args.episode_dir))
        print(json.dumps({"observed_only": True}, ensure_ascii=False, indent=2))


def _validate_generated_run(
    episode_dir: Path,
    run_dir: Path,
    manifest: AnnotationRunManifest,
    rows: list[AnnotationRunRow],
    *,
    episode_ids: set[str],
    write: bool,
) -> dict[str, int]:
    if write:
        if run_dir.exists():
            raise ValueError(f"annotation run already exists: {run_dir}")
        _write_run(run_dir, manifest, rows)
        load_annotation_run(run_dir, episode_ids=episode_ids)
        return _readiness_counts(
            load_analytics_episodes(episode_dir, annotation_run_dir=run_dir)
        )

    with tempfile.TemporaryDirectory(prefix="m3-baseline-run-") as tmp:
        temp_run_dir = Path(tmp) / run_dir.name
        _write_run(temp_run_dir, manifest, rows)
        load_annotation_run(temp_run_dir, episode_ids=episode_ids)
        return _readiness_counts(
            load_analytics_episodes(episode_dir, annotation_run_dir=temp_run_dir)
        )


def _baseline_rows(records: list[dict[str, Any]]) -> list[AnnotationRunRow]:
    seen: set[str] = set()
    rows: list[AnnotationRunRow] = []
    for record in records:
        episode_id = _episode_id(record)
        if episode_id in seen:
            raise ValueError(f"duplicate episode id: {episode_id}")
        seen.add(episode_id)
        derived = _selected_derived(record)
        rows.append(
            AnnotationRunRow.model_validate(
                {
                    "episode_id": episode_id,
                    "derived": derived,
                }
            )
        )
    return sorted(rows, key=lambda row: row.episode_id)


def _selected_derived(record: dict[str, Any]) -> dict[str, Any]:
    selected = record.get("derived")
    if selected is None:
        selected = record.get("current_derived", empty_derived())
    if not isinstance(selected, dict):
        raise ValueError(f"derived must be an object: {_episode_id(record)}")

    normalized = {
        "id": _episode_id(record),
        "date": record.get("date"),
        "source": record.get("source"),
        "observed": record.get("observed"),
        "derived": selected,
    }
    normalized, _ = normalize_episode(normalized)
    try:
        episode = Episode.model_validate(normalized)
    except ValidationError as exc:
        raise ValueError(f"invalid episode derived: {_episode_id(record)}") from exc
    return episode.derived.model_dump(mode="json")


def _readiness_counts(episodes: list[Episode]) -> dict[str, int]:
    report = build_report(episodes)
    return {
        "episodes": report.total_episodes,
        "annotation_ready": sum(
            1 for item in report.readiness if item.annotation_ready
        ),
        "graph_ready": len(report.graph_ready),
        "report_ready": sum(1 for item in report.readiness if item.report_ready),
        "payload_eligible": sum(
            1 for item in report.readiness if item.payload_eligible
        ),
    }


def _strip_readiness_counts(episodes: list[Episode]) -> dict[str, int]:
    counts = _readiness_counts(episodes)
    return {
        "graph_ready": counts["graph_ready"],
        "report_ready": counts["report_ready"],
        "payload_eligible": counts["payload_eligible"],
    }


def _readiness_delta(
    embedded_readiness: dict[str, int],
    selected_readiness: dict[str, int],
) -> dict[str, int]:
    return {
        key: selected_readiness[key] - embedded_readiness[key]
        for key in ("graph_ready", "report_ready", "payload_eligible")
    }


def _validate_readiness_policy(
    embedded_readiness: dict[str, int],
    selected_readiness: dict[str, int],
    *,
    allow_readiness_improvement: bool,
) -> None:
    delta = _readiness_delta(embedded_readiness, selected_readiness)
    regressions = {key: value for key, value in delta.items() if value < 0}
    if regressions:
        raise ValueError(
            "annotation-run readiness regresses embedded baseline: "
            + json.dumps(regressions, sort_keys=True)
        )
    if not allow_readiness_improvement and any(value > 0 for value in delta.values()):
        raise ValueError(
            "annotation-run readiness improvement requires "
            "--allow-readiness-improvement"
        )
    if any(value != 0 for value in delta.values()) and not allow_readiness_improvement:
        raise ValueError("annotation-run readiness does not match embedded baseline")


def _episodes_from_embedded_records(records: list[dict[str, Any]]) -> list[Episode]:
    episodes: list[Episode] = []
    for record in records:
        normalized = {
            "id": _episode_id(record),
            "date": record.get("date"),
            "source": record.get("source"),
            "observed": record.get("observed"),
            "derived": _selected_derived(record),
        }
        normalized, _ = normalize_episode(normalized)
        try:
            episodes.append(Episode.model_validate(normalized))
        except ValidationError as exc:
            raise ValueError(f"invalid episode: {_episode_id(record)}") from exc
    return episodes


def _stripped_records(
    records_by_path: dict[Path, dict[str, Any]],
) -> dict[Path, dict[str, Any]]:
    stripped_by_path: dict[Path, dict[str, Any]] = {}
    for path, record in records_by_path.items():
        stripped = deepcopy(record)
        stripped.pop("derived", None)
        stripped.pop("current_derived", None)
        _verify_stripped_record(record, stripped, path)
        json.loads(json.dumps(stripped, ensure_ascii=False))
        stripped_by_path[path] = stripped
    return stripped_by_path


def _verify_stripped_record(
    original: dict[str, Any],
    stripped: dict[str, Any],
    path: Path,
) -> None:
    for key, value in original.items():
        if key in {"derived", "current_derived"}:
            continue
        if stripped.get(key) != value:
            raise ValueError(f"stripped episode lost or changed field {path.name}:{key}")
    for key in ("id", "episode_id", "date", "source", "observed"):
        if key in original and stripped.get(key) != original[key]:
            raise ValueError(f"stripped episode lost required field {path.name}:{key}")
    if "derived" in stripped or "current_derived" in stripped:
        raise ValueError(f"stripped episode still has derived fields: {path.name}")


def _validate_stripped_records(
    stripped_by_path: dict[Path, dict[str, Any]],
    annotation_run_dir: Path,
    *,
    expected_readiness: dict[str, int],
) -> dict[str, int]:
    with tempfile.TemporaryDirectory(prefix="m3-strip-derived-") as tmp:
        temp_episode_dir = Path(tmp) / "episodes"
        temp_episode_dir.mkdir()
        for path, stripped in stripped_by_path.items():
            _write_json(temp_episode_dir / path.name, stripped)
        loaded = load_analytics_episodes(
            temp_episode_dir,
            annotation_run_dir=annotation_run_dir,
        )
        for episode in loaded:
            Episode.model_validate(episode.model_dump(mode="json"))
        check_observed_only(temp_episode_dir)
        readiness = _strip_readiness_counts(loaded)
    if readiness != expected_readiness:
        raise ValueError("stripped readiness does not match annotation-run baseline")
    return readiness


def _create_and_verify_backup(
    records_by_path: dict[Path, dict[str, Any]],
    backup_dir: Path,
) -> None:
    backup_dir.mkdir(parents=True, exist_ok=False)
    for source_path in records_by_path:
        _copy_episode_backup(source_path, backup_dir / source_path.name)
    _verify_backup(records_by_path, backup_dir)


def _copy_episode_backup(source_path: Path, backup_path: Path) -> None:
    shutil.copy2(source_path, backup_path)


def _verify_backup(
    records_by_path: dict[Path, dict[str, Any]],
    backup_dir: Path,
) -> None:
    for source_path, original in records_by_path.items():
        backup_path = backup_dir / source_path.name
        if not backup_path.exists():
            raise ValueError(f"backup missing episode file: {backup_path}")
        if _read_json(backup_path) != original:
            raise ValueError(f"backup does not match original: {backup_path}")


def _replace_episode_files(stripped_by_path: dict[Path, dict[str, Any]]) -> None:
    temp_paths: dict[Path, Path] = {}
    for target_path, stripped in stripped_by_path.items():
        temp_path = target_path.with_name(f".{target_path.name}.strip-tmp")
        _write_json(temp_path, stripped)
        temp_paths[target_path] = temp_path

    for target_path, temp_path in temp_paths.items():
        temp_path.replace(target_path)


def _write_run(
    run_dir: Path,
    manifest: AnnotationRunManifest,
    rows: list[AnnotationRunRow],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "annotations.jsonl").write_text(
        "".join(
            row.model_dump_json() + "\n"
            for row in sorted(rows, key=lambda item: item.episode_id)
        ),
        encoding="utf-8",
    )


def _read_episode_records(episode_dir: Path) -> list[dict[str, Any]]:
    return [_read_json(path) for path in sorted(episode_dir.glob("episode-*.json"))]


def _read_episode_records_by_path(episode_dir: Path) -> dict[Path, dict[str, Any]]:
    return {path: _read_json(path) for path in _episode_paths(episode_dir)}


def _episode_paths(episode_dir: Path) -> list[Path]:
    return sorted(episode_dir.glob("episode-*.json"))


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"episode JSON must be an object: {path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _episode_id(record: dict[str, Any]) -> str:
    value = record.get("id", record.get("episode_id"))
    if not isinstance(value, str) or not value:
        raise ValueError("episode id is required")
    return value


def _episode_ids(records: list[dict[str, Any]]) -> set[str]:
    seen: set[str] = set()
    for record in records:
        episode_id = _episode_id(record)
        if episode_id in seen:
            raise ValueError(f"duplicate episode id: {episode_id}")
        seen.add(episode_id)
    return seen


def _created_at(timestamp: str | None) -> datetime:
    if timestamp is None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    return datetime.strptime(timestamp, "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)


def _is_empty_derived(derived: dict[str, Any]) -> bool:
    return not any(
        derived.get(key)
        for key in (
            "nodes",
            "trigger_annotations",
            "actor_annotations",
            "cognition_annotations",
            "emotion_annotations",
            "behavior_annotations",
            "outcome_annotations",
            "relations",
        )
    )


if __name__ == "__main__":
    main()

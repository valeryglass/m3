from __future__ import annotations

import argparse
import json
import shutil
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.derived_normalizer import empty_derived
from app.readiness import classify_episode_readiness
from app.schemas.episode import Episode


DEFAULT_EPISODE_DIR = Path("data/episodes")
DEFAULT_WORK_DIR = Path("data/annotation-work")
DEFAULT_BACKUP_ROOT = Path("data/backups")
DEFAULT_BATCH_SIZE = 5
DEFAULT_QUEUE_PREFIX = "queue"
ANNOTATION_FIELDS = (
    "trigger_annotations",
    "actor_annotations",
    "cognition_annotations",
    "emotion_annotations",
    "behavior_annotations",
)
QUEUE_INSTRUCTIONS = (
    "Fill only proposal.derived for this episode. Preserve id/date/source/observed. "
    "Use only model/episode.schema.json fields. Every derived item needs "
    "source_field, source_quote, and confidence. Skip uncertain annotations."
)


@dataclass(frozen=True)
class AuditSummary:
    total: int = 0
    valid: int = 0
    invalid: int = 0
    empty_derived: int = 0
    with_nodes: int = 0
    with_annotations: int = 0
    with_relations: int = 0
    observed_ready: int = 0
    graph_ready: int = 0
    report_ready: int = 0
    profile_eligible: int = 0
    gap_reasons: dict[str, int] = field(default_factory=dict)
    nodes_total: int = 0
    trigger_annotations_total: int = 0
    actor_annotations_total: int = 0
    cognition_annotations_total: int = 0
    emotion_annotations_total: int = 0
    behavior_annotations_total: int = 0
    relations_total: int = 0
    invalid_files: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExportSummary:
    episodes: int
    batches: int
    files: tuple[str, ...]


@dataclass(frozen=True)
class ValidationSummary:
    total: int = 0
    valid: int = 0
    invalid: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ApplySummary:
    total: int
    validated: int
    updated: int
    dry_run: bool
    backup_dir: str | None = None


def audit_episode_dir(episode_dir: Path = DEFAULT_EPISODE_DIR) -> AuditSummary:
    invalid_files: list[str] = []
    total = valid = 0
    empty_derived = with_nodes = with_annotations = with_relations = 0
    observed_ready = graph_ready = report_ready = profile_eligible = 0
    gap_reasons: dict[str, int] = {}
    totals = {
        "nodes_total": 0,
        "trigger_annotations_total": 0,
        "actor_annotations_total": 0,
        "cognition_annotations_total": 0,
        "emotion_annotations_total": 0,
        "behavior_annotations_total": 0,
        "relations_total": 0,
    }

    for path in _episode_paths(episode_dir):
        total += 1
        try:
            episode = Episode.model_validate(_read_json(path))
        except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            invalid_files.append(f"{path.name}: {type(exc).__name__}")
            continue

        valid += 1
        derived = episode.derived
        annotations = [
            derived.trigger_annotations,
            derived.actor_annotations,
            derived.cognition_annotations,
            derived.emotion_annotations,
            derived.behavior_annotations,
        ]
        if not derived.nodes and not any(annotations) and not derived.relations:
            empty_derived += 1
        if derived.nodes:
            with_nodes += 1
        if any(annotations):
            with_annotations += 1
        if derived.relations:
            with_relations += 1
        readiness = classify_episode_readiness(episode)
        if readiness.observed_ready:
            observed_ready += 1
        if readiness.graph_ready:
            graph_ready += 1
        if readiness.report_ready:
            report_ready += 1
        if readiness.profile_eligible:
            profile_eligible += 1
        for reason in readiness.gap_reasons:
            gap_reasons[reason] = gap_reasons.get(reason, 0) + 1

        totals["nodes_total"] += len(derived.nodes)
        totals["trigger_annotations_total"] += len(derived.trigger_annotations)
        totals["actor_annotations_total"] += len(derived.actor_annotations)
        totals["cognition_annotations_total"] += len(derived.cognition_annotations)
        totals["emotion_annotations_total"] += len(derived.emotion_annotations)
        totals["behavior_annotations_total"] += len(derived.behavior_annotations)
        totals["relations_total"] += len(derived.relations)

    return AuditSummary(
        total=total,
        valid=valid,
        invalid=total - valid,
        empty_derived=empty_derived,
        with_nodes=with_nodes,
        with_annotations=with_annotations,
        with_relations=with_relations,
        observed_ready=observed_ready,
        graph_ready=graph_ready,
        report_ready=report_ready,
        profile_eligible=profile_eligible,
        gap_reasons=gap_reasons,
        invalid_files=tuple(invalid_files),
        **totals,
    )


def export_batches(
    episode_dir: Path = DEFAULT_EPISODE_DIR,
    work_dir: Path = DEFAULT_WORK_DIR,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> ExportSummary:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    episodes = []
    for path in _episode_paths(episode_dir):
        data = _read_json(path)
        episode = Episode.model_validate(data)
        episodes.append(
            {
                "episode_id": episode.id,
                "path": path.as_posix(),
                "date": data["date"],
                "source": data["source"],
                "observed": data["observed"],
                "current_derived": data.get("derived", empty_derived()),
            }
        )

    work_dir.mkdir(parents=True, exist_ok=True)
    output_files: list[str] = []
    for index, batch in enumerate(_chunks(episodes, batch_size), start=1):
        path = work_dir / f"batch-{index:03d}.jsonl"
        _write_jsonl(path, batch)
        output_files.append(path.as_posix())

    return ExportSummary(
        episodes=len(episodes),
        batches=len(output_files),
        files=tuple(output_files),
    )


def queue_empty_derived(
    episode_dir: Path = DEFAULT_EPISODE_DIR,
    work_dir: Path = DEFAULT_WORK_DIR,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    source: str | None = None,
    prefix: str = DEFAULT_QUEUE_PREFIX,
) -> ExportSummary:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    records = []
    for path in _episode_paths(episode_dir):
        data = _read_json(path)
        episode = Episode.model_validate(data)
        if source is not None and episode.source != source:
            continue
        readiness = classify_episode_readiness(episode)
        if "empty_derived" not in readiness.gap_reasons:
            continue
        records.append(
            {
                "episode_id": episode.id,
                "path": path.as_posix(),
                "date": data["date"],
                "source": data["source"],
                "gap_reasons": list(readiness.gap_reasons),
                "observed": data["observed"],
                "current_derived": data.get("derived", empty_derived()),
                "instructions": QUEUE_INSTRUCTIONS,
            }
        )

    work_dir.mkdir(parents=True, exist_ok=True)
    output_files: list[str] = []
    for index, batch in enumerate(_chunks(records, batch_size), start=1):
        path = work_dir / f"{prefix}-{index:03d}.jsonl"
        _write_jsonl(path, batch)
        output_files.append(path.as_posix())

    return ExportSummary(
        episodes=len(records),
        batches=len(output_files),
        files=tuple(output_files),
    )


def validate_proposals(proposal_path: Path) -> ValidationSummary:
    total = valid = 0
    errors: list[str] = []

    for line_no, proposal in _read_jsonl(proposal_path):
        total += 1
        try:
            _validated_episode_from_proposal(proposal)
        except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            errors.append(f"line {line_no}: {exc}")
            continue
        valid += 1

    return ValidationSummary(
        total=total,
        valid=valid,
        invalid=total - valid,
        errors=tuple(errors),
    )


def apply_proposals(
    proposal_path: Path,
    *,
    write: bool = False,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    timestamp: str | None = None,
) -> ApplySummary:
    proposals = [proposal for _, proposal in _read_jsonl(proposal_path)]
    validated = [_validated_episode_from_proposal(proposal) for proposal in proposals]

    if not write:
        return ApplySummary(
            total=len(proposals),
            validated=len(validated),
            updated=0,
            dry_run=True,
        )

    backup_dir = backup_root / f"episodes-{timestamp or _timestamp()}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    for item in validated:
        source_path = item["path"]
        shutil.copy2(source_path, backup_dir / source_path.name)

    for item in validated:
        _write_json(item["path"], item["data"])

    return ApplySummary(
        total=len(proposals),
        validated=len(validated),
        updated=len(validated),
        dry_run=False,
        backup_dir=backup_dir.as_posix(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export, validate, and apply local CBT episode annotations."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--episode-dir", default=str(DEFAULT_EPISODE_DIR))

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--episode-dir", default=str(DEFAULT_EPISODE_DIR))
    export_parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR))
    export_parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)

    queue_parser = subparsers.add_parser("queue")
    queue_parser.add_argument("--episode-dir", default=str(DEFAULT_EPISODE_DIR))
    queue_parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR))
    queue_parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    queue_parser.add_argument("--source")
    queue_parser.add_argument("--prefix", default=DEFAULT_QUEUE_PREFIX)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("proposal_path")

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("proposal_path")
    apply_parser.add_argument("--write", action="store_true")
    apply_parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))

    args = parser.parse_args()
    if args.command == "audit":
        summary = audit_episode_dir(Path(args.episode_dir))
    elif args.command == "export":
        summary = export_batches(
            Path(args.episode_dir),
            Path(args.work_dir),
            batch_size=args.batch_size,
        )
    elif args.command == "queue":
        summary = queue_empty_derived(
            Path(args.episode_dir),
            Path(args.work_dir),
            batch_size=args.batch_size,
            source=args.source,
            prefix=args.prefix,
        )
    elif args.command == "validate":
        summary = validate_proposals(Path(args.proposal_path))
    elif args.command == "apply":
        summary = apply_proposals(
            Path(args.proposal_path),
            write=args.write,
            backup_root=Path(args.backup_root),
        )
    else:
        raise ValueError(f"Unsupported command: {args.command}")
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))


def _validated_episode_from_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be an object")
    source_path = Path(str(proposal.get("path", "")))
    if not source_path:
        raise ValueError("proposal.path is required")
    source = _read_json(source_path)
    if proposal.get("episode_id") != source.get("id"):
        raise ValueError("proposal episode_id does not match source episode id")
    derived = proposal.get("derived")
    if not isinstance(derived, dict):
        raise ValueError("proposal.derived must be an object")

    data = deepcopy(source)
    data["derived"] = derived
    episode = Episode.model_validate(data)
    _validate_integrity(episode)
    return {"path": source_path, "data": data}


def _validate_integrity(episode: Episode) -> None:
    observed = episode.observed
    node_ids = {item.id for item in episode.derived.nodes}

    for node in episode.derived.nodes:
        _require_source_field(observed, node.source_field)

    for section in ANNOTATION_FIELDS:
        for annotation in getattr(episode.derived, section):
            _require_source_field(observed, annotation.source_field)
            node_id = getattr(annotation, "node_id", None)
            if node_id and node_id not in node_ids:
                raise ValueError(f"unknown node_id: {node_id}")

    for relation in episode.derived.relations:
        _require_source_field(observed, relation.source_field)
        _require_ref(observed, relation.from_ref, node_ids)
        _require_ref(observed, relation.to_ref, node_ids)


def _require_source_field(observed: Any, source_field: str) -> None:
    if source_field.startswith("observed.emotion."):
        emotion = observed.emotion
        name = source_field.removeprefix("observed.emotion.")
        if getattr(emotion, name) is None:
            raise ValueError(f"missing source field: {source_field}")
        return
    if source_field.startswith("observed."):
        name = source_field.removeprefix("observed.")
        if getattr(observed, name) is None:
            raise ValueError(f"missing source field: {source_field}")
        return
    raise ValueError(f"unsupported source field: {source_field}")


def _require_ref(observed: Any, ref: str, node_ids: set[str]) -> None:
    if ref == "episode":
        return
    if ref in node_ids:
        return
    if ref.startswith("node-"):
        raise ValueError(f"unknown relation ref: {ref}")
    if ref.startswith("observed."):
        _require_source_field(observed, ref)
        return
    raise ValueError(f"unsupported relation ref: {ref}")


def _episode_paths(episode_dir: Path) -> list[Path]:
    return sorted(episode_dir.glob("episode-*.json"))


def _chunks(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON file must contain an object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    records = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError(f"line {line_no}: JSONL records must be objects")
        records.append((line_no, data))
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import argparse
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas.episode import Episode


LEGACY_DERIVED_KEYS = frozenset({"atomic_thoughts", "cognitive_distortions"})
CURRENT_DERIVED_KEYS = (
    "nodes",
    "trigger_annotations",
    "actor_annotations",
    "cognition_annotations",
    "emotion_annotations",
    "behavior_annotations",
    "outcome_annotations",
    "relations",
)
PRE_RELATION_DERIVED_KEYS = tuple(
    key for key in CURRENT_DERIVED_KEYS if key != "relations"
)
@dataclass(frozen=True)
class EpisodeBatchSummary:
    total: int = 0
    legacy_derived: int = 0
    current_derived: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    invalid_files: tuple[str, ...] = field(default_factory=tuple)


def empty_derived() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in CURRENT_DERIVED_KEYS}


def normalize_episode(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    normalized = deepcopy(data)
    changed = _normalize_observed_keys(normalized)
    derived = normalized.get("derived")
    if isinstance(derived, dict) and set(derived) == LEGACY_DERIVED_KEYS:
        normalized["derived"] = empty_derived()
        changed = True
    elif isinstance(derived, dict):
        changed = _normalize_derived_shell(derived) or changed
        changed = _normalize_node_refs(derived) or changed
        changed = _normalize_node_origins(derived) or changed
    return normalized, changed


def normalize_episode_derived(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    return normalize_episode(data)


def scan_episode_dir(episode_dir: Path) -> EpisodeBatchSummary:
    total = legacy_derived = current_derived = failed = 0
    invalid_files: list[str] = []
    for path in _episode_paths(episode_dir):
        total += 1
        try:
            data = _read_json(path)
            normalized, changed = normalize_episode(data)
            Episode.model_validate(normalized)
        except (OSError, ValueError, json.JSONDecodeError, ValidationError):
            failed += 1
            invalid_files.append(path.name)
            continue
        if changed:
            legacy_derived += 1
        elif _has_current_derived(data):
            current_derived += 1
    return EpisodeBatchSummary(
        total=total,
        legacy_derived=legacy_derived,
        current_derived=current_derived,
        skipped=current_derived,
        failed=failed,
        invalid_files=tuple(invalid_files),
    )


def normalize_episode_dir(episode_dir: Path) -> EpisodeBatchSummary:
    dry_run = scan_episode_dir(episode_dir)
    if dry_run.failed:
        raise ValueError(
            "Cannot normalize invalid episode files: "
            + ", ".join(dry_run.invalid_files)
        )

    updated = 0
    for path in _episode_paths(episode_dir):
        data = _read_json(path)
        normalized, changed = normalize_episode(data)
        if not changed:
            continue
        Episode.model_validate(normalized)
        _write_json(path, normalized)
        updated += 1

    return EpisodeBatchSummary(
        total=dry_run.total,
        legacy_derived=dry_run.legacy_derived,
        current_derived=dry_run.current_derived,
        updated=updated,
        skipped=dry_run.current_derived,
        failed=0,
        invalid_files=(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan or normalize episode derived annotation shells."
    )
    parser.add_argument(
        "episode_dir",
        nargs="?",
        default="data/episodes",
        help="Directory containing episode-*.json files.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Rewrite legacy derived shells after validating the full directory.",
    )
    args = parser.parse_args()

    episode_dir = Path(args.episode_dir)
    summary = (
        normalize_episode_dir(episode_dir)
        if args.write
        else scan_episode_dir(episode_dir)
    )
    print(_format_summary(summary))


def _has_current_derived(data: dict[str, Any]) -> bool:
    derived = data.get("derived")
    return isinstance(derived, dict) and all(key in derived for key in CURRENT_DERIVED_KEYS)


def _normalize_observed_keys(data: dict[str, Any]) -> bool:
    return False


def _normalize_derived_shell(derived: dict[str, Any]) -> bool:
    if "relations" in derived:
        return False
    if not all(key in derived for key in PRE_RELATION_DERIVED_KEYS):
        return False
    derived["relations"] = []
    return True


def _normalize_node_refs(derived: dict[str, Any]) -> bool:
    changed = False
    nodes = derived.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            changed = _normalize_node_object(node) or changed

    for section in (
        "trigger_annotations",
        "actor_annotations",
        "cognition_annotations",
        "emotion_annotations",
        "behavior_annotations",
    ):
        items = derived.get(section)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            changed = _normalize_source_field_container(item) or changed

    relations = derived.get("relations")
    if isinstance(relations, list):
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            for key in ("from_ref", "to_ref"):
                value = relation.get(key)
                if isinstance(value, str):
                    normalized = _observed_ref(value)
                    if normalized != value:
                        relation[key] = normalized
                        changed = True
            changed = _normalize_source_field_container(relation) or changed
    return changed


def _normalize_node_object(node: dict[str, Any]) -> bool:
    changed = False
    changed = _normalize_source_field_container(node) or changed
    return changed


def _normalize_source_field_container(item: dict[str, Any]) -> bool:
    value = item.get("source_field")
    if not isinstance(value, str):
        return False
    normalized = _observed_ref(value)
    if normalized == value:
        return False
    item["source_field"] = normalized
    return True


def _observed_ref(value: str) -> str:
    return value


def _normalize_node_origins(derived: dict[str, Any]) -> bool:
    nodes = derived.get("nodes")
    if not isinstance(nodes, list):
        return False

    changed = False
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if "node_origin" not in node:
            node["node_origin"] = "observed"
            changed = True
    return changed


def _episode_paths(episode_dir: Path) -> list[Path]:
    return sorted(episode_dir.glob("episode-*.json"))


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Episode JSON must be an object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _format_summary(summary: EpisodeBatchSummary) -> str:
    lines = [
        f"total: {summary.total}",
        f"legacy_derived: {summary.legacy_derived}",
        f"current_derived: {summary.current_derived}",
        f"updated: {summary.updated}",
        f"skipped: {summary.skipped}",
        f"failed: {summary.failed}",
    ]
    if summary.invalid_files:
        lines.append("invalid_files: " + ", ".join(summary.invalid_files))
    return "\n".join(lines)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.annotation_runs import load_annotation_run
from app.domain_classifier import (
    CLASSIFIER_VERSION,
    classify_episode_domains,
    reviewed_domain_annotations,
)
from app.graph_report import load_episodes
from app.schemas.annotation_run import (
    AnnotationRunManifest,
    AnnotationRunRow,
    DomainEnrichmentProvenance,
)
from app.schemas.episode import Episode


@dataclass(frozen=True)
class DomainEnrichmentSummary:
    episode_count: int
    rule_classified_count: int
    review_required_count: int
    reviewed_count: int
    unknown_count: int
    snapshot_written: bool
    run_dir: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "episode_count": self.episode_count,
            "rule_classified_count": self.rule_classified_count,
            "review_required_count": self.review_required_count,
            "reviewed_count": self.reviewed_count,
            "unknown_count": self.unknown_count,
            "snapshot_written": self.snapshot_written,
            "run_dir": self.run_dir,
        }


def prepare_domain_review(
    episode_dir: Path,
    annotation_run_dir: Path,
    review_queue_path: Path,
) -> DomainEnrichmentSummary:
    episodes = load_episodes(episode_dir, annotation_run_dir=annotation_run_dir)
    queue = []
    rule_classified = 0
    for episode in episodes:
        decision = classify_episode_domains(episode)
        if decision.needs_review:
            queue.append(
                {
                    "episode_id": episode.id,
                    "candidate_domains": list(decision.candidate_domains),
                    "evidence": _review_evidence_payload(episode),
                }
            )
        else:
            rule_classified += 1
    review_queue_path.parent.mkdir(parents=True, exist_ok=True)
    review_queue_path.write_text(
        json.dumps(
            {
                "classifier_version": CLASSIFIER_VERSION,
                "base_annotation_run_id": annotation_run_dir.name,
                "items": queue,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return DomainEnrichmentSummary(
        episode_count=len(episodes),
        rule_classified_count=rule_classified,
        review_required_count=len(queue),
        reviewed_count=0,
        unknown_count=0,
        snapshot_written=False,
    )


def write_domain_snapshot(
    episode_dir: Path,
    annotation_run_dir: Path,
    output_root: Path,
    run_id: str,
    review_overrides_path: Path,
    *,
    created_at: datetime | None = None,
) -> DomainEnrichmentSummary:
    base_run = load_annotation_run(
        annotation_run_dir,
        episode_ids=_episode_ids(episode_dir),
    )
    episodes = load_episodes(episode_dir, annotation_run_dir=annotation_run_dir)
    episodes_by_id = {episode.id: episode for episode in episodes}
    decisions = {
        episode.id: classify_episode_domains(episode) for episode in episodes
    }
    review_ids = {
        episode_id
        for episode_id, decision in decisions.items()
        if decision.needs_review
    }
    overrides = _load_overrides(review_overrides_path)
    if set(overrides) != review_ids:
        missing = sorted(review_ids - set(overrides))
        extra = sorted(set(overrides) - review_ids)
        raise ValueError(
            "domain review overrides do not match review queue: "
            f"missing={len(missing)} extra={len(extra)}"
        )

    rows: list[AnnotationRunRow] = []
    reviewed_count = 0
    unknown_count = 0
    for base_row in base_run.rows:
        episode = episodes_by_id[base_row.episode_id]
        if base_row.episode_id in overrides:
            override = overrides[base_row.episode_id]
            annotations = reviewed_domain_annotations(
                episode,
                primary_domain=override["primary_domain"],
                primary_source_field=override["primary_source_field"],
                secondary_domain=override.get("secondary_domain"),
                secondary_source_field=override.get("secondary_source_field"),
            )
            reviewed_count += 1
        else:
            annotations = decisions[base_row.episode_id].annotations
        if annotations[0].domain == "unknown":
            unknown_count += 1
        derived = base_row.derived.model_copy(
            update={"domain_annotations": list(annotations)}
        )
        rows.append(
            AnnotationRunRow(episode_id=base_row.episode_id, derived=derived)
        )

    _assert_preserved(base_run.rows, tuple(rows))
    run_dir = output_root / run_id
    manifest = AnnotationRunManifest(
        **base_run.manifest.model_dump(
            exclude={
                "annotation_run_id",
                "created_at",
                "source_episode_count",
                "final_snapshot_count",
                "domain_enrichment_provenance",
            }
        ),
        annotation_run_id=run_id,
        created_at=created_at or datetime.now(timezone.utc),
        source_episode_count=len(rows),
        final_snapshot_count=len(rows),
        domain_enrichment_provenance=DomainEnrichmentProvenance(
            classifier_version=CLASSIFIER_VERSION,
            base_annotation_run_id=base_run.manifest.annotation_run_id,
            rule_classified_count=len(rows) - reviewed_count,
            reviewed_count=reviewed_count,
            unknown_count=unknown_count,
        ),
    )
    _write_run(run_dir, manifest, tuple(rows))
    return DomainEnrichmentSummary(
        episode_count=len(rows),
        rule_classified_count=len(rows) - reviewed_count,
        review_required_count=len(review_ids),
        reviewed_count=reviewed_count,
        unknown_count=unknown_count,
        snapshot_written=True,
        run_dir=run_dir.as_posix(),
    )


def _load_overrides(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("domain review overrides items must be a list")
    overrides: dict[str, dict[str, Any]] = {}
    for item in items:
        episode_id = item.get("episode_id")
        if not isinstance(episode_id, str) or episode_id in overrides:
            raise ValueError("invalid or duplicate domain review override")
        overrides[episode_id] = item
    return overrides


def _review_evidence_payload(episode: Episode) -> dict[str, str]:
    evidence = {"observed.situation": episode.observed.situation.source_quote}
    for name in ("trigger", "actor", "quote"):
        value = getattr(episode.observed, name)
        if value is not None and value.source_quote.strip():
            evidence[f"observed.{name}"] = value.source_quote
    return evidence


def _episode_ids(episode_dir: Path) -> set[str]:
    episode_ids: set[str] = set()
    for path in sorted(episode_dir.glob("episode-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        episode_id = data.get("id", data.get("episode_id"))
        if not isinstance(episode_id, str) or not episode_id:
            raise ValueError(f"episode id is required: {path}")
        if episode_id in episode_ids:
            raise ValueError(f"duplicate episode id: {episode_id}")
        episode_ids.add(episode_id)
    return episode_ids


def _assert_preserved(
    base_rows: tuple[AnnotationRunRow, ...],
    enriched_rows: tuple[AnnotationRunRow, ...],
) -> None:
    base_by_id = {row.episode_id: row for row in base_rows}
    enriched_by_id = {row.episode_id: row for row in enriched_rows}
    if set(base_by_id) != set(enriched_by_id):
        raise ValueError("domain enrichment changed annotation row identity")
    for episode_id, base_row in base_by_id.items():
        before = base_row.derived.model_dump(mode="json")
        after = enriched_by_id[episode_id].derived.model_dump(mode="json")
        before.pop("domain_annotations", None)
        after.pop("domain_annotations", None)
        if before != after:
            raise ValueError(
                f"domain enrichment changed existing derived data: {episode_id}"
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Enrich annotation snapshots with life domains")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare-review")
    prepare.add_argument("--episode-dir", type=Path, default=Path("data/episodes"))
    prepare.add_argument("--annotation-run-dir", type=Path, required=True)
    prepare.add_argument("--review-queue", type=Path, required=True)
    write = subparsers.add_parser("write-snapshot")
    write.add_argument("--episode-dir", type=Path, default=Path("data/episodes"))
    write.add_argument("--annotation-run-dir", type=Path, required=True)
    write.add_argument("--output-root", type=Path, default=Path("data/annotation-runs"))
    write.add_argument("--run-id", required=True)
    write.add_argument("--review-overrides", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare-review":
        summary = prepare_domain_review(
            args.episode_dir,
            args.annotation_run_dir,
            args.review_queue,
        )
    else:
        summary = write_domain_snapshot(
            args.episode_dir,
            args.annotation_run_dir,
            args.output_root,
            args.run_id,
            args.review_overrides,
        )
    print(json.dumps(summary.as_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

import json

import pytest

from app.annotation_producer import produce_annotation_run
from app.annotation_runs import load_annotation_run
from app.domain_enrichment import prepare_domain_review, write_domain_snapshot
from tests.test_annotation_producer import _episode, _read_jsonl, _write_json


def test_domain_enrichment_prepares_private_review_queue_and_preserves_snapshot(
    tmp_path,
):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    review_queue = tmp_path / "annotation-work" / "domain-review.json"
    overrides = tmp_path / "annotation-work" / "domain-overrides.json"
    episode_dir.mkdir()
    direct = _episode("episode-20260503-1")
    direct["observed"]["situation"] = {
        "value": "На работе обсуждал задачу.",
        "source_quote": "на работе обсуждал задачу",
    }
    ambiguous = _episode("episode-20260503-2")
    ambiguous["observed"]["situation"] = {
        "value": "Произошло событие.",
        "source_quote": "произошло событие",
    }
    _write_json(episode_dir / "episode-20260503-1.json", direct)
    _write_json(episode_dir / "episode-20260503-2.json", ambiguous)
    produce_annotation_run(
        episode_dir,
        run_root,
        write=True,
        timestamp="20260619-100000",
    )
    base_run = run_root / "run-20260619-100000-deterministic"
    base_rows = _read_jsonl(base_run / "annotations.jsonl")

    prepared = prepare_domain_review(episode_dir, base_run, review_queue)

    assert prepared.episode_count == 2
    assert prepared.rule_classified_count == 1
    assert prepared.review_required_count == 1
    queue = json.loads(review_queue.read_text(encoding="utf-8"))
    assert [item["episode_id"] for item in queue["items"]] == [
        "episode-20260503-2"
    ]
    _write_json(
        overrides,
        {
            "items": [
                {
                    "episode_id": "episode-20260503-2",
                    "primary_domain": "unknown",
                    "primary_source_field": "observed.situation",
                }
            ]
        },
    )

    summary = write_domain_snapshot(
        episode_dir,
        base_run,
        run_root,
        "run-20260619-110000-domains",
        overrides,
    )

    enriched_run = run_root / "run-20260619-110000-domains"
    enriched_rows = _read_jsonl(enriched_run / "annotations.jsonl")
    assert summary.snapshot_written is True
    assert summary.rule_classified_count == 1
    assert summary.reviewed_count == 1
    assert summary.unknown_count == 1
    for before, after in zip(base_rows, enriched_rows, strict=True):
        before_derived = before["derived"]
        after_derived = after["derived"]
        before_derived.pop("domain_annotations")
        assert after_derived.pop("domain_annotations")
        assert after_derived == before_derived
    loaded = load_annotation_run(
        enriched_run,
        episode_ids={"episode-20260503-1", "episode-20260503-2"},
    )
    assert len(loaded.rows) == 2
    assert loaded.manifest.domain_enrichment_provenance is not None
    assert loaded.manifest.domain_enrichment_provenance.reviewed_count == 1


def test_domain_enrichment_requires_review_for_every_queued_episode(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_root = tmp_path / "annotation-runs"
    overrides = tmp_path / "overrides.json"
    episode_dir.mkdir()
    episode = _episode()
    episode["observed"]["situation"] = {
        "value": "Произошло событие.",
        "source_quote": "произошло событие",
    }
    _write_json(episode_dir / "episode-20260503-1.json", episode)
    produce_annotation_run(
        episode_dir,
        run_root,
        write=True,
        timestamp="20260619-100000",
    )
    _write_json(overrides, {"items": []})

    with pytest.raises(ValueError, match="do not match review queue"):
        write_domain_snapshot(
            episode_dir,
            run_root / "run-20260619-100000-deterministic",
            run_root,
            "run-20260619-110000-domains",
            overrides,
        )

    assert not (run_root / "run-20260619-110000-domains").exists()

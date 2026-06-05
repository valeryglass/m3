import json

from app.annotation_workflow import (
    apply_proposals,
    audit_episode_dir,
    export_batches,
    queue_empty_derived,
    validate_proposals,
)
from app.derived_normalizer import empty_derived


def _episode(episode_id="episode-20260430-1", *, derived=None, source="telegram-chat:123"):
    return {
        "id": episode_id,
        "date": "2026-04-30",
        "source": source,
        "observed": {
            "situation": {"value": "Group chat.", "source_quote": "group chat"},
            "automatic_thought": {
                "value": "They will judge me.",
                "source_quote": "they will judge me",
            },
            "emotion": {"value": "страх", "source_quote": "страх"},
            "physical": {"value": "Tight chest.", "source_quote": "tight chest"},
            "behavior": {"value": "Closed chat.", "source_quote": "closed chat"},
            "short_term_consequence": {"value": "Relief.", "source_quote": "relief"},
            "long_term_consequence": {
                "value": "Question unresolved.",
                "source_quote": "unresolved",
            },
        },
        "derived": derived if derived is not None else empty_derived(),
    }


def _derived():
    return {
        "nodes": [
            {
                "id": "node-1",
                "node_origin": "observed",
                "kind": "cognition",
                "text": "They will judge me.",
                "source_field": "observed.automatic_thought",
                "source_quote": "they will judge me",
                "confidence": 0.9,
            },
            {
                "id": "node-2",
                "node_origin": "observed",
                "kind": "short_outcome",
                "text": "Relief.",
                "source_field": "observed.short_term_consequence",
                "source_quote": "relief",
                "confidence": 0.85,
            }
        ],
        "trigger_annotations": [],
        "actor_annotations": [],
        "cognition_annotations": [
            {
                "id": "cognition-annotation-1",
                "node_id": "node-1",
                "text": "They will judge me.",
                "kind": "prediction",
                "source_field": "observed.automatic_thought",
                "source_quote": "they will judge me",
                "confidence": 0.8,
            }
        ],
        "emotion_annotations": [],
        "behavior_annotations": [],
        "outcome_annotations": [
            {
                "id": "outcome-annotation-1",
                "node_id": "node-2",
                "horizon": "short_term",
                "type": "relief",
                "source_field": "observed.short_term_consequence",
                "source_quote": "relief",
                "confidence": 0.85,
            }
        ],
        "relations": [
            {
                "id": "relation-1",
                "type": "belongs_to",
                "from_ref": "node-1",
                "to_ref": "episode",
                "source_field": "observed.automatic_thought",
                "source_quote": "they will judge me",
                "confidence": 1.0,
            }
        ],
    }


def _write_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path, records):
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_audit_counts_valid_invalid_and_derived_coverage(tmp_path):
    episode_dir = tmp_path / "episodes"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260430-1.json", _episode())
    _write_json(
        episode_dir / "episode-20260430-2.json",
        _episode("episode-20260430-2", derived=_derived()),
    )
    (episode_dir / "episode-20260430-3.json").write_text("{broken", encoding="utf-8")

    summary = audit_episode_dir(episode_dir)

    assert summary.total == 3
    assert summary.valid == 2
    assert summary.invalid == 1
    assert summary.empty_derived == 1
    assert summary.with_nodes == 1
    assert summary.with_annotations == 1
    assert summary.with_relations == 1
    assert summary.observed_ready == 2
    assert summary.annotation_ready == 1
    assert summary.graph_ready == 1
    assert summary.report_ready == 1
    assert summary.payload_eligible == 0
    assert summary.gap_reasons == {"empty_derived": 1}
    assert summary.nodes_total == 2
    assert summary.outcome_annotations_total == 1
    assert summary.invalid_files == ("episode-20260430-3.json: JSONDecodeError",)


def test_export_writes_batches_without_modifying_episodes(tmp_path):
    episode_dir = tmp_path / "episodes"
    work_dir = tmp_path / "annotation-work"
    episode_dir.mkdir()
    path = episode_dir / "episode-20260430-1.json"
    _write_json(path, _episode())
    before = path.read_text(encoding="utf-8")
    _write_json(episode_dir / "episode-20260430-2.json", _episode("episode-20260430-2"))

    summary = export_batches(episode_dir, work_dir, batch_size=1)

    assert summary.episodes == 2
    assert summary.batches == 2
    assert path.read_text(encoding="utf-8") == before
    first_batch = (work_dir / "batch-001.jsonl").read_text(encoding="utf-8")
    assert '"observed"' in first_batch
    assert '"selected_derived"' in first_batch


def test_queue_exports_only_empty_derived_with_instructions(tmp_path):
    episode_dir = tmp_path / "episodes"
    work_dir = tmp_path / "annotation-work"
    episode_dir.mkdir()
    empty_path = episode_dir / "episode-20260430-1.json"
    ready_path = episode_dir / "episode-20260430-2.json"
    _write_json(empty_path, _episode())
    _write_json(ready_path, _episode("episode-20260430-2", derived=_derived()))
    before = empty_path.read_text(encoding="utf-8")

    summary = queue_empty_derived(episode_dir, work_dir, batch_size=10)

    assert summary.episodes == 1
    assert summary.batches == 1
    assert summary.files == ((work_dir / "queue-001.jsonl").as_posix(),)
    assert empty_path.read_text(encoding="utf-8") == before
    records = _read_jsonl(work_dir / "queue-001.jsonl")
    assert len(records) == 1
    record = records[0]
    assert record["episode_id"] == "episode-20260430-1"
    assert record["path"] == empty_path.as_posix()
    assert record["source"] == "telegram-chat:123"
    assert record["date"] == "2026-04-30"
    assert record["gap_reasons"] == ["empty_derived"]
    assert record["observed"]["emotion"]["value"] == "страх"
    assert record["selected_derived"] == empty_derived()
    assert "Fill only proposal.derived" in record["instructions"]
    assert "outcome_annotations" in record["instructions"]


def test_queue_can_filter_by_source(tmp_path):
    episode_dir = tmp_path / "episodes"
    work_dir = tmp_path / "annotation-work"
    episode_dir.mkdir()
    _write_json(
        episode_dir / "episode-20260430-1.json",
        _episode(source="telegram-chat:123"),
    )
    _write_json(
        episode_dir / "episode-20260430-2.json",
        _episode("episode-20260430-2", source="telegram-chat:456"),
    )

    summary = queue_empty_derived(
        episode_dir,
        work_dir,
        batch_size=10,
        source="telegram-chat:456",
    )

    assert summary.episodes == 1
    records = _read_jsonl(work_dir / "queue-001.jsonl")
    assert records[0]["episode_id"] == "episode-20260430-2"
    assert records[0]["source"] == "telegram-chat:456"


def test_validate_rejects_bad_node_reference(tmp_path):
    episode_dir = tmp_path / "episodes"
    episode_dir.mkdir()
    path = episode_dir / "episode-20260430-1.json"
    _write_json(path, _episode())
    derived = _derived()
    derived["relations"][0]["from_ref"] = "node-99"
    proposal_path = tmp_path / "proposals.jsonl"
    _write_jsonl(
        proposal_path,
        [{"episode_id": "episode-20260430-1", "path": path.as_posix(), "derived": derived}],
    )

    summary = validate_proposals(proposal_path)

    assert summary.total == 1
    assert summary.valid == 0
    assert summary.invalid == 1
    assert "unknown relation ref: node-99" in summary.errors[0]


def test_validate_rejects_bad_outcome_node_reference(tmp_path):
    episode_dir = tmp_path / "episodes"
    episode_dir.mkdir()
    path = episode_dir / "episode-20260430-1.json"
    _write_json(path, _episode())
    derived = _derived()
    derived["outcome_annotations"][0]["node_id"] = "node-99"
    proposal_path = tmp_path / "proposals.jsonl"
    _write_jsonl(
        proposal_path,
        [{"episode_id": "episode-20260430-1", "path": path.as_posix(), "derived": derived}],
    )

    summary = validate_proposals(proposal_path)

    assert summary.total == 1
    assert summary.valid == 0
    assert summary.invalid == 1
    assert "unknown node_id: node-99" in summary.errors[0]


def test_apply_defaults_to_dry_run_without_writing(tmp_path):
    episode_dir = tmp_path / "episodes"
    backup_root = tmp_path / "backups"
    episode_dir.mkdir()
    path = episode_dir / "episode-20260430-1.json"
    _write_json(path, _episode())
    before = path.read_text(encoding="utf-8")
    proposal_path = tmp_path / "proposals.jsonl"
    _write_jsonl(
        proposal_path,
        [{"episode_id": "episode-20260430-1", "path": path.as_posix(), "derived": _derived()}],
    )

    summary = apply_proposals(proposal_path, backup_root=backup_root)

    assert summary.dry_run is True
    assert summary.validated == 1
    assert summary.updated == 0
    assert path.read_text(encoding="utf-8") == before
    assert not backup_root.exists()


def test_apply_with_write_backs_up_and_replaces_only_derived(tmp_path):
    episode_dir = tmp_path / "episodes"
    backup_root = tmp_path / "backups"
    episode_dir.mkdir()
    path = episode_dir / "episode-20260430-1.json"
    original = _episode()
    _write_json(path, original)
    proposal_path = tmp_path / "proposals.jsonl"
    _write_jsonl(
        proposal_path,
        [{"episode_id": "episode-20260430-1", "path": path.as_posix(), "derived": _derived()}],
    )

    summary = apply_proposals(
        proposal_path,
        write=True,
        backup_root=backup_root,
        timestamp="20260511-120000",
    )

    updated = json.loads(path.read_text(encoding="utf-8"))
    backup = json.loads(
        (backup_root / "episodes-20260511-120000" / path.name).read_text(
            encoding="utf-8"
        )
    )
    assert summary.dry_run is False
    assert summary.updated == 1
    assert updated["observed"] == original["observed"]
    assert updated["derived"]["nodes"][0]["id"] == "node-1"
    assert backup == original

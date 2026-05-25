import json

from app.annotation_workflow import (
    apply_proposals,
    audit_episode_dir,
    export_batches,
    validate_proposals,
)
from app.derived_normalizer import empty_derived


def _episode(episode_id="episode-20260430-1", *, derived=None):
    return {
        "id": episode_id,
        "date": "2026-04-30",
        "source": "telegram-chat:123",
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
    assert summary.graph_ready == 1
    assert summary.report_ready == 1
    assert summary.profile_eligible == 0
    assert summary.gap_reasons == {"empty_derived": 1}
    assert summary.nodes_total == 1
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
    assert '"current_derived"' in first_batch


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

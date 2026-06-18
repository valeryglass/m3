import json

from app.analytics_loader import load_analytics_episodes
from app.annotation_producer import produce_annotation_run


def test_annotation_producer_dry_run_does_not_write(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260503-1.json", _episode())

    summary = produce_annotation_run(
        episode_dir,
        output_root,
        timestamp="20260618-120000",
    )

    assert summary.dry_run is True
    assert summary.episode_count == 1
    assert summary.row_count == 1
    assert not output_root.exists()


def test_annotation_producer_write_creates_run(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260503-1.json", _episode())

    summary = produce_annotation_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260618-120000",
    )

    run_dir = output_root / "run-20260618-120000-deterministic"
    rows = _read_jsonl(run_dir / "annotations.jsonl")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert summary.dry_run is False
    assert manifest["prompt_version"] == "deterministic-observed-v1"
    assert rows[0]["episode_id"] == "episode-20260503-1"
    assert rows[0]["derived"]["nodes"]


def test_annotation_producer_only_missing_skips_existing(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    existing_run = output_root / "run-20260618-110000-deterministic"
    episode_dir.mkdir()
    first = _episode("episode-20260503-1")
    second = _episode("episode-20260503-2")
    _write_json(episode_dir / "episode-20260503-1.json", first)
    _write_json(episode_dir / "episode-20260503-2.json", second)
    produce_annotation_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260618-110000",
    )

    summary = produce_annotation_run(
        episode_dir,
        output_root,
        only_missing=True,
        annotation_run_dir=existing_run,
        write=True,
        timestamp="20260618-120000",
    )

    rows = _read_jsonl(output_root / "run-20260618-120000-deterministic" / "annotations.jsonl")
    assert summary.row_count == 0
    assert rows == []


def test_annotation_producer_source_filter(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    other = _episode("episode-20260503-2")
    other["source"] = "telegram-chat:456"
    _write_json(episode_dir / "episode-20260503-1.json", _episode())
    _write_json(episode_dir / "episode-20260503-2.json", other)

    summary = produce_annotation_run(
        episode_dir,
        output_root,
        source="telegram-chat:456",
        write=True,
        timestamp="20260618-120000",
    )

    rows = _read_jsonl(output_root / "run-20260618-120000-deterministic" / "annotations.jsonl")
    assert summary.row_count == 1
    assert rows[0]["episode_id"] == "episode-20260503-2"


def test_annotation_run_is_readable_by_analytics_loader(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    episode = _episode()
    _write_json(episode_dir / "episode-20260503-1.json", episode)
    produce_annotation_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260618-120000",
    )

    episodes = load_analytics_episodes(
        episode_dir,
        annotation_run_dir=output_root / "run-20260618-120000-deterministic",
    )

    assert episodes[0].derived.nodes


def test_annotation_producer_reports_coverage_delta(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260503-1.json", _episode("episode-20260503-1"))
    _write_json(episode_dir / "episode-20260503-2.json", _episode("episode-20260503-2"))

    summary = produce_annotation_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260618-120000",
    )

    assert summary.annotated_before == 0
    assert summary.annotated_after == 2
    assert summary.pending_before == 2
    assert summary.pending_after == 0
    assert summary.coverage_before == "partial"
    assert summary.coverage_after == "full"


def test_annotation_producer_only_missing_reports_noop_when_full(tmp_path):
    episode_dir = tmp_path / "episodes"
    output_root = tmp_path / "annotation-runs"
    existing_run = output_root / "run-20260618-110000-deterministic"
    episode_dir.mkdir()
    _write_json(episode_dir / "episode-20260503-1.json", _episode())
    produce_annotation_run(
        episode_dir,
        output_root,
        write=True,
        timestamp="20260618-110000",
    )

    summary = produce_annotation_run(
        episode_dir,
        output_root,
        only_missing=True,
        annotation_run_dir=existing_run,
        timestamp="20260618-120000",
    )

    assert summary.row_count == 0
    assert summary.annotated_before == 1
    assert summary.annotated_after == 1
    assert summary.pending_before == 0
    assert summary.pending_after == 0
    assert summary.coverage_before == "full"
    assert summary.coverage_after == "full"


def _episode(episode_id="episode-20260503-1"):
    return {
        "id": episode_id,
        "date": "2026-05-03",
        "source": "telegram-chat:123",
        "observed": {
            "situation": {"value": "s", "source_quote": "s"},
            "trigger": {"value": "коллега", "source_quote": "коллега"},
            "actor": {"value": "коллега", "source_quote": "коллега"},
            "quote": {"value": "q", "source_quote": "q"},
            "automatic_thought": {"value": "я плохой", "source_quote": "я плохой"},
            "emotion": {"value": "страх", "source_quote": "страх"},
            "behavior": {"value": "избегать", "source_quote": "избегать"},
            "physical": {"value": "тело", "source_quote": "тело"},
            "short_term_consequence": {"value": "легче", "source_quote": "легче"},
            "long_term_consequence": {"value": "цена", "source_quote": "цена"},
        },
    }


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

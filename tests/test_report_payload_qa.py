import json

from app.insight_payload import build_insight_payload, write_insight_payload
from app.graph_report import build_report
from app.map_payload import write_map_payload
from app.report_payload_qa import (
    STATUS_BLOCKED,
    STATUS_PASSED,
    build_qa_status,
)
from tests.test_insight_payload import _empty_derived, _episode, _write_annotation_run


def test_report_payload_qa_full_source_run_passes(tmp_path):
    episode_dir, run_dir = _episode_dir_with_run(tmp_path)
    journal_path = tmp_path / "journal.jsonl"

    status = build_qa_status(
        episode_dir,
        run_dir,
        "telegram-chat:123",
        journal_log=journal_path,
    )

    assert status["status"] == STATUS_PASSED
    assert status["selected_annotation_run_id"] == run_dir.name
    assert status["selected_annotation_run_path"] == run_dir.as_posix()
    assert status["coverage"]["state"] == "full"
    assert status["readiness"]["payload_eligible_count"] == 4
    assert "main_pattern" in status["report_card_kinds"]
    assert status["short_report_chars"] > 0
    assert status["long_report_chars"] > status["short_report_chars"]
    assert all(check["passed"] for check in status["checks"])
    events = _read_jsonl(journal_path)
    assert [event["event_type"] for event in events] == [
        "report_payload_qa.started",
        "report_payload_qa.passed",
    ]
    assert "Короткий отчет" not in journal_path.read_text(encoding="utf-8")


def test_report_payload_qa_missing_explicit_run_is_blocked(tmp_path):
    episode_dir = tmp_path / "episodes"
    journal_path = tmp_path / "journal.jsonl"
    episode_dir.mkdir()

    status = build_qa_status(
        episode_dir,
        None,
        "telegram-chat:123",
        journal_log=journal_path,
    )

    assert status["status"] == STATUS_BLOCKED
    assert status["blockers"] == ["annotation-run is required"]
    assert status["selected_annotation_run_path"] is None
    events = _read_jsonl(journal_path)
    assert events[-1]["event_type"] == "report_payload_qa.blocked"
    assert events[-1]["counts"]["blocker_count"] == 1


def test_report_payload_qa_partial_coverage_blocks_readiness(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    first = _episode("episode-20260430-1")
    second = _episode("episode-20260430-2")
    for episode in (first, second):
        _write_episode(episode_dir, episode)
    _write_annotation_run(run_dir, [(first["id"], first["derived"])])

    status = build_qa_status(episode_dir, run_dir, "telegram-chat:123")

    assert status["status"] == STATUS_BLOCKED
    assert status["coverage"]["state"] == "partial"
    assert "source coverage is partial" in status["blockers"]
    assert any(
        check["name"] == "payload_export_ready" and not check["passed"]
        for check in status["checks"]
    )


def test_report_payload_qa_payload_ineligible_source_blocks(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    episode = _episode("episode-20260430-1")
    _write_episode(episode_dir, episode)
    _write_annotation_run(run_dir, [(episode["id"], _empty_derived())])

    status = build_qa_status(episode_dir, run_dir, "telegram-chat:123")

    assert status["status"] == STATUS_BLOCKED
    assert any("payload readiness is incomplete" in item for item in status["blockers"])


def test_report_payload_qa_exported_insight_mismatch_blocks(tmp_path):
    episode_dir, run_dir = _episode_dir_with_run(tmp_path)
    insight_output = tmp_path / "insight.json"
    insight_output.write_text('{"kind": "wrong"}\n', encoding="utf-8")

    status = build_qa_status(
        episode_dir,
        run_dir,
        "telegram-chat:123",
        insight_payload_path=insight_output,
    )

    assert status["status"] == STATUS_BLOCKED
    assert "insight export differs" in status["blockers"]


def test_report_payload_qa_exported_map_mismatch_blocks(tmp_path):
    episode_dir, run_dir = _episode_dir_with_run(tmp_path)
    map_output = tmp_path / "map.json"
    map_output.write_text('{"kind": "wrong"}\n', encoding="utf-8")

    status = build_qa_status(
        episode_dir,
        run_dir,
        "telegram-chat:123",
        map_payload_path=map_output,
    )

    assert status["status"] == STATUS_BLOCKED
    assert "map export differs" in status["blockers"]


def test_report_payload_qa_matching_exports_pass(tmp_path):
    episode_dir, run_dir = _episode_dir_with_run(tmp_path)
    insight_output = tmp_path / "insight.json"
    map_output = tmp_path / "map.json"
    all_episodes, source_episodes, coverage = _loaded_source(episode_dir, run_dir)
    report = build_report(source_episodes, coverage=coverage)
    insight = build_insight_payload(report)
    write_insight_payload(insight, insight_output)
    write_map_payload(
        all_episodes,
        map_output,
        source="telegram-chat:123",
        coverage=coverage,
        provenance={
            "episode_dir": episode_dir.as_posix(),
            "source_scope": "telegram-chat:123",
            "annotation_run_id": run_dir.name,
            "annotation_run_path": run_dir.as_posix(),
            "generated_at": "2026-07-06T00:00:00+00:00",
        },
    )

    status = build_qa_status(
        episode_dir,
        run_dir,
        "telegram-chat:123",
        insight_payload_path=insight_output,
        map_payload_path=map_output,
    )

    assert status["status"] == STATUS_PASSED
    assert any(check["name"] == "insight_export_matches" for check in status["checks"])
    assert any(check["name"] == "map_export_matches" for check in status["checks"])


def test_report_payload_qa_report_text_guard_blocks_forbidden_wording(
    tmp_path,
    monkeypatch,
):
    episode_dir, run_dir = _episode_dir_with_run(tmp_path)
    monkeypatch.setattr(
        "app.report_payload_qa.render_summary_from_payload",
        lambda payload: "payload диагноз caused by stable trait",
    )

    status = build_qa_status(episode_dir, run_dir, "telegram-chat:123")

    assert status["status"] == STATUS_BLOCKED
    assert any("forbidden report wording" in item for item in status["blockers"])


def test_report_payload_qa_output_excludes_raw_quotes_and_report_text(tmp_path):
    episode_dir, run_dir = _episode_dir_with_run(tmp_path)

    status = build_qa_status(episode_dir, run_dir, "telegram-chat:123")
    rendered = json.dumps(status, ensure_ascii=False)

    assert "they will judge me" not in rendered
    assert "Group chat" not in rendered
    assert "Короткий отчет" not in rendered
    assert "Подробный отчет" not in rendered


def _episode_dir_with_run(tmp_path):
    episode_dir = tmp_path / "episodes"
    run_dir = tmp_path / "annotation-runs" / "run-test"
    episode_dir.mkdir()
    episodes = [
        _episode("episode-20260430-1", behavior_type="avoid"),
        _episode("episode-20260430-2", behavior_type="avoid"),
        _episode("episode-20260430-3", behavior_type="avoid"),
        _episode("episode-20260430-4", behavior_type="approach"),
    ]
    for episode in episodes:
        _write_episode(episode_dir, episode)
    _write_annotation_run(
        run_dir,
        [(episode["id"], episode["derived"]) for episode in episodes],
    )
    return episode_dir, run_dir


def _loaded_source(episode_dir, run_dir):
    from app.analytics_loader import annotation_coverage_for_episode_ids
    from app.graph_report import load_episodes

    all_episodes = load_episodes(episode_dir, annotation_run_dir=run_dir)
    source_episodes = [
        episode for episode in all_episodes if episode.source == "telegram-chat:123"
    ]
    coverage = annotation_coverage_for_episode_ids(
        {episode.id for episode in source_episodes},
        annotation_run_dir=run_dir,
        known_episode_ids={episode.id for episode in all_episodes},
    )
    return all_episodes, source_episodes, coverage


def _write_episode(episode_dir, episode):
    (episode_dir / f"{episode['id']}.json").write_text(
        json.dumps(episode, ensure_ascii=False),
        encoding="utf-8",
    )


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

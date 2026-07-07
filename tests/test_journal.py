import json

from app.journal import JournalLog, journal_event, record_journal_event


def test_journal_writes_jsonl_and_creates_parent_directory(tmp_path):
    path = tmp_path / "journal" / "events.jsonl"
    log = JournalLog(path)

    log.append(
        journal_event(
            component="test",
            event_type="test.started",
            stage="started",
            refs={"run_dir": tmp_path / "run-test"},
            counts={"episode_count": 1},
        )
    )

    rows = _read_jsonl(path)
    assert rows[0]["schema_version"] == "m3.journal_event.v1"
    assert rows[0]["component"] == "test"
    assert rows[0]["event_type"] == "test.started"
    assert rows[0]["refs"]["run_dir"].endswith("run-test")


def test_journal_appends_multiple_events(tmp_path):
    path = tmp_path / "events.jsonl"
    log = JournalLog(path)

    for index in range(2):
        log.append(
            journal_event(
                component="test",
                event_type=f"test.{index}",
                stage="checked",
            )
        )

    assert [row["event_type"] for row in _read_jsonl(path)] == ["test.0", "test.1"]


def test_journal_redacts_unsafe_keys(tmp_path):
    path = tmp_path / "events.jsonl"
    JournalLog(path).append(
        journal_event(
            component="capture",
            event_type="capture.failed",
            stage="failed",
            level="error",
            details={
                "raw_text": "private",
                "nested": {"api_key": "secret", "safe": "ok"},
                "prompt": "private prompt",
                "llm_output": "private output",
                "transcript": "private transcript",
            },
        )
    )

    rendered = path.read_text(encoding="utf-8")
    assert "private" not in rendered
    row = _read_jsonl(path)[0]
    assert row["details"]["raw_text"] == "[redacted]"
    assert row["details"]["nested"]["api_key"] == "[redacted]"
    assert row["details"]["nested"]["safe"] == "ok"


def test_record_journal_event_is_best_effort(tmp_path):
    directory_path = tmp_path / "directory"
    directory_path.mkdir()

    record_journal_event(
        JournalLog(directory_path),
        journal_event(component="test", event_type="test.failed", stage="failed"),
    )


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

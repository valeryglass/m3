import json
from threading import Thread

import pytest

from app.runtime_storage import (
    LockUnavailableError,
    ProcessLock,
    append_jsonl,
    atomic_write_text,
)


def test_atomic_write_preserves_previous_file_when_replace_fails(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text('{"state": "old"}\n', encoding="utf-8")

    def fail_replace(source, target):
        raise OSError("interrupted replace")

    monkeypatch.setattr("app.runtime_storage.os.replace", fail_replace)

    with pytest.raises(OSError, match="interrupted replace"):
        atomic_write_text(path, '{"state": "new"}\n')

    assert json.loads(path.read_text(encoding="utf-8")) == {"state": "old"}
    assert not list(tmp_path.glob("*.tmp"))


def test_jsonl_append_is_serialized_across_threads(tmp_path):
    path = tmp_path / "events.jsonl"
    threads = [
        Thread(target=append_jsonl, args=(path, {"index": index}))
        for index in range(40)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert sorted(row["index"] for row in rows) == list(range(40))


def test_process_lock_rejects_second_writer(tmp_path):
    path = tmp_path / "bot.lock"
    first = ProcessLock(path)
    second = ProcessLock(path)

    first.acquire()
    try:
        with pytest.raises(LockUnavailableError):
            second.acquire()
    finally:
        first.release()

    second.acquire()
    second.release()

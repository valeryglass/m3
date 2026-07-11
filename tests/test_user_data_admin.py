import json
import zipfile
from datetime import datetime, timezone

import pytest

from app.user_data_admin import UserDataManager, UserDataPaths
from app.userlist import JsonUserList


def test_inventory_and_export_are_identity_scoped(tmp_path):
    manager, paths = _seed_two_users(tmp_path)

    inventory = manager.inventory("111")

    assert inventory.episode_ids == ("episode-20260711-1",)
    assert inventory.userlist_records == 1
    assert inventory.ux_event_rows == 1
    assert inventory.provider_usage_record == 1
    assert len(inventory.affected_annotation_runs) == 1
    assert inventory.safe_summary()["delete_confirmation"] == "DELETE-111"

    output = tmp_path / "user-111.zip"
    result = manager.export("111", output)

    assert result["status"] == "exported"
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        rendered = "\n".join(
            archive.read(name).decode("utf-8")
            for name in names
            if name.endswith((".json", ".jsonl"))
        )
    assert "artifacts/episodes/episode-20260711-1.json" in names
    assert "artifacts/runtime_sessions/chat-111.json" in names
    assert "artifacts/runtime_sessions/review/chat-111.json" in names
    assert "derived/run-test/annotations.jsonl" in names
    assert "user-one-private" in rendered
    assert "user-two-private" not in rendered
    assert "telegram-chat-222" not in rendered


def test_delete_requires_exact_confirmation_and_preserves_other_user(tmp_path):
    manager, paths = _seed_two_users(tmp_path)

    with pytest.raises(ValueError, match="DELETE-111"):
        manager.delete("111", confirmation="yes")
    assert (paths.episode_dir / "episode-20260711-1.json").exists()

    result = manager.delete("111", confirmation="DELETE-111")

    assert result["status"] == "deleted"
    assert result["verified"] is True
    assert not (paths.episode_dir / "episode-20260711-1.json").exists()
    assert (paths.episode_dir / "episode-20260711-2.json").exists()
    assert not (paths.annotation_run_root / "run-test").exists()
    assert not (paths.reports_dir / "all.md").exists()
    assert not (paths.exports_dir / "all.json").exists()
    assert not (paths.backups_dir / "backup.json").exists()
    assert set(JsonUserList(paths.userlist_path).load()) == {"222"}
    ux_rows = _read_jsonl(paths.ux_event_log)
    assert [row["user_id"] for row in ux_rows] == ["222"]
    assert set(json.loads(paths.provider_usage_state.read_text())["users"]) == {"222"}
    assert manager.verify("111")["verified"] is True


def test_delete_preview_does_not_mutate_data(tmp_path):
    manager, paths = _seed_two_users(tmp_path)

    preview = manager.inventory("111").safe_summary()

    assert preview["has_data"] is True
    assert (paths.episode_dir / "episode-20260711-1.json").exists()
    assert JsonUserList(paths.userlist_path).records_for_identity("111")


def test_inventory_rejects_non_numeric_identity(tmp_path):
    manager = UserDataManager(_paths(tmp_path / "data"))

    with pytest.raises(ValueError, match="numeric"):
        manager.inventory("../../other-user")


def _seed_two_users(tmp_path):
    paths = _paths(tmp_path / "data")
    manager = UserDataManager(paths)
    now = datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc)
    users = JsonUserList(paths.userlist_path)
    users.upsert_waitlisted(111, "111", now=now, profile={"username": "one"})
    users.upsert_waitlisted(222, "222", now=now, profile={"username": "two"})

    _write_json(
        paths.episode_dir / "episode-20260711-1.json",
        {
            "id": "episode-20260711-1",
            "source": "telegram-chat:111",
            "observed": {"situation": {"value": "user-one-private"}},
        },
    )
    _write_json(
        paths.episode_dir / "episode-20260711-2.json",
        {
            "id": "episode-20260711-2",
            "source": "telegram-chat:222",
            "observed": {"situation": {"value": "user-two-private"}},
        },
    )
    _write_json(paths.runtime_session_dir / "chat-111.json", {"chat_id": 111})
    _write_json(
        paths.runtime_session_dir / "review" / "chat-111.json",
        {"chat_id": 111},
    )
    _write_json(
        paths.capture_artifact_dir / "telegram-chat-111" / "capture-111.json",
        {"chat_id": 111, "text": "user-one-private"},
    )
    _write_json(
        paths.capture_artifact_dir / "telegram-chat-222" / "capture-222.json",
        {"chat_id": 222, "text": "user-two-private"},
    )
    _write_jsonl(
        paths.ux_event_log,
        [
            {"event_type": "update_received", "user_id": "111", "chat_id": 111},
            {"event_type": "update_received", "user_id": "222", "chat_id": 222},
        ],
    )
    _write_json(
        paths.provider_usage_state,
        {
            "schema_version": "m3.provider_usage.v1",
            "day": "2026-07-11",
            "users": {
                "111": {"capture_calls": 1, "profile_calls": 2, "tokens": 30},
                "222": {"capture_calls": 2, "profile_calls": 1, "tokens": 40},
            },
            "global": {
                "calls": 6,
                "prompt_tokens": 40,
                "completion_tokens": 30,
                "total_tokens": 70,
            },
            "circuit": {"consecutive_failures": 0, "opened_at": None},
        },
    )
    _write_jsonl(
        paths.journal_log,
        [
            {"event_type": "capture", "refs": {"chat_id": 111}},
            {"event_type": "capture", "refs": {"chat_id": 222}},
        ],
    )
    run_dir = paths.annotation_run_root / "run-test"
    _write_jsonl(
        run_dir / "annotations.jsonl",
        [
            {
                "episode_id": "episode-20260711-1",
                "derived": {"text": "user-one-private"},
            },
            {
                "episode_id": "episode-20260711-2",
                "derived": {"text": "user-two-private"},
            },
        ],
    )
    _write_json(run_dir / "manifest.json", {"run_id": "run-test"})
    _write_text(paths.reports_dir / "all.md", "shared report")
    _write_json(paths.exports_dir / "all.json", {"shared": True})
    _write_json(paths.backups_dir / "backup.json", {"shared": True})
    return manager, paths


def _paths(root):
    return UserDataPaths(
        episode_dir=root / "episodes",
        runtime_session_dir=root / "runtime-sessions",
        runtime_flow_dir=root / "runtime-flows",
        userlist_path=root / "userlist" / "users.json",
        ux_event_log=root / "ux-events" / "events.jsonl",
        journal_log=root / "journal" / "events.jsonl",
        provider_usage_state=root / "provider-usage" / "state.json",
        annotation_run_root=root / "annotation-runs",
        intake_transcript_dir=root / "intake-transcripts",
        capture_artifact_dir=root / "capture-artifacts",
        capture_extraction_dir=root / "capture-extractions",
        capture_debug_dir=root / "capture-debug",
        reports_dir=root / "reports",
        exports_dir=root / "exports",
        backups_dir=root / "backups",
    )


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

from datetime import datetime, timezone

from app.userlist import APPROVED, PAUSED, WAITLISTED, JsonUserList


def test_userlist_creates_waitlisted_user(tmp_path):
    userlist = JsonUserList(tmp_path / "users.json")
    now = datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc)

    result = userlist.upsert_waitlisted(
        456,
        "456",
        now=now,
        profile={
            "username": "tester",
            "first_name": "Test",
            "last_name": "",
            "language_code": "en",
        },
    )

    assert result.created is True
    assert userlist.load() == {
        "456": {
            "chat_id": 456,
            "user_id": "456",
            "status": WAITLISTED,
            "first_seen_at": "2026-05-07T10:00:00Z",
            "last_seen_at": "2026-05-07T10:00:00Z",
            "username": "tester",
            "first_name": "Test",
            "language_code": "en",
        }
    }


def test_userlist_repeated_waitlist_updates_last_seen_only(tmp_path):
    userlist = JsonUserList(tmp_path / "users.json")
    first = datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc)
    second = datetime(2026, 5, 7, 11, 0, tzinfo=timezone.utc)

    userlist.upsert_waitlisted(456, "456", now=first)
    result = userlist.upsert_waitlisted(456, "456", now=second)

    assert result.created is False
    assert userlist.load()["456"]["first_seen_at"] == "2026-05-07T10:00:00Z"
    assert userlist.load()["456"]["last_seen_at"] == "2026-05-07T11:00:00Z"
    assert len(userlist.load()) == 1


def test_userlist_approve_and_pause_persist_decisions(tmp_path):
    userlist = JsonUserList(tmp_path / "users.json")
    first = datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc)
    approved = datetime(2026, 5, 7, 11, 0, tzinfo=timezone.utc)
    paused = datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc)

    userlist.upsert_waitlisted(456, "456", now=first)
    userlist.approve(456, decided_by="123", now=approved)

    assert userlist.is_approved(456) is True
    assert userlist.load()["456"]["status"] == APPROVED
    assert userlist.load()["456"]["approved_at"] == "2026-05-07T11:00:00Z"
    assert userlist.load()["456"]["decided_by"] == "123"

    userlist.pause(456, decided_by="123", now=paused)

    assert userlist.is_approved(456) is False
    assert userlist.load()["456"]["status"] == PAUSED
    assert userlist.load()["456"]["paused_at"] == "2026-05-07T12:00:00Z"


def test_userlist_records_versioned_adult_consent(tmp_path):
    userlist = JsonUserList(tmp_path / "users.json")
    now = datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc)
    userlist.approve(456, decided_by="123", now=now)

    assert userlist.has_current_consent(456, "beta-1") is False
    userlist.accept_consent(456, notice_version="beta-1", now=now)

    assert userlist.has_current_consent(456, "beta-1") is True
    assert userlist.has_current_consent(456, "beta-2") is False
    assert userlist.load()["456"]["consent"] == {
        "status": "accepted",
        "notice_version": "beta-1",
        "adult_confirmed": True,
        "accepted_at": "2026-05-07T10:00:00Z",
    }


def test_userlist_decline_and_identity_deletion(tmp_path):
    userlist = JsonUserList(tmp_path / "users.json")
    now = datetime(2026, 5, 7, 10, 0, tzinfo=timezone.utc)
    userlist.upsert_waitlisted(456, "user-1", now=now)
    userlist.upsert_waitlisted(789, "user-2", now=now)
    userlist.decline_consent(456, notice_version="beta-1", now=now)

    assert userlist.has_current_consent(456, "beta-1") is False
    assert set(userlist.records_for_identity("user-1")) == {"456"}
    assert userlist.delete_identity("user-1") == 1
    assert set(userlist.load()) == {"789"}

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.journal import JournalLog
from app.provider_guard import (
    ProviderGuard,
    ProviderGuardBlocked,
    ProviderLimits,
    ProviderUsageStore,
    usage_counts,
)


NOW = datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc)


def test_daily_user_limit_persists_across_store_instances(tmp_path):
    path = tmp_path / "usage.json"
    limits = _limits(capture_daily_per_user=1)
    ProviderUsageStore(path, limits).consume("111", "capture", now=NOW)

    restarted = ProviderUsageStore(path, limits)

    with pytest.raises(ProviderGuardBlocked) as exc:
        restarted.check("111", "capture", now=NOW)
    assert exc.value.code == "user_daily_limit"
    restarted.check("111", "capture", now=NOW + timedelta(days=1))


def test_token_budget_and_usage_state_store_counts_only(tmp_path):
    path = tmp_path / "usage.json"
    store = ProviderUsageStore(path, _limits(daily_token_budget=10))
    store.consume("111", "profile", now=NOW)
    store.record_usage(
        "111",
        "profile",
        prompt_tokens=6,
        completion_tokens=4,
        total_tokens=10,
        now=NOW,
    )

    with pytest.raises(ProviderGuardBlocked) as exc:
        store.check("222", "capture", now=NOW)

    assert exc.value.code == "daily_token_budget_exhausted"
    rendered = path.read_text(encoding="utf-8")
    state = json.loads(rendered)
    assert state["global"]["total_tokens"] == 10
    assert set(state["users"]["111"]) == {
        "capture_calls",
        "profile_calls",
        "tokens",
    }


def test_circuit_opens_and_recovers_after_cooldown(tmp_path):
    store = ProviderUsageStore(
        tmp_path / "usage.json",
        _limits(circuit_failure_threshold=2, circuit_cooldown_sec=30),
    )
    store.record_failure("provider_timeout", now=NOW)
    store.record_failure("provider_error", now=NOW)

    with pytest.raises(ProviderGuardBlocked) as exc:
        store.check("111", "capture", now=NOW)
    assert exc.value.code == "circuit_open"
    store.check("111", "capture", now=NOW + timedelta(seconds=31))


def test_guard_retries_retryable_result_once(tmp_path):
    guard = ProviderGuard(
        ProviderUsageStore(
            tmp_path / "usage.json",
            _limits(max_retries=1, retry_backoff_sec=0),
        )
    )
    attempts = 0

    async def scenario():
        nonlocal attempts

        async def operation():
            nonlocal attempts
            attempts += 1
            return SimpleNamespace(
                failure_code="provider_timeout" if attempts == 1 else None
            )

        return await guard.call(
            "111",
            "capture",
            operation,
            lambda result: result.failure_code,
        )

    result = asyncio.run(scenario())

    assert result.failure_code is None
    assert attempts == 2
    snapshot = guard.store.snapshot()
    assert snapshot["global"]["calls"] == 2


def test_guard_allows_other_user_while_same_user_waits(tmp_path):
    guard = ProviderGuard(
        ProviderUsageStore(
            tmp_path / "usage.json",
            _limits(max_in_flight=2, queue_timeout_sec=1),
        )
    )

    async def scenario():
        first = await guard.acquire("111", "capture")
        same_task = asyncio.create_task(guard.acquire("111", "profile"))
        other_task = asyncio.create_task(guard.acquire("222", "capture"))
        await asyncio.sleep(0.03)
        assert not same_task.done()
        assert other_task.done()
        other = await other_task
        other.succeed()
        first.succeed()
        same = await same_task
        same.succeed()

    asyncio.run(scenario())


def test_queue_timeout_is_journaled_without_content(tmp_path):
    journal_path = tmp_path / "journal.jsonl"
    guard = ProviderGuard(
        ProviderUsageStore(
            tmp_path / "usage.json",
            _limits(max_in_flight=1, queue_timeout_sec=0.01),
        ),
        journal_log=JournalLog(journal_path),
    )

    async def scenario():
        first = await guard.acquire("111", "capture")
        with pytest.raises(ProviderGuardBlocked) as exc:
            await guard.acquire("222", "profile")
        assert exc.value.code == "queue_timeout"
        first.succeed()

    asyncio.run(scenario())

    event = json.loads(journal_path.read_text(encoding="utf-8"))
    assert event["reason"] == "queue_timeout"
    assert event["refs"] == {"user_id": "222"}
    assert "prompt" not in journal_path.read_text(encoding="utf-8")


def test_usage_counts_supports_chat_and_responses_shapes():
    assert usage_counts(
        SimpleNamespace(
            usage=SimpleNamespace(
                prompt_tokens=3,
                completion_tokens=2,
                total_tokens=5,
            )
        )
    ) == (3, 2, 5)
    assert usage_counts(
        SimpleNamespace(
            usage=SimpleNamespace(input_tokens=4, output_tokens=1)
        )
    ) == (4, 1, 5)


def test_invalid_usage_state_blocks_paid_call_safely(tmp_path):
    path = tmp_path / "usage.json"
    path.write_text("not-json", encoding="utf-8")
    guard = ProviderGuard(ProviderUsageStore(path, _limits()))

    async def scenario():
        with pytest.raises(ProviderGuardBlocked) as exc:
            await guard.acquire("111", "capture")
        assert exc.value.code == "usage_state_unavailable"

    asyncio.run(scenario())


def test_usage_telemetry_failure_does_not_raise(tmp_path, monkeypatch):
    journal_path = tmp_path / "journal.jsonl"
    guard = ProviderGuard(
        ProviderUsageStore(tmp_path / "usage.json", _limits()),
        journal_log=JournalLog(journal_path),
    )

    def fail_record_usage(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(guard.store, "record_usage", fail_record_usage)

    guard.record_usage(
        "111",
        "profile",
        prompt_tokens=3,
        completion_tokens=2,
        total_tokens=5,
    )

    event = json.loads(journal_path.read_text(encoding="utf-8"))
    assert event["failure_code"] == "usage_state_write_failed"
    assert event["details"] == {
        "exception_type": "OSError",
        "surface": "profile",
    }


def _limits(**overrides):
    values = {
        "capture_daily_per_user": 10,
        "profile_daily_per_user": 10,
        "daily_token_budget": 1000,
        "max_in_flight": 2,
        "queue_timeout_sec": 0.2,
        "circuit_failure_threshold": 10,
        "circuit_cooldown_sec": 30,
        "max_retries": 0,
        "retry_backoff_sec": 0,
    }
    values.update(overrides)
    return ProviderLimits(**values)

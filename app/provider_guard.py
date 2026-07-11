from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

from app.journal import JournalLog, journal_event, record_journal_event
from app.runtime_storage import atomic_write_json, locked_path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency guard
    load_dotenv = None


SCHEMA_VERSION = "m3.provider_usage.v1"
RETRYABLE_FAILURES = frozenset(
    {"provider_timeout", "provider_error", "rate_limited", "queue_timeout"}
)
T = TypeVar("T")


class ProviderGuardBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ProviderLimits:
    capture_daily_per_user: int = 20
    profile_daily_per_user: int = 20
    daily_token_budget: int = 200_000
    max_in_flight: int = 2
    queue_timeout_sec: float = 10.0
    circuit_failure_threshold: int = 3
    circuit_cooldown_sec: int = 300
    max_retries: int = 1
    retry_backoff_sec: float = 0.5

    def __post_init__(self) -> None:
        positive = {
            "capture_daily_per_user": self.capture_daily_per_user,
            "profile_daily_per_user": self.profile_daily_per_user,
            "daily_token_budget": self.daily_token_budget,
            "max_in_flight": self.max_in_flight,
            "queue_timeout_sec": self.queue_timeout_sec,
            "circuit_failure_threshold": self.circuit_failure_threshold,
            "circuit_cooldown_sec": self.circuit_cooldown_sec,
        }
        if any(value <= 0 for value in positive.values()):
            raise ValueError("provider limits must be positive")
        if self.max_retries < 0 or self.retry_backoff_sec < 0:
            raise ValueError("provider retry settings cannot be negative")


class ProviderUsageStore:
    def __init__(self, path: Path, limits: ProviderLimits) -> None:
        self.path = path
        self.limits = limits

    def check(
        self,
        user_id: str,
        surface: str,
        *,
        now: datetime | None = None,
    ) -> None:
        timestamp = now or _utc_now()
        with locked_path(self.path):
            state = self._load_current(timestamp)
            self._check_state(state, user_id, surface, timestamp)

    def consume(
        self,
        user_id: str,
        surface: str,
        *,
        now: datetime | None = None,
    ) -> None:
        timestamp = now or _utc_now()
        with locked_path(self.path):
            state = self._load_current(timestamp)
            self._check_state(state, user_id, surface, timestamp)
            user = state["users"].setdefault(
                str(user_id),
                {"capture_calls": 0, "profile_calls": 0, "tokens": 0},
            )
            user[f"{surface}_calls"] += 1
            state["global"]["calls"] += 1
            self._save(state)

    def record_usage(
        self,
        user_id: str,
        surface: str,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        now: datetime | None = None,
    ) -> None:
        timestamp = now or _utc_now()
        prompt = max(0, int(prompt_tokens))
        completion = max(0, int(completion_tokens))
        total = max(0, int(total_tokens)) or prompt + completion
        with locked_path(self.path):
            state = self._load_current(timestamp)
            user = state["users"].setdefault(
                str(user_id),
                {"capture_calls": 0, "profile_calls": 0, "tokens": 0},
            )
            user["tokens"] += total
            state["global"]["prompt_tokens"] += prompt
            state["global"]["completion_tokens"] += completion
            state["global"]["total_tokens"] += total
            self._save(state)

    def record_success(self, *, now: datetime | None = None) -> None:
        timestamp = now or _utc_now()
        with locked_path(self.path):
            state = self._load_current(timestamp)
            state["circuit"] = {"consecutive_failures": 0, "opened_at": None}
            self._save(state)

    def record_failure(self, failure_code: str, *, now: datetime | None = None) -> None:
        if failure_code not in RETRYABLE_FAILURES:
            return
        timestamp = now or _utc_now()
        with locked_path(self.path):
            state = self._load_current(timestamp)
            circuit = state["circuit"]
            circuit["consecutive_failures"] += 1
            if (
                circuit["consecutive_failures"]
                >= self.limits.circuit_failure_threshold
            ):
                circuit["opened_at"] = timestamp.isoformat()
            self._save(state)

    def snapshot(self, *, now: datetime | None = None) -> dict[str, Any]:
        with locked_path(self.path):
            return self._load_current(now or _utc_now())

    def _check_state(
        self,
        state: dict[str, Any],
        user_id: str,
        surface: str,
        now: datetime,
    ) -> None:
        if surface not in {"capture", "profile"}:
            raise ValueError("provider surface must be capture or profile")
        circuit = state["circuit"]
        opened_at = circuit.get("opened_at")
        if opened_at:
            opened = datetime.fromisoformat(str(opened_at))
            if now < opened + timedelta(seconds=self.limits.circuit_cooldown_sec):
                raise ProviderGuardBlocked("circuit_open")
            circuit.update({"consecutive_failures": 0, "opened_at": None})
        if state["global"]["total_tokens"] >= self.limits.daily_token_budget:
            raise ProviderGuardBlocked("daily_token_budget_exhausted")
        user = state["users"].get(str(user_id), {})
        limit = (
            self.limits.capture_daily_per_user
            if surface == "capture"
            else self.limits.profile_daily_per_user
        )
        if int(user.get(f"{surface}_calls", 0)) >= limit:
            raise ProviderGuardBlocked("user_daily_limit")

    def _load_current(self, now: datetime) -> dict[str, Any]:
        day = now.astimezone(timezone.utc).date().isoformat()
        if not self.path.exists():
            return _empty_state(day)
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("invalid provider usage state")
        if value.get("day") != day:
            return _empty_state(day)
        return value

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_json(self.path, state, sort_keys=True, lock=False)


class ProviderReservation:
    def __init__(
        self,
        guard: ProviderGuard,
        *,
        user_id: str,
        surface: str,
        user_semaphore: asyncio.Semaphore,
    ) -> None:
        self.guard = guard
        self.user_id = user_id
        self.surface = surface
        self.user_semaphore = user_semaphore
        self.closed = False

    def succeed(self) -> None:
        if self.closed:
            return
        self.guard.store.record_success()
        self._release()

    def fail(self, failure_code: str) -> None:
        if self.closed:
            return
        self.guard.store.record_failure(failure_code)
        self._release()

    def _release(self) -> None:
        self.closed = True
        self.guard._global_semaphore.release()
        self.user_semaphore.release()


class ProviderGuard:
    def __init__(
        self,
        store: ProviderUsageStore,
        *,
        journal_log: JournalLog | None = None,
    ) -> None:
        self.store = store
        self.limits = store.limits
        self.journal_log = journal_log
        self._global_semaphore = asyncio.Semaphore(self.limits.max_in_flight)
        self._user_semaphores: dict[str, asyncio.Semaphore] = {}

    async def acquire(self, user_id: str, surface: str) -> ProviderReservation:
        normalized_user_id = str(user_id)
        try:
            self.store.check(normalized_user_id, surface)
            user_semaphore = self._user_semaphores.setdefault(
                normalized_user_id, asyncio.Semaphore(1)
            )
            await asyncio.wait_for(
                user_semaphore.acquire(),
                timeout=self.limits.queue_timeout_sec,
            )
            try:
                await asyncio.wait_for(
                    self._global_semaphore.acquire(),
                    timeout=self.limits.queue_timeout_sec,
                )
            except BaseException:
                user_semaphore.release()
                raise
            try:
                self.store.consume(normalized_user_id, surface)
            except BaseException:
                self._global_semaphore.release()
                user_semaphore.release()
                raise
            return ProviderReservation(
                self,
                user_id=normalized_user_id,
                surface=surface,
                user_semaphore=user_semaphore,
            )
        except TimeoutError as exc:
            self._record_blocked(normalized_user_id, surface, "queue_timeout")
            raise ProviderGuardBlocked("queue_timeout") from exc
        except ProviderGuardBlocked as exc:
            self._record_blocked(normalized_user_id, surface, exc.code)
            raise
        except (KeyError, OSError, TypeError, ValueError) as exc:
            code = "usage_state_unavailable"
            self._record_blocked(normalized_user_id, surface, code)
            raise ProviderGuardBlocked(code) from exc

    async def call(
        self,
        user_id: str,
        surface: str,
        operation: Callable[[], Awaitable[T]],
        failure_code: Callable[[T], str | None],
    ) -> T:
        last_result: T | None = None
        for attempt in range(self.limits.max_retries + 1):
            reservation = await self.acquire(user_id, surface)
            try:
                result = await operation()
            except BaseException:
                reservation.fail("provider_error")
                raise
            code = failure_code(result)
            if code is None:
                reservation.succeed()
                return result
            reservation.fail(code)
            last_result = result
            if code not in RETRYABLE_FAILURES or attempt >= self.limits.max_retries:
                return result
            await asyncio.sleep(self.limits.retry_backoff_sec * (2**attempt))
        if last_result is None:  # pragma: no cover - loop always executes
            raise RuntimeError("provider call did not execute")
        return last_result

    def record_usage(
        self,
        user_id: str,
        surface: str,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        try:
            self.store.record_usage(
                str(user_id),
                surface,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
        except (KeyError, OSError, TypeError, ValueError) as exc:
            record_journal_event(
                self.journal_log,
                journal_event(
                    component="provider_guard",
                    event_type="provider_usage.record_failed",
                    stage="failed",
                    level="error",
                    refs={"user_id": str(user_id)},
                    failure_code="usage_state_write_failed",
                    details={
                        "surface": surface,
                        "exception_type": type(exc).__name__,
                    },
                ),
            )

    def _record_blocked(self, user_id: str, surface: str, code: str) -> None:
        record_journal_event(
            self.journal_log,
            journal_event(
                component="provider_guard",
                event_type="provider_call.blocked",
                stage="blocked",
                level="warning",
                refs={"user_id": user_id},
                reason=code,
                details={"surface": surface},
            ),
        )


def usage_counts(response: Any) -> tuple[int, int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0
    prompt = int(
        getattr(usage, "prompt_tokens", None)
        or getattr(usage, "input_tokens", None)
        or 0
    )
    completion = int(
        getattr(usage, "completion_tokens", None)
        or getattr(usage, "output_tokens", None)
        or 0
    )
    total = int(getattr(usage, "total_tokens", None) or prompt + completion)
    return prompt, completion, total


def api_failure_code(error: Exception) -> str:
    class_name = type(error).__name__.lower()
    status_code = getattr(error, "status_code", None)
    if status_code == 429 or "ratelimit" in class_name or "rate_limit" in class_name:
        return "rate_limited"
    return "provider_error"


def provider_guard_for_settings(
    settings: Any,
    *,
    journal_log: JournalLog | None = None,
) -> ProviderGuard:
    limits = ProviderLimits(
        capture_daily_per_user=getattr(
            settings, "provider_capture_daily_limit", 20
        ),
        profile_daily_per_user=getattr(settings, "provider_profile_daily_limit", 20),
        daily_token_budget=getattr(settings, "provider_daily_token_budget", 200_000),
        max_in_flight=getattr(settings, "provider_max_in_flight", 2),
        queue_timeout_sec=getattr(settings, "provider_queue_timeout_sec", 10.0),
        circuit_failure_threshold=getattr(
            settings, "provider_circuit_failure_threshold", 3
        ),
        circuit_cooldown_sec=getattr(
            settings, "provider_circuit_cooldown_sec", 300
        ),
        max_retries=getattr(settings, "provider_max_retries", 1),
        retry_backoff_sec=getattr(settings, "provider_retry_backoff_sec", 0.5),
    )
    return ProviderGuard(
        ProviderUsageStore(
            Path(
                getattr(
                    settings,
                    "provider_usage_state",
                    Path("data/provider-usage/state.json"),
                )
            ),
            limits,
        ),
        journal_log=journal_log,
    )


def _empty_state(day: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "day": day,
        "users": {},
        "global": {
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "circuit": {"consecutive_failures": 0, "opened_at": None},
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def main() -> None:
    if load_dotenv is not None:
        load_dotenv()
    parser = argparse.ArgumentParser(
        description="Print private count-only provider usage state."
    )
    parser.add_argument(
        "--state",
        default=os.environ.get(
            "M3_PROVIDER_USAGE_STATE", "data/provider-usage/state.json"
        ),
    )
    args = parser.parse_args()
    state = ProviderUsageStore(Path(args.state), ProviderLimits()).snapshot()
    print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

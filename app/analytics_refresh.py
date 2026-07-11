from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.analytics_loader import selected_annotation_run
from app.annotation_producer import AnnotationProducerSummary, produce_annotation_run
from app.blocking_runtime import run_blocking
from app.journal import JournalLog, journal_event, record_journal_event
from app.runtime_storage import file_lock


FRESHNESS_EMPTY = "empty"
FRESHNESS_READY = "ready"
FRESHNESS_STALE = "stale"
FRESHNESS_REFRESHING = "refreshing"
FRESHNESS_BLOCKED = "blocked"


@dataclass(frozen=True)
class AnalyticsFreshness:
    state: str
    observed_count: int
    annotation_row_count: int
    annotated_count: int
    pending_count: int
    pending_episode_ids: tuple[str, ...]
    selected_run_id: str | None = None
    selected_run_path: str | None = None
    blocker: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "observed_count": self.observed_count,
            "annotation_row_count": self.annotation_row_count,
            "annotated_count": self.annotated_count,
            "pending_count": self.pending_count,
            "pending_episode_ids": list(self.pending_episode_ids),
            "selected_run_id": self.selected_run_id,
            "selected_run_path": self.selected_run_path,
            "blocker": self.blocker,
        }


@dataclass(frozen=True)
class AnalyticsRefreshResult:
    action: str
    freshness: AnalyticsFreshness
    summary: AnnotationProducerSummary | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "freshness": self.freshness.as_dict(),
            "summary": self.summary.as_dict() if self.summary is not None else None,
        }


def inspect_analytics_freshness(
    episode_dir: Path,
    annotation_run_root: Path,
    *,
    annotation_run_dir: Path | None = None,
) -> AnalyticsFreshness:
    try:
        episode_ids = _episode_ids(episode_dir)
        if not episode_ids:
            return AnalyticsFreshness(
                state=FRESHNESS_EMPTY,
                observed_count=0,
                annotation_row_count=0,
                annotated_count=0,
                pending_count=0,
                pending_episode_ids=(),
            )
        selected = selected_annotation_run(
            episode_dir,
            annotation_run_dir=annotation_run_dir,
            annotation_run_root=annotation_run_root,
            episode_ids=episode_ids,
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return AnalyticsFreshness(
            state=FRESHNESS_BLOCKED,
            observed_count=0,
            annotation_row_count=0,
            annotated_count=0,
            pending_count=0,
            pending_episode_ids=(),
            blocker="invalid_episode_or_annotation_run",
        )

    if selected is None:
        pending = tuple(sorted(episode_ids))
        return AnalyticsFreshness(
            state=FRESHNESS_STALE,
            observed_count=len(episode_ids),
            annotation_row_count=0,
            annotated_count=0,
            pending_count=len(pending),
            pending_episode_ids=pending,
        )

    row_ids = set(selected.derived_by_episode_id)
    annotated = episode_ids & row_ids
    pending = tuple(sorted(episode_ids - row_ids))
    return AnalyticsFreshness(
        state=FRESHNESS_READY if not pending else FRESHNESS_STALE,
        observed_count=len(episode_ids),
        annotation_row_count=len(row_ids),
        annotated_count=len(annotated),
        pending_count=len(pending),
        pending_episode_ids=pending,
        selected_run_id=selected.manifest.annotation_run_id,
        selected_run_path=selected.path.as_posix(),
    )


def refresh_analytics_once(
    episode_dir: Path,
    annotation_run_root: Path,
    *,
    annotation_run_dir: Path | None = None,
    journal_log: JournalLog | Path | None = None,
) -> AnalyticsRefreshResult:
    with file_lock(annotation_run_root / ".analytics-refresh.lock"):
        before = inspect_analytics_freshness(
            episode_dir,
            annotation_run_root,
            annotation_run_dir=annotation_run_dir,
        )
        if before.state == FRESHNESS_BLOCKED:
            return AnalyticsRefreshResult("blocked", before)
        if before.state == FRESHNESS_EMPTY:
            return AnalyticsRefreshResult("no_op_empty", before)
        if before.state == FRESHNESS_READY:
            return AnalyticsRefreshResult("no_op_ready", before)
        if annotation_run_dir is not None:
            return AnalyticsRefreshResult(
                "blocked",
                replace(
                    before,
                    state=FRESHNESS_BLOCKED,
                    blocker="explicit_annotation_run_is_pinned",
                ),
            )

        base_run_dir = (
            Path(before.selected_run_path) if before.selected_run_path is not None else None
        )
        action = "missing_only" if base_run_dir is not None else "full_snapshot"
        try:
            summary = produce_annotation_run(
                episode_dir,
                annotation_run_root,
                run_id=_automatic_run_id(),
                only_missing=base_run_dir is not None,
                annotation_run_dir=base_run_dir,
                annotation_run_root=annotation_run_root,
                write=True,
                journal_log=journal_log,
            )
        except Exception:
            return AnalyticsRefreshResult(
                "blocked",
                replace(
                    before,
                    state=FRESHNESS_BLOCKED,
                    blocker="annotation_refresh_failed",
                ),
            )

        after = inspect_analytics_freshness(episode_dir, annotation_run_root)
        if after.state == FRESHNESS_BLOCKED:
            return AnalyticsRefreshResult("blocked", after, summary)
        if summary.snapshot_written and after.selected_run_id != summary.run_id:
            return AnalyticsRefreshResult(
                "blocked",
                replace(
                    after,
                    state=FRESHNESS_BLOCKED,
                    blocker="published_run_not_selected",
                ),
                summary,
            )
        if after.state == FRESHNESS_STALE and summary.generated_count == 0:
            return AnalyticsRefreshResult(
                "blocked",
                replace(
                    after,
                    state=FRESHNESS_BLOCKED,
                    blocker="annotation_refresh_made_no_progress",
                ),
                summary,
            )
        return AnalyticsRefreshResult(action, after, summary)


class AnalyticsRefreshCoordinator:
    def __init__(
        self,
        episode_dir: Path,
        annotation_run_root: Path,
        *,
        annotation_run_dir: Path | None = None,
        journal_log: JournalLog | Path | None = None,
        runner: Callable[..., Awaitable[Any]] = run_blocking,
        refresher: Callable[..., AnalyticsRefreshResult] = refresh_analytics_once,
    ) -> None:
        self.episode_dir = episode_dir
        self.annotation_run_root = annotation_run_root
        self.annotation_run_dir = annotation_run_dir
        self.journal_log = journal_log
        self.runner = runner
        self.refresher = refresher
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._generation = 0
        self._last_freshness: AnalyticsFreshness | None = None

    async def start(self) -> AnalyticsFreshness:
        freshness = await self.runner(
            inspect_analytics_freshness,
            self.episode_dir,
            self.annotation_run_root,
            annotation_run_dir=self.annotation_run_dir,
        )
        self._last_freshness = freshness
        if freshness.state == FRESHNESS_STALE:
            await self.enqueue(reason="startup_recovery")
        elif freshness.state == FRESHNESS_BLOCKED:
            self._record("analytics_refresh.blocked", "blocked", freshness)
        else:
            self._record("analytics_refresh.checked", "checked", freshness)
        return freshness

    async def enqueue(
        self,
        episode_id: str | None = None,
        *,
        reason: str = "episode_saved",
    ) -> None:
        async with self._lock:
            self._generation += 1
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._worker())
        refs = {"episode_id": episode_id} if episode_id else None
        record_journal_event(
            self.journal_log,
            journal_event(
                component="analytics_refresh",
                event_type="analytics_refresh.queued",
                stage="started",
                refs=refs,
                details={"reason": reason},
            ),
        )

    async def refresh_now(self) -> AnalyticsFreshness:
        await self.enqueue(reason="operator_refresh")
        return await self.wait_idle()

    async def wait_idle(self) -> AnalyticsFreshness:
        while True:
            async with self._lock:
                task = self._task
            if task is None:
                break
            await asyncio.shield(task)
        if self._last_freshness is None:
            return await self.status()
        return self._last_freshness

    async def status(self) -> AnalyticsFreshness:
        freshness = await self.runner(
            inspect_analytics_freshness,
            self.episode_dir,
            self.annotation_run_root,
            annotation_run_dir=self.annotation_run_dir,
        )
        async with self._lock:
            active = self._task is not None and not self._task.done()
        if active and freshness.state == FRESHNESS_STALE:
            return replace(freshness, state=FRESHNESS_REFRESHING)
        if (
            not active
            and freshness.state == FRESHNESS_STALE
            and self._last_freshness is not None
            and self._last_freshness.state == FRESHNESS_BLOCKED
        ):
            return replace(
                freshness,
                state=FRESHNESS_BLOCKED,
                blocker=self._last_freshness.blocker,
            )
        return freshness

    async def _worker(self) -> None:
        await asyncio.sleep(0)
        while True:
            async with self._lock:
                generation = self._generation
            self._record(
                "analytics_refresh.started",
                "started",
                self._last_freshness,
            )
            try:
                result = await self.runner(
                    self.refresher,
                    self.episode_dir,
                    self.annotation_run_root,
                    annotation_run_dir=self.annotation_run_dir,
                    journal_log=self.journal_log,
                )
            except Exception:
                current = await self.runner(
                    inspect_analytics_freshness,
                    self.episode_dir,
                    self.annotation_run_root,
                    annotation_run_dir=self.annotation_run_dir,
                )
                result = AnalyticsRefreshResult(
                    "blocked",
                    replace(
                        current,
                        state=FRESHNESS_BLOCKED,
                        blocker="analytics_refresh_worker_failed",
                    ),
                )
            self._last_freshness = result.freshness
            self._record_result(result)

            async with self._lock:
                should_continue = (
                    result.freshness.state == FRESHNESS_STALE
                    or generation != self._generation
                )
                if result.freshness.state == FRESHNESS_BLOCKED:
                    should_continue = False
                if not should_continue:
                    if self._task is asyncio.current_task():
                        self._task = None
                    return

    def _record_result(self, result: AnalyticsRefreshResult) -> None:
        if result.freshness.state == FRESHNESS_BLOCKED:
            self._record("analytics_refresh.blocked", "blocked", result.freshness)
        elif result.summary is not None and result.summary.snapshot_written:
            self._record(
                "analytics_refresh.published",
                "succeeded",
                result.freshness,
                run_id=result.summary.run_id,
                action=result.action,
            )
        else:
            self._record(
                "analytics_refresh.checked",
                "checked",
                result.freshness,
                action=result.action,
            )

    def _record(
        self,
        event_type: str,
        stage: str,
        freshness: AnalyticsFreshness | None,
        *,
        run_id: str | None = None,
        action: str | None = None,
    ) -> None:
        counts = None
        refs: dict[str, str] = {
            "episode_dir": self.episode_dir.as_posix(),
            "annotation_run_root": self.annotation_run_root.as_posix(),
        }
        details: dict[str, Any] = {}
        failure_code = None
        if freshness is not None:
            counts = {
                "observed_count": freshness.observed_count,
                "annotation_row_count": freshness.annotation_row_count,
                "pending_count": freshness.pending_count,
            }
            details["freshness"] = freshness.state
            failure_code = freshness.blocker
            if freshness.selected_run_path:
                refs["selected_run_path"] = freshness.selected_run_path
            if freshness.selected_run_id:
                details["selected_run_id"] = freshness.selected_run_id
        if action:
            details["action"] = action
        record_journal_event(
            self.journal_log,
            journal_event(
                component="analytics_refresh",
                event_type=event_type,
                stage=stage,
                level="error" if stage == "blocked" else "info",
                run_id=run_id,
                refs=refs,
                counts=counts,
                failure_code=failure_code,
                details=details or None,
            ),
        )


def _episode_ids(episode_dir: Path) -> set[str]:
    ids: set[str] = set()
    for path in sorted(episode_dir.glob("episode-*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"episode JSON must be an object: {path}")
        episode_id = value.get("id", value.get("episode_id"))
        if not isinstance(episode_id, str) or not episode_id:
            raise ValueError(f"episode id is required: {path}")
        if episode_id in ids:
            raise ValueError(f"duplicate episode id: {episode_id}")
        ids.add(episode_id)
    return ids


def _automatic_run_id() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("run-%Y%m%d-%H%M%S-deterministic-auto-%f")

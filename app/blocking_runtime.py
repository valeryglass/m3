from __future__ import annotations

import asyncio
from concurrent.futures import Future
from functools import partial
from queue import Full, Queue
from threading import Lock, Thread
from typing import Any, Callable


class BlockingWorkQueueFull(RuntimeError):
    pass


class DaemonWorkerPool:
    def __init__(self, *, max_workers: int, max_queue_size: int) -> None:
        if max_workers <= 0 or max_queue_size <= 0:
            raise ValueError("worker and queue limits must be positive")
        self._queue: Queue[tuple[Future[Any], Callable[[], Any]]] = Queue(
            maxsize=max_queue_size
        )
        self._threads = tuple(
            Thread(
                target=self._worker,
                name=f"m3-blocking-{index + 1}",
                daemon=True,
            )
            for index in range(max_workers)
        )
        for thread in self._threads:
            thread.start()

    def submit(self, function: Callable[[], Any]) -> Future[Any]:
        future: Future[Any] = Future()
        try:
            self._queue.put_nowait((future, function))
        except Full as exc:
            raise BlockingWorkQueueFull("blocking worker queue is full") from exc
        return future

    def _worker(self) -> None:
        while True:
            future, function = self._queue.get()
            try:
                if future.set_running_or_notify_cancel():
                    try:
                        future.set_result(function())
                    except BaseException as exc:
                        future.set_exception(exc)
            finally:
                self._queue.task_done()


_POOL_LOCK = Lock()
_BLOCKING_WORKERS: DaemonWorkerPool | None = None


async def run_blocking(
    function: Callable[..., Any],
    /,
    *args: Any,
    **kwargs: Any,
) -> Any:
    future = _blocking_workers().submit(partial(function, *args, **kwargs))
    try:
        while not future.done():
            await asyncio.sleep(0.01)
        return future.result()
    except asyncio.CancelledError:
        future.cancel()
        raise


def _blocking_workers() -> DaemonWorkerPool:
    global _BLOCKING_WORKERS
    with _POOL_LOCK:
        if _BLOCKING_WORKERS is None:
            _BLOCKING_WORKERS = DaemonWorkerPool(max_workers=4, max_queue_size=32)
        return _BLOCKING_WORKERS

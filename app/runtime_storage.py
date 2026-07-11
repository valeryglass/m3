from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Iterator

import fcntl


class LockUnavailableError(RuntimeError):
    pass


_LOCKS_GUARD = Lock()
_THREAD_LOCKS: dict[str, RLock] = {}


def atomic_write_json(
    path: Path,
    payload: Any,
    *,
    sort_keys: bool = False,
    lock: bool = True,
) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=sort_keys) + "\n",
        lock=lock,
    )


def atomic_write_text(path: Path, text: str, *, lock: bool = True) -> None:
    if lock:
        with locked_path(path):
            _atomic_write_text_unlocked(path, text)
        return
    _atomic_write_text_unlocked(path, text)


def append_jsonl(path: Path, payload: Any) -> None:
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    encoded = line.encode("utf-8")
    with locked_path(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            view = memoryview(encoded)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def locked_unlink(path: Path, *, missing_ok: bool = True) -> None:
    with locked_path(path):
        path.unlink(missing_ok=missing_ok)


@contextmanager
def locked_path(path: Path) -> Iterator[None]:
    with file_lock(_lock_path(path)):
        yield


@contextmanager
def file_lock(path: Path, *, blocking: bool = True) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    thread_lock = _thread_lock(path)
    acquired = thread_lock.acquire(blocking=blocking)
    if not acquired:
        raise LockUnavailableError(f"lock is already held: {path}")
    handle = None
    try:
        handle = path.open("a+", encoding="utf-8")
        operation = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(handle.fileno(), operation)
        except BlockingIOError as exc:
            raise LockUnavailableError(f"lock is already held: {path}") from exc
        yield
    finally:
        if handle is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
        thread_lock.release()


class ProcessLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._context = None

    def acquire(self) -> None:
        if self._context is not None:
            return
        context = file_lock(self.path, blocking=False)
        context.__enter__()
        try:
            self.path.write_text(str(os.getpid()) + "\n", encoding="utf-8")
        except BaseException:
            context.__exit__(None, None, None)
            raise
        self._context = context

    def release(self) -> None:
        if self._context is None:
            return
        context = self._context
        self._context = None
        context.__exit__(None, None, None)

    def __enter__(self) -> ProcessLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


def _atomic_write_text_unlocked(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _lock_path(path: Path) -> Path:
    return path.parent / f".{path.name}.lock"


def _thread_lock(path: Path) -> RLock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, RLock())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

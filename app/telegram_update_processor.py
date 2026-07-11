from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any

from telegram.ext import BaseUpdateProcessor


class PerChatUpdateProcessor(BaseUpdateProcessor):
    """Run different chats concurrently while preserving per-chat order."""

    def __init__(self, max_concurrent_updates: int = 8) -> None:
        super().__init__(max_concurrent_updates=max_concurrent_updates)
        self._chat_locks: dict[int | str, asyncio.Lock] = {}

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        self._chat_locks.clear()

    async def do_process_update(
        self,
        update: object,
        coroutine: Awaitable[Any],
    ) -> None:
        key = _update_chat_key(update)
        lock = self._chat_locks.setdefault(key, asyncio.Lock())
        async with lock:
            await coroutine


def _update_chat_key(update: object) -> int | str:
    chat = getattr(update, "effective_chat", None)
    chat_id = getattr(chat, "id", None)
    if chat_id is not None:
        return int(chat_id)
    update_id = getattr(update, "update_id", None)
    return f"update:{update_id}" if update_id is not None else "update:unknown"

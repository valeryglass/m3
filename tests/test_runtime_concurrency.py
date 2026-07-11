import asyncio
import json
from threading import Event, Thread
from types import SimpleNamespace

from app.blocking_runtime import run_blocking
from app.journal import JournalLog
from app.storage import JsonStorage
from app.telegram_bot import _record_telegram_error
from app.telegram_update_processor import PerChatUpdateProcessor


OBSERVED = {
    "situation": {"value": "s", "source_quote": "s"},
    "behavior": {"value": "b", "source_quote": "b"},
    "short_term_consequence": {"value": "st", "source_quote": "st"},
    "long_term_consequence": {"value": "lt", "source_quote": "lt"},
    "automatic_thought": {"value": "at", "source_quote": "at"},
    "emotion": {"value": "e", "source_quote": "e"},
    "physical": {"value": "p", "source_quote": "p"},
}


def test_concurrent_episode_saves_allocate_unique_ids(tmp_path):
    storage = JsonStorage(tmp_path / "episodes")
    paths = []

    def save(index: int) -> None:
        paths.append(
            storage.save_observed_episode(
                chat_id=100 + index,
                episode_date="2026-07-11",
                observed=OBSERVED,
            )
        )

    threads = [Thread(target=save, args=(index,)) for index in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert len(paths) == 12
    assert len({path.name for path in paths}) == 12
    assert len(list((tmp_path / "episodes").glob("episode-*.json"))) == 12


def test_blocking_worker_keeps_event_loop_responsive():
    release = Event()

    async def scenario() -> None:
        task = asyncio.create_task(run_blocking(release.wait, 2))
        await asyncio.sleep(0.03)
        assert not task.done()
        release.set()
        assert await task is True

    asyncio.run(scenario())


def test_per_chat_processor_serializes_same_chat_and_allows_other_chat():
    async def scenario() -> None:
        processor = PerChatUpdateProcessor(max_concurrent_updates=3)
        release = asyncio.Event()
        entered: list[str] = []

        async def work(label: str) -> None:
            entered.append(label)
            await release.wait()

        same_first = asyncio.create_task(
            processor.process_update(_update(1), work("same-first"))
        )
        same_second = asyncio.create_task(
            processor.process_update(_update(1), work("same-second"))
        )
        other = asyncio.create_task(
            processor.process_update(_update(2), work("other"))
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert "same-first" in entered
        assert "same-second" not in entered
        assert "other" in entered
        release.set()
        await asyncio.gather(same_first, same_second, other)
        assert entered.index("same-first") < entered.index("same-second")

    asyncio.run(scenario())


def test_global_error_journal_does_not_store_exception_message(tmp_path):
    path = tmp_path / "journal.jsonl"
    update = SimpleNamespace(
        update_id=44,
        effective_chat=SimpleNamespace(id=123),
        effective_user=SimpleNamespace(id=456),
    )

    _record_telegram_error(
        update,
        RuntimeError("private episode content"),
        JournalLog(path),
    )

    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["event_type"] == "telegram.update_failed"
    assert row["refs"] == {"chat_id": 123, "update_id": 44, "user_id": 456}
    assert row["details"] == {"exception_type": "RuntimeError"}
    assert "private episode content" not in path.read_text(encoding="utf-8")


def _update(chat_id: int):
    return SimpleNamespace(effective_chat=SimpleNamespace(id=chat_id))

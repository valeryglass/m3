from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.telegram_media import (
    DEFAULT_AUDIO_MAX_DURATION_SEC,
    TelegramMediaRejected,
    TelegramMediaRequest,
    temporary_telegram_media,
    validate_telegram_media_request,
)


class _FakeTelegramFile:
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def download_to_drive(self, custom_path: Path) -> None:
        custom_path.write_bytes(self.content)


class _FakeBot:
    def __init__(self, content: bytes = b"audio") -> None:
        self.content = content
        self.file_ids = []

    async def get_file(self, file_id: str):
        self.file_ids.append(file_id)
        return _FakeTelegramFile(self.content)


def test_validate_rejects_over_duration_before_download():
    request = TelegramMediaRequest(
        file_id="voice-file",
        media_kind="voice",
        duration_seconds=DEFAULT_AUDIO_MAX_DURATION_SEC + 1,
    )

    with pytest.raises(TelegramMediaRejected) as exc:
        validate_telegram_media_request(request)

    assert exc.value.reason == "over_duration"


def test_validate_rejects_over_size_before_download():
    request = TelegramMediaRequest(
        file_id="voice-file",
        media_kind="voice",
        file_size=21 * 1024 * 1024,
    )

    with pytest.raises(TelegramMediaRejected) as exc:
        validate_telegram_media_request(request)

    assert exc.value.reason == "over_size"


def test_validate_rejects_non_audio_document():
    request = TelegramMediaRequest(
        file_id="doc-file",
        media_kind="document",
        mime_type="application/pdf",
    )

    with pytest.raises(TelegramMediaRejected) as exc:
        validate_telegram_media_request(request)

    assert exc.value.reason == "unsupported_document"


def test_temporary_telegram_media_downloads_and_cleans_up(tmp_path):
    async def run_test() -> None:
        bot = _FakeBot(b"voice-bytes")
        request = TelegramMediaRequest(
            file_id="voice-file",
            media_kind="voice",
            mime_type="audio/ogg",
            duration_seconds=12,
            file_size=128,
        )

        async with temporary_telegram_media(bot, request, temp_dir=tmp_path) as media:
            assert media.path.exists()
            assert media.path.read_bytes() == b"voice-bytes"
            assert media.path.suffix == ".ogg"
            media_path = media.path

        assert bot.file_ids == ["voice-file"]
        assert not media_path.exists()

    asyncio.run(run_test())

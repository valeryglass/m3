from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import AsyncIterator


DEFAULT_AUDIO_MAX_DURATION_SEC = 300
DEFAULT_AUDIO_MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
AUDIO_MIME_PREFIX = "audio/"


class TelegramMediaRejected(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class TelegramMediaDownloadFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class TelegramMediaRequest:
    file_id: str
    media_kind: str
    duration_seconds: int | None = None
    file_size: int | None = None
    mime_type: str | None = None
    file_name: str | None = None

    def __post_init__(self) -> None:
        if not self.file_id:
            raise TelegramMediaRejected("missing_file_id")


@dataclass(frozen=True)
class DownloadedTelegramMedia:
    path: Path
    request: TelegramMediaRequest
    file_size: int | None = None


def validate_telegram_media_request(
    request: TelegramMediaRequest,
    *,
    max_duration_sec: int = DEFAULT_AUDIO_MAX_DURATION_SEC,
    max_file_size_bytes: int = DEFAULT_AUDIO_MAX_FILE_SIZE_BYTES,
) -> None:
    if request.duration_seconds is not None and request.duration_seconds > max_duration_sec:
        raise TelegramMediaRejected("over_duration")
    if request.file_size is not None and request.file_size > max_file_size_bytes:
        raise TelegramMediaRejected("over_size")
    if request.media_kind == "document" and not (request.mime_type or "").startswith(
        AUDIO_MIME_PREFIX
    ):
        raise TelegramMediaRejected("unsupported_document")


async def download_telegram_media(
    bot,
    request: TelegramMediaRequest,
    *,
    temp_dir: Path,
    max_duration_sec: int = DEFAULT_AUDIO_MAX_DURATION_SEC,
    max_file_size_bytes: int = DEFAULT_AUDIO_MAX_FILE_SIZE_BYTES,
) -> DownloadedTelegramMedia:
    validate_telegram_media_request(
        request,
        max_duration_sec=max_duration_sec,
        max_file_size_bytes=max_file_size_bytes,
    )
    temp_dir.mkdir(parents=True, exist_ok=True)
    suffix = _suffix_for_request(request)
    with NamedTemporaryFile(prefix="m3-audio-", suffix=suffix, dir=temp_dir, delete=False) as handle:
        path = Path(handle.name)

    try:
        telegram_file = await bot.get_file(request.file_id)
        await telegram_file.download_to_drive(custom_path=path)
    except Exception as exc:  # pragma: no cover - provider-specific runtime branch
        path.unlink(missing_ok=True)
        raise TelegramMediaDownloadFailed(str(exc)) from exc

    return DownloadedTelegramMedia(
        path=path,
        request=request,
        file_size=path.stat().st_size if path.exists() else None,
    )


@asynccontextmanager
async def temporary_telegram_media(
    bot,
    request: TelegramMediaRequest,
    *,
    temp_dir: Path,
    max_duration_sec: int = DEFAULT_AUDIO_MAX_DURATION_SEC,
    max_file_size_bytes: int = DEFAULT_AUDIO_MAX_FILE_SIZE_BYTES,
) -> AsyncIterator[DownloadedTelegramMedia]:
    downloaded = await download_telegram_media(
        bot,
        request,
        temp_dir=temp_dir,
        max_duration_sec=max_duration_sec,
        max_file_size_bytes=max_file_size_bytes,
    )
    try:
        yield downloaded
    finally:
        downloaded.path.unlink(missing_ok=True)


def _suffix_for_request(request: TelegramMediaRequest) -> str:
    if request.file_name and "." in request.file_name:
        suffix = Path(request.file_name).suffix
        if suffix:
            return suffix
    if request.mime_type == "audio/ogg":
        return ".ogg"
    if request.mime_type == "audio/mpeg":
        return ".mp3"
    if request.mime_type == "audio/mp4":
        return ".m4a"
    return ".audio"

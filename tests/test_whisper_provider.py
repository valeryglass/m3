from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.telegram_media import DownloadedTelegramMedia, TelegramMediaRequest
from app.transcription import TranscriptionFailed
from app.whisper_provider import WhisperCliTranscriptionProvider


def _fake_media(tmp_path: Path) -> DownloadedTelegramMedia:
    media_path = tmp_path / "voice.ogg"
    media_path.write_bytes(b"voice")
    return DownloadedTelegramMedia(
        path=media_path,
        request=TelegramMediaRequest(file_id="voice-file-id", media_kind="voice"),
        file_size=5,
    )


def test_whisper_cli_provider_reads_txt_output(tmp_path):
    command = tmp_path / "fake-whisper"
    command.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "audio = pathlib.Path(sys.argv[1])\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output_dir') + 1])\n"
        "(out / (audio.stem + '.txt')).write_text(' spoken transcript ', encoding='utf-8')\n",
        encoding="utf-8",
    )
    command.chmod(command.stat().st_mode | 0o111)

    transcript = WhisperCliTranscriptionProvider(command=str(command)).transcribe(
        _fake_media(tmp_path)
    )

    assert transcript.text == " spoken transcript "
    assert transcript.provider == "whisper-cli"


def test_whisper_cli_provider_raises_on_failure(tmp_path):
    command = tmp_path / "fake-whisper"
    command.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('boom', file=sys.stderr)\n"
        "raise SystemExit(2)\n",
        encoding="utf-8",
    )
    command.chmod(command.stat().st_mode | 0o111)

    with pytest.raises(TranscriptionFailed, match="boom"):
        WhisperCliTranscriptionProvider(command=str(command)).transcribe(
            _fake_media(tmp_path)
        )

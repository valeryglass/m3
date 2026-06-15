from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from app.telegram_media import DownloadedTelegramMedia
from app.transcription import TranscriptResult, TranscriptionFailed


@dataclass(frozen=True)
class WhisperCliTranscriptionProvider:
    command: str = "whisper"
    model: str | None = None
    language: str | None = None

    def transcribe(self, media: DownloadedTelegramMedia) -> TranscriptResult:
        with TemporaryDirectory(prefix="m3-whisper-") as output_dir:
            args = [
                self.command,
                str(media.path),
                "--output_format",
                "txt",
                "--output_dir",
                output_dir,
            ]
            if self.model:
                args.extend(["--model", self.model])
            if self.language:
                args.extend(["--language", self.language])

            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "whisper failed").strip()
                raise TranscriptionFailed(detail)

            transcript_path = Path(output_dir) / f"{media.path.stem}.txt"
            if not transcript_path.exists():
                raise TranscriptionFailed("whisper did not produce transcript text")
            return TranscriptResult(
                transcript_path.read_text(encoding="utf-8"),
                language=self.language,
                provider="whisper-cli",
            )

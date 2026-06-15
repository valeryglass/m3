# Docker Runtime Checklist

Purpose: make local/alpha Telegram bot rollout boring and repeatable.

## Runtime Principle

Docker should own process startup, dependency isolation, and restart behavior.
It should not own private source-of-truth decisions.

Private runtime data remains under configured `data/` paths and must not be
baked into images.

## Build And Start

```bash
docker compose build bot
docker compose up -d bot
docker compose logs -f bot
```

Run from a clean branch state:

```bash
git status --short --branch
```

## Environment

Keep runtime configuration in `.env` or deploy environment, not in committed
code.

Required core values:

```text
TELEGRAM_BOT_TOKEN
M3_TELEGRAM_ADMIN_CHAT_IDS
M3_TELEGRAM_OWNER_CHAT_ID
```

For audio runtime:

```text
M3_TRANSCRIPTION_PROVIDER=whisper
M3_WHISPER_COMMAND=whisper
M3_AUDIO_TEMP_DIR=data/runtime-audio
M3_AUDIO_MAX_DURATION_SEC=300
M3_AUDIO_MAX_FILE_SIZE_BYTES=20971520
```

## Data Volumes

These paths must survive container rebuilds:

```text
data/episodes/
data/runtime-sessions/
data/userlist/
data/ux-events/
data/annotation-runs/   # when used
```

Temporary audio may be recreated:

```text
data/runtime-audio/
```

Raw audio should remain temporary-only unless a later ADR changes retention.

## Pre-Restart Checks

```bash
python3 -m py_compile app/*.py app/schemas/*.py
python3 -m pytest -q
```

If running only inside Docker, use the equivalent container command.

## Post-Restart Smoke

At minimum:

```text
/start
plain text one-take
voice note under limit, if audio is enabled
save
cancel
/profile
/report_ux
```

Watch logs during the first real media test.

## Rollback

Rollback should be branch/image based:

```bash
git switch <previous-known-good-branch-or-tag>
docker compose build bot
docker compose up -d bot
```

Do not delete private runtime data as a rollback shortcut.

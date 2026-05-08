# M3

Personal CBT-oriented knowledge system maintained with Codex.

## Architecture

The project has working layers:

- `raw/`: immutable user texts, thoughts, logs, and artifacts.
- `sources/`: immutable methodology and reference sources.
- `model/`: accepted CBT model and JSON contracts.
- `data/episodes/`: private structured JSON episode records.
- `data/state/`: private in-progress Telegram loop state.
- `data/userlist/`: private alpha waitlist and approval records.
- `data/ux-events/`: private step-level UX analytics event log.
- `config/`: runtime configuration files.
- `app/`: runnable Telegram loop extractor app.
- `roles/`: optional Codex role specs for specific tasks.
- `schema.md`: repository/system structure map.

## Current Focus

The current engine is machine-first, episode-centered CBT storage.

`model/episode.schema.json` is the canonical episode contract. Episode records
belong in `data/episodes/` as JSON and must preserve the observed vs derived
boundary.

## Telegram Loop Extractor

The local Telegram MVP runs a deterministic one-question loop from
`roles/loop-extractor.md`.

```bash
cp .env.example .env
# fill TELEGRAM_BOT_TOKEN, M3_TELEGRAM_ADMIN_CHAT_IDS, and M3_TELEGRAM_OWNER_CHAT_ID
python -m app.telegram_bot
```

Runtime episode artifacts, session state, and alpha userlist records are stored
under `data/` and are ignored by git.

Normal bot access is granted through approved records in
`data/userlist/users.json`. The `.env` admin settings only control hidden admin
commands and owner notifications.

The bot uses `config/tone.yaml` for user-facing loop tone, with fallback text in
`app/tone_engine.py`. Tone changes interface wording only; CBT data and analytics
event fields stay unchanged.

## UX Analytics

The Telegram loop records private step-level UX events without raw answer text.

```bash
python -m app.ux_analytics
```

# M3

Personal CBT-oriented knowledge system maintained with Codex.

## Architecture

The project has working layers:

- `raw/`: immutable user texts, thoughts, logs, and artifacts.
- `sources/`: immutable reference/source materials.
- `model/`: accepted CBT model and JSON contracts.
- `data/episodes/`: private observed/source episode records.
- `data/runtime-sessions/`: private in-progress Telegram session memory.
- `data/userlist/`: private alpha waitlist and approval records.
- `data/ux-events/`: private step-level UX analytics event log.
- `data/exports/map-payload/`: explicit tracked map payload JSON/HTML exports.
- `data/reports/`: optional private debug/export snapshots.
- `config/`: runtime configuration files.
- `app/`: runnable Telegram loop extractor app.
- `docs/`: architecture operating system and methodology drafts.
- `roles/`: optional Codex role specs for specific tasks.
- `project.manifest.yaml`: structural source of truth for modules,
  interfaces, lifecycle gates, and ownership.

`docs/methodology/` is for draft methodology notes. Drafts are not accepted
model knowledge until they are promoted into `model/` through an explicit
change.

## Current Focus

The current engine is machine-first, episode-centered CBT storage with
runs-first derived annotations.

`model/episode.schema.json` is the canonical episode contract. Episode files
are observed source artifacts. Annotation-runs are durable derived graph
artifacts. Analytics loaders hydrate runtime `Episode.derived` from the selected
annotation-run or compatibility fallback.

Reports are computed projections, not active storage. Normal bot/profile/admin
paths build summaries on demand from observed episodes plus the selected/latest
annotation-run. Markdown reports are optional debug exports.

Map payload JSON and HTML previews are explicit generated exports under
`data/exports/map-payload/`. They may contain derived private data, so commit
them only when deliberately sharing that export surface.

`app.graph_report` without `--output-dir` prints the Markdown summary only and
must not write report files. Markdown export happens only when `--output-dir`
is explicitly passed.

## Telegram Loop Extractor

The local Telegram MVP runs a deterministic one-question loop from
`roles/loop-extractor.md`.

```bash
cp .env.example .env
# fill TELEGRAM_BOT_TOKEN, M3_TELEGRAM_ADMIN_CHAT_IDS, and M3_TELEGRAM_OWNER_CHAT_ID
python -m app.telegram_bot
```

Runtime episode artifacts, session memory, and alpha userlist records are stored
under `data/` and are ignored by git.

Analytics can use versioned derived annotations from `data/annotation-runs/`.
Set `M3_ANNOTATION_RUN_DIR` to force one run, or leave it empty to use the
latest valid `run-*` under `M3_ANNOTATION_RUN_ROOT`.

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

`app.ux_analytics` writes files only when `--output-dir` is explicitly passed.

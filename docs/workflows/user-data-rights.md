# User Data Rights Workflow

Use this workflow for an approved export or deletion request. Commands print
counts, IDs, and paths only. Export archives contain private content and must be
handled as sensitive data.

## Preconditions

- Resolve the request to the Telegram `user_id` recorded in the userlist.
- Stop the bot before export or deletion. The command fails if the bot-writer
  lock is active.
- Confirm configured paths in `.env`; the CLI reads current `M3_*` data paths.
- Account for external backups or working copies outside configured `data/`.

## Inventory

```bash
.venv/bin/python -m app.user_data_admin inventory --user-id <telegram-user-id>
```

Review count-only/path-only output. Do not send this operator inventory to a
different user.

## Export

```bash
.venv/bin/python -m app.user_data_admin export \
  --user-id <telegram-user-id> \
  --output <private-handoff-path>.zip
```

The archive excludes shared reports, exports, and backups because they can
contain other users. It includes the selected user's source artifacts, matching
UX/journal rows, provider usage counts, access record, and matching annotation
rows.

## Delete Preview

```bash
.venv/bin/python -m app.user_data_admin delete-preview \
  --user-id <telegram-user-id>
```

The preview returns the exact confirmation token. Deletion conservatively
clears affected annotation runs and configured shared reports/exports/backups.

## Confirmed Delete

```bash
.venv/bin/python -m app.user_data_admin delete \
  --user-id <telegram-user-id> \
  --confirm DELETE-<telegram-user-id>
```

Do not run deletion before any requested export is delivered and verified.

## Verification

```bash
.venv/bin/python -m app.user_data_admin verify --user-id <telegram-user-id>
```

Release the request only when `verified` is `true`. Then rebuild analytics from
remaining episodes through RM-15. Record any unmanaged backup/copy follow-up
outside the runtime tool.

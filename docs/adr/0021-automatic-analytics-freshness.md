# 0021: Automatic Analytics Freshness

## Status

Accepted and implemented for RM-15. Live restart and volume evidence remain part
of RM-16.

## Context

Episodes are saved independently from durable annotation-run snapshots. Before
RM-15, a new saved episode remained outside `/profile` analytics until the owner
ran a missing-only producer command. This made report freshness an operator
memory task and allowed a report to look current while selected coverage was
partial.

The annotation producer is deterministic and already writes self-contained
replacement snapshots through a temporary directory. The missing piece is safe
runtime orchestration, not a second annotation model or another source of truth.

## Decision

- Saved Episode files are the durable refresh queue. No separate pending-work
  database or JSON queue is introduced.
- `app.analytics_refresh` compares current episode IDs with the selected/latest
  valid annotation-run on startup and after every successful Save.
- One process-local coordinator coalesces simultaneous enqueue requests and runs
  deterministic production through the existing bounded blocking worker pool.
- With no valid base run, refresh writes a full snapshot. With a partial valid
  base, it writes a missing-only complete snapshot carrying existing rows
  forward unchanged.
- New runs are published only through the Annotation Producer's temporary
  directory rename. A failed refresh leaves the previous valid run untouched.
- Latest-run discovery uses manifest `created_at`, with path name only as a tie
  breaker. Explicit `M3_ANNOTATION_RUN_DIR` remains authoritative; if it is
  stale, automatic publication is blocked because the runtime cannot silently
  move an owner-pinned selection.
- If another episode is saved while production is running, the coordinator
  checks coverage again and produces another complete snapshot before becoming
  idle.
- A profile render fixes one selected run for episode hydration and coverage.
  Partial reports retain the deterministic coverage note. If no report can yet
  be built, the user sees a neutral processing message.
- Admin graph checks expose selected run ID, pending count, and freshness state.
- Queue, start, publish, no-op, and blocker journal events contain IDs, paths,
  counts, states, and failure codes only.

## Consequences

- Restart recovery cannot lose pending work because pending work is derived from
  immutable Episode files and complete snapshots.
- Report freshness is eventually consistent immediately after Save; user Save
  confirmation does not wait for annotation production.
- Public-beta operation must leave `M3_ANNOTATION_RUN_DIR` empty so latest valid
  run selection can advance automatically. Explicit pins remain useful for
  offline QA and exports.
- User-data deletion still requires the bot to be stopped. On the next startup,
  remaining episodes generate a replacement snapshot.
- Episode, annotation-run, InsightPayload, MapPayload, and Telegram command
  contracts do not change.

## Rejected Alternatives

- Persist a second refresh queue. Episode/run comparison already provides a
  crash-safe queue and avoids dual-state reconciliation.
- Mutate the selected annotation-run in place. Annotation runs are immutable
  derived snapshots and must remain rollback evidence.
- Block Save until annotation completes. That couples user confirmation latency
  to downstream deterministic analytics without improving source durability.

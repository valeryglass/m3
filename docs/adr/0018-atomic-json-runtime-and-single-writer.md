# 0018: Atomic JSON Runtime And Single Writer

## Status

Accepted and implemented for RM-13.

## Context

The beta runtime persists episodes, sessions, capture flows, reviews, source
artifacts, user access records, UX events, and process journal events as private
JSON or JSONL files. Direct writes can expose partial files, duplicate episode
IDs, or interleaved log records when different chats run concurrently.
Synchronous provider calls can also stall unrelated Telegram updates.

A database migration would add an unrelated operational boundary before the
current beta data contracts are stable.

## Decision

- Keep the existing JSON and JSONL artifact contracts.
- Write active JSON through a same-directory temporary file, `fsync`, and
  `os.replace`.
- Protect mutable paths and episode ID allocation with thread and `flock`
  locks.
- Append UX and journal JSONL records under the same lock discipline.
- Hold one non-blocking process lock under `data/runtime-flows/` for the full
  bot lifetime; a second writer exits before polling.
- Process different Telegram chats concurrently, but serialize updates from the
  same chat.
- Run extraction, transcription, and profile provider work through one bounded
  daemon worker pool.
- Record unhandled Telegram update failures as private, content-free process
  journal metadata.

## Consequences

- Interrupted replacement leaves the previous valid JSON file active.
- Concurrent episode saves cannot allocate the same ID.
- Existing private artifacts remain readable without migration.
- Lock and abandoned temporary files are runtime metadata and are ignored by
  Git; lock ownership, not lock-file existence, determines writer activity.
- This remains a single-instance architecture. Horizontal multi-writer scaling
  requires a later storage ADR.

## Rejected Alternative

Introduce PostgreSQL or SQLite for Beta-2. That would combine runtime hardening
with a storage-contract migration and does not solve provider/event-loop
responsiveness by itself.

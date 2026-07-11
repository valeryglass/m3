# Runtime Storage

## Purpose

Provide crash-safe local JSON writes, serialized JSONL appends, process locks,
and bounded blocking work for the single-instance beta runtime.

## Inputs

- validated runtime JSON payloads from owning modules;
- safe UX and process journal event mappings;
- synchronous extraction, transcription, and profile provider calls.

## Outputs

- atomically replaced private JSON files;
- serialized append-only JSONL rows;
- one active bot-writer lease per runtime-flow root;
- per-chat ordered Telegram execution across concurrently active chats.

## Dependencies

- local POSIX filesystem with atomic same-filesystem `os.replace` and `flock`;
- Telegram Capture for process lifecycle and update dispatch.

## Interfaces

No domain interface. Owning modules retain their persisted contracts and call
the runtime primitives internally.

## Safety Rules

- temporary files are created in the destination directory;
- replacement occurs only after file flush and `fsync`;
- episode ID selection and write share one directory lock;
- UX and journal lines are serialized and written as complete UTF-8 rows;
- lock files contain process metadata only;
- unhandled-error journal events contain IDs and exception type, never the
  exception message or submitted content;
- multiple bot writers for one runtime root are rejected.

## Lifecycle

`experimental`

The local single-writer contract is implemented and concurrency-tested. RM-16
must still verify behavior on the production Docker volume and host filesystem.

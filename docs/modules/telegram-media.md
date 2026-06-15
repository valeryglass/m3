# Telegram Media

## Purpose

Provide the future Telegram file-download boundary for voice notes, audio
messages, and audio-like document uploads.

Telegram Media does not own transcription, episode drafts, persistence,
annotation, reports, or graph behavior. It converts Telegram `file_id` metadata
into temporary media material that a transcription provider can consume.

## Inputs

- Telegram voice `file_id` and metadata.
- Telegram audio `file_id` and metadata.
- Telegram document `file_id` when MIME type is audio-like.
- configured size limits, duration limits, and MIME allowlist.

## Outputs

- temporary local media path or bytes for transcription.
- download failure reason.
- rejection reason for unsupported or oversized media.

## Guarantees

- raw audio is not persisted by default.
- temporary files are cleaned after success or failure.
- unsupported, oversized, or over-duration media is rejected before provider calls.
- download errors do not create drafts.
- successful downloads still do not create drafts until transcription succeeds.


## MVP2 Limits

Initial policy:

```text
soft UX target: <= 3 minutes
hard duration cap: <= 5 minutes
raw audio retention: temp-only
provider: Whisper first, behind provider boundary
```

Telegram Media owns checking duration/size metadata when available before any
provider call. Exact limits should be configuration values, but the MVP2 default
should stay conservative.

## Ownership

- producer: `telegram_capture` surface handlers.
- consumer: `app.transcription` provider boundary.

## Lifecycle

`draft`

This module is planned for `mvp2/audio-input` after the input-funnel alpha
foundation. The first implementation slice should add this boundary before any
real provider integration.

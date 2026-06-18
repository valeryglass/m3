# 0008: Audio Transcription Provider And Retention

## Status

Accepted planning decision for `mvp2/audio-input`.

## Decision

Production audio input must be wired in two steps:

```text
Telegram media -> temporary media boundary -> transcription provider -> TranscriptResult -> IntakeTranscript -> future extraction/validation -> confirmed episode
```

The current input-funnel alpha already accepts voice, audio, and audio-like
Telegram documents as input artifacts. MVP2 audio first stores a durable
transcript source artifact. Structured episode extraction and user validation are
separate later steps.

Raw Telegram audio is not persisted by default. Media bytes/files are temporary
runtime material used only to obtain a transcript or a clear failure. Transcript
text is persisted as the first durable source artifact for audio intake. It is
not a canonical episode record. Only a later user-confirmed observed episode may
enter episode storage and graph/report analytics.

## Why

Audio is the most natural capture medium for many users, but it is also the
highest-risk intake path for accidental retention, provider coupling, and false
confidence. Wiring provider calls directly into Telegram handlers would mix
surface handling, media retention, transcription, draft construction, and
persistence.

This ADR keeps the existing sacred boundary intact:

```text
input != episode
raw audio != episode
transcript artifact != episode
draft != episode
confirmed observed episode = canonical persisted source artifact
```

## Provider Policy

The production provider must sit behind the `app.transcription` boundary.
MVP2 starts with Whisper as the first provider, but provider choice remains a
configuration boundary, not episode schema.


MVP2 provider decision:

```text
default provider: whisper
architecture: cross-provider TranscriptionProvider boundary
Telegram handlers must not call Whisper directly
```

Provider implementations must return either:

```text
TranscriptResult(text, language?, provider?)
```

or a clear failure.

Empty transcripts are failures. Provider failures must not create drafts or
persist episodes. The bot may tell the user that transcription failed and ask for
text instead.

## Retention Policy

Default behavior:

- raw Telegram audio is temporary only.
- temporary media files/bytes are deleted after transcription success or failure.
- transcript text is persisted as a private `IntakeTranscript` source artifact.
- transcript artifacts do not store raw audio paths or Telegram `file_id` values.
- UX events may record event names, funnel, media kind, size bucket or failure
  reason, but not raw private audio or full transcript text.
- confirmed episode files remain observed source artifacts and must not store raw
  audio.

Any decision to retain raw audio requires a later ADR.

Operator-facing default:

```text
M3_AUDIO_STORE_RAW=false
```

The initial implementation should treat `false` as the only supported production
value. The flag documents the boundary; it is not permission to retain raw audio
without a later ADR.



## Media Limits

MVP2 should start with short voice/audio capture, not long-form transcription.

Recommended limits:

```text
soft UX target: 180 seconds
hard duration cap: 300 seconds
file size cap: provider/runtime configured, checked before provider call
```

User-facing behavior for longer media: reject politely and keep
`audio_one_take` armed for a shorter voice/audio retry or `/cancel`. Ten-minute
audio is explicitly out of MVP2 default scope and can be reconsidered later as
an operator-configured extension.

## Failure And Retry Policy

Failure states:

```text
input_rejected
media_download_failed
transcription_failed
transcription_pending
```


No silent fallback policy:

```text
no media download -> no IntakeTranscript
no transcript -> no IntakeTranscript
empty transcript -> no IntakeTranscript
provider error -> no IntakeTranscript
```

The current audio flow must never create or guess an `EpisodeDraft`, session, or
episode from a transcript, file metadata, duration, MIME type, or empty media
placeholder.

Episode creation is blocked for media until a transcript exists and a later
extraction/validation flow accepts structured observed fields. Retries should be
explicit and bounded. The system must not enter an automatic retry loop that
repeatedly downloads or sends media to a provider without a user-visible action
or operator decision.

## Non-goals

- no audio-specific episode schema.
- no raw audio archive.
- no voice emotion recognition.
- no prosody analysis.
- no speaker diarization.
- no long-form audio commitment.
- no clinical or diagnostic inference changes.

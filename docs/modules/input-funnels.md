# Input Funnels

## Purpose

Normalize different user input surfaces into common pre-episode capture
artifacts.

Input Funnels do not own the episode schema, annotation logic, graph reporting,
or user-facing reports. They adapt surface-specific input into a normalized
shape. Text input can seed Episode Drafts directly. Audio first persists an
`IntakeTranscript`, then may seed a draft only after explicit confirmation.

## Inputs

- Telegram text messages.
- Telegram voice notes.
- Telegram audio uploads.
- Telegram document uploads that contain audio.
- Future structured forms or web UI submissions.

## Outputs

- normalized input artifacts for the selected downstream boundary.

Conceptual shape:

```text
InputArtifact:
  source: telegram | future_surface
  media_kind: text | voice | audio | document | form
  source_ref:
    chat_id?
    message_id?
    file_id?
  raw_text?
  transcript?
  duration_seconds?
  mime_type?
  file_size?
  received_at?
```

## Guarantees

- input artifacts are not observed episodes.
- transcripts are support evidence, not canonical episode records.
- surface-specific metadata stays outside the canonical episode schema unless a
  future ADR promotes it.
- unsupported media can be rejected before draft creation.
- audio artifacts cannot create a draft before successful transcription and
  explicit transcript confirmation.

## Ownership

- producer: surface adapters such as `telegram_capture`
- consumers: `episode_drafts` for accepted text/transcript evidence;
  `intake_transcripts` for transcribed audio

## Lifecycle

`draft`

This boundary keeps input normalization reusable without forcing every input
surface into one downstream draft path.

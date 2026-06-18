# Input Funnels

## Purpose

Normalize different user input surfaces into common pre-episode capture
artifacts.

Input Funnels do not own the episode schema, annotation logic, graph reporting,
or user-facing reports. They adapt surface-specific input into a normalized
shape. The explicit userflow chooses the consumer: hidden text tools can use
Episode Drafts; `audio_one_take` persists an `IntakeTranscript` source artifact.

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
- audio artifacts are not converted into `EpisodeDraft` by the current
  `audio_one_take` flow.

## Ownership

- producer: surface adapters such as `telegram_capture`
- consumers: `episode_drafts` for explicit text tools; `intake_transcripts` for
  `audio_one_take`

## Lifecycle

`draft`

This boundary keeps input normalization reusable without forcing every input
surface into one downstream draft path.

# Input Funnels

## Purpose

Normalize different user input surfaces into common pre-episode capture
artifacts.

Input Funnels do not own the episode schema, annotation logic, graph reporting,
or user-facing reports. They adapt surface-specific input into a shape that can
be consumed by Episode Drafts.

## Inputs

- Telegram text messages.
- Telegram voice notes.
- Telegram audio uploads.
- Telegram document uploads that contain audio.
- Future structured forms or web UI submissions.

## Outputs

- normalized input artifacts for the Episode Drafts boundary.

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

## Ownership

- producer: surface adapters such as `telegram_capture`
- consumer: `episode_drafts`

## Lifecycle

`draft`

This boundary is planned so audio, one-take text, three-block narrative, and the
classic question flow can share one downstream draft path.

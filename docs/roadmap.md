# Roadmap

## Current Release Track

### Input Funnels And Episode Draft Hydration

Status: alpha foundation.

The epic has produced a shared runtime path for text, hidden command, hidden
three-block, voice, audio, and audio-document inputs:

```text
input surface -> InputArtifact -> EpisodeDraft -> Gap Hydration -> Draft Review -> confirmed episode
```

Accepted alpha result:

- one-take text can start draft capture.
- hidden `/capture <text>` can start draft capture explicitly.
- hidden `/capture3 a | b | c` can start a three-block draft.
- voice/audio/document inputs are recognized as input artifacts.
- untranscribed media stops before draft creation.
- draft review is explicit before persistence.
- funnel, gap-question, confirmation, save, discard, and rejection metrics are
  visible in UX analytics.

Not yet production feature status:

- audio/voice is not a production capture feature until transcription is wired.
- hidden command routes are alpha/test affordances, not polished user UX.
- one-take text is the only new user-visible capture behavior in this epic.
- episode schema, annotation runs, graph reports, and map payload behavior are
  intentionally unchanged.

## MVP2 Audio Input Track

Branch base:

```text
epic/input-funnel-alpha -> mvp2/audio-input
```

Goal: turn media intake placeholders into production audio draft capture on
`mvp2/audio-input` without weakening the episode schema or retaining raw audio
by default.

### PR-A0 Audio transcription ADR

Goal: accept ADR `0008-audio-transcription-provider-and-retention` before
provider wiring.

Acceptance:

- MVP provider is Whisper, behind a cross-provider configuration boundary.
- raw Telegram audio is temporary-only by default.
- no transcript means no draft; no silent fallback.
- soft duration target is 3 minutes; hard cap is 5 minutes for MVP2.
- transcript text is support evidence for draft construction.
- failure/retry behavior is explicit.
- UX events do not store raw audio or full transcripts.
- default retention is temporary raw audio only, with no raw archive.

### PR-A1 Telegram media download boundary

Goal: add a dedicated Telegram media boundary before provider integration.

Acceptance:

- voice, audio, and audio-like document `file_id` values can be downloaded in
  tests with fake Telegram file objects.
- size, MIME, and duration guards reject unsupported media before provider calls.
- temporary media is cleaned after success or failure.
- download failures emit safe UX events and do not create drafts.

### PR-A2 Transcription provider interface

Goal: upgrade the passive transcription module into a provider interface.

Acceptance:

- provider success returns `TranscriptResult`.
- empty transcripts are rejected.
- provider failures emit `transcription_failed`.
- no draft is created on provider failure.

### PR-A3 Voice to draft

Goal: let Telegram voice notes create drafts only after transcription succeeds.

Acceptance:

- voice note -> download -> transcribe -> attach transcript -> draft session.
- confirmation remains required before persistence.
- raw audio is not saved.
- UX events include input, transcript, draft, gap, confirmation/save/discard.

### PR-A4 Audio/document fallback to draft

Goal: give uploaded audio and audio-like documents the same downstream behavior
as voice notes.

Acceptance:

- `message.audio` can create a draft after transcript.
- audio-like document can create a draft after transcript.
- unsupported documents remain politely rejected.
- oversized files remain blocked before provider calls.

### PR-A5 Production smoke, operator notes, and rollback

Goal: make deploy readiness observable.

Acceptance:

- full local test suite passes before rollout.
- smoke covers `/start`, plain text, `/capture`, `/capture3`, voice, audio,
  audio document, unsupported document, save, cancel, `/profile`, and
  `/report_ux`.
- operator notes distinguish alpha text capture, media pending transcription,
  and production audio draft capture.
- expected UX events are listed for each smoke flow.
- legacy sessions without optional funnel/media metadata keep working.
- rollback note confirms no episode schema migration is required.

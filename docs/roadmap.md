# Roadmap

## Completed Foundation Track

### Input Funnels And Episode Draft Hydration

Status: completed alpha foundation for explicit text developer routes.

The epic produced reusable input and draft boundaries:

```text
hidden text surface -> InputArtifact -> EpisodeDraft -> Gap Hydration -> Draft Review -> confirmed episode
```

Accepted alpha result:

- hidden `/capture <text>` can start draft capture explicitly.
- hidden `/capture3 a | b | c` can start a three-block draft.
- voice/audio/document inputs can be normalized as input artifacts.
- draft review is explicit before persistence.
- funnel, gap-question, confirmation, save, discard, and rejection metrics are
  visible in UX analytics.

Containment decisions supersede earlier automatic-capture experiments:

- `/start` is the only normal entrypoint for classic 10Q.
- idle text and media return `/start` guidance.
- hidden command routes remain developer affordances.
- audio input does not enter the Episode Draft path.
- episode schema, annotation runs, graph reports, and map payload behavior are
  intentionally unchanged.

## MVP2 Audio Input Track

Branch base:

```text
epic/input-funnel-alpha -> mvp2/audio-input
```

Goal: provide explicit transcript-backed `audio_one_take` intake without
weakening the episode schema or retaining raw audio by default.

```text
/voice
  -> audio_one_take
  -> audio_intake_started
  -> temporary media
  -> transcription
  -> IntakeTranscript source artifact
  -> transcript preview
  -> audio_intake_completed
  -> idle
```

Audio does not create an `EpisodeDraft` or episode. Extraction and validation
remain later work.

### PR-A0 Audio transcription ADR

Goal: accept ADR `0008-audio-transcription-provider-and-retention` before
provider wiring.

Acceptance:

- MVP provider is Whisper, behind a cross-provider configuration boundary.
- raw Telegram audio is temporary-only by default.
- no transcript means no source artifact; no silent fallback.
- soft duration target is 3 minutes; hard cap is 5 minutes for MVP2.
- transcript text is persisted as a private source artifact for future extraction.
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
- download failures emit safe UX events and do not create transcript artifacts.

### PR-A2 Transcription provider interface

Goal: upgrade the passive transcription module into a provider interface.

Acceptance:

- provider success returns `TranscriptResult`.
- empty transcripts are rejected.
- provider failures emit `transcription_failed`.
- no `IntakeTranscript` is created on provider failure.

### PR-A3 Voice to transcript artifact

Goal: let Telegram voice notes create durable transcript source artifacts after
transcription succeeds.

Acceptance:

- voice note -> download -> transcribe -> persist `IntakeTranscript`.
- raw audio is not saved.
- the bot shows a transcript preview and stops the audio branch.
- no episode is created until a later extraction/validation flow exists.

### PR-A4 Audio/document fallback to transcript artifact

Goal: give uploaded audio and audio-like documents the same transcript-artifact
behavior as voice notes.

Acceptance:

- `message.audio` can create an `IntakeTranscript` after transcript.
- audio-like document can create an `IntakeTranscript` after transcript.
- unsupported documents remain politely rejected.
- oversized files remain blocked before provider calls.

### PR-A5 Production smoke, operator notes, and rollback

Goal: make deploy readiness observable.

Acceptance:

- full local test suite passes before rollout.
- smoke covers idle containment, classic 10Q, hidden `/voice`, supported and
  unsupported media, cancellation, `/help`, `/profile`, and post-audio idle
  behavior.
- operator notes distinguish hidden draft tools from explicit transcript intake.
- `docs/workflows/audio-input-smoke.md` defines the deploy smoke checklist.
- expected UX events are listed for each smoke flow.
- legacy sessions without optional funnel/media metadata keep working.
- rollback note confirms no episode schema migration is required.

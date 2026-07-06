# Roadmap

## Completed Foundation Track

### First-Class Capture And Schema Extraction

Status: promoted to first-class draft capture modes.

The epic produced reusable input and draft boundaries:

```text
explicit capture command -> CaptureArtifact -> Capture Extraction -> Draft Review -> confirmed episode
```

Accepted alpha result:

- `/start` and `/10q` start classic question capture.
- `/1t` arms one-take text capture.
- `/3b` collects three sequential blocks.
- `/1a` arms voice/audio capture; hidden `/1v` is an alias.
- hidden `/capture`, `/capture3`, and `/voice` remain compatibility routes.
- completed capture evidence is persisted privately before extraction.
- non-10Q modes require grounded structured extraction and go directly to
  review.
- classic 10Q uses deterministic direct projection.
- draft review is explicit before persistence.
- funnel, extraction, confirmation, save, discard, and rejection metrics are
  visible in UX analytics.

Containment decisions supersede earlier automatic-capture experiments:

- `/start` remains an alias for classic 10Q.
- idle text and media return `/start` guidance.
- commands do not replace active work without `/cancel`.
- audio enters the Episode Draft path only after full transcript confirmation.
- non-10Q extraction failure creates no draft or review and never falls back to
  10Q or Gap Hydration.
- episode schema, annotation runs, graph reports, and map payload behavior are
  intentionally unchanged.

## Beta-1 Stable Micro Build

Status: active release-management roadmap.

Goal: make the beta product stable and usable around the existing capture
surface:

```text
/10q /3b /1t /1a
  -> schema-valid episode
  -> annotation-run refresh
  -> hydrated graph
  -> basic map export
  -> short report
  -> long report
  -> UX/admin stats
```

RM order:

- RM-00: align roadmap source of truth.
- RM-01: add runtime mode and DeepSeek provider support. Status: implemented.
- RM-02: add operator analytics commands. Status: implemented.
- RM-03: define capture smoke to beta standard. Status: implemented.
- RM-04: produce or verify a fresh annotation-run. Status: implemented.
- RM-05: QA payload, map, short report, and long report. Status: implemented.
- RM-06: inventory and rewrite brand text.
- RM-07: prepare tutorial script.

Current runtime truth: non-10Q production capture extraction defaults to
DeepSeek through owner-controlled runtime mode/provider settings. OpenAI
Responses remains explicit compatibility.

## MVP2 Audio Input Track

Branch base:

```text
epic/input-funnel-alpha -> mvp2/audio-input
```

Goal: provide explicit transcript-backed `one_take_audio` intake without
weakening the episode schema or retaining raw audio by default.

```text
/1a
  -> one_take_audio
  -> audio_intake_started
  -> temporary media
  -> transcription
  -> IntakeTranscript source artifact
  -> complete transcript confirmation
  -> CaptureArtifact
  -> Capture Extraction
  -> DraftReviewSession
  -> final Save confirmation
```

Audio creates a `CaptureArtifact` only after the user accepts the complete
transcript. Successful extraction creates the shared Save review; final episode
persistence still requires explicit Save.

### PR-A0 Audio transcription ADR

Goal: accept ADR `0008-audio-transcription-provider-and-retention` before
provider wiring.

Acceptance:

- MVP provider is Whisper, behind a cross-provider configuration boundary.
- raw Telegram audio is temporary-only by default.
- no transcript means no source artifact; no silent fallback.
- soft duration target is 3 minutes; hard cap is 5 minutes for MVP2.
- transcript text is persisted as a private source artifact before explicit
  draft continuation.
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
- the bot shows the complete transcript and requires Continue or Reject.
- Continue starts grounded schema extraction; no draft exists on extraction
  failure and no episode exists before final Save.

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

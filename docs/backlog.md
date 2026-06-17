# Backlog

Status: active lightweight project backlog. This file is a working planning
surface, not a source of truth, schema, roadmap commitment, or release plan.

Use it for small next-step memory that is too concrete for external methodology
and too early for accepted model docs.


## Epic: Input Funnels And Episode Draft Hydration

Intent: refactor capture so text, voice, uploaded audio, three-block narrative,
and the classic question flow all enter the same draft and gap-hydration
pipeline without changing the canonical episode schema.

Decision candidate:

- Add ADR `0007-input-funnels-and-episode-drafts`.
- Treat Telegram Capture as a surface adapter.
- Introduce Input Funnels, Episode Drafts, and Gap Hydration as explicit
  planning boundaries.
- Keep confirmed observed episodes as the only canonical persisted source
  artifact.

Global acceptance:

- `episode.schema.json` is unchanged for the planning epic.
- No audio-specific episode type is introduced.
- Raw audio and transcripts do not bypass user confirmation.
- Gap hydration can operate on any partial episode draft.
- Existing graph, report, annotation-run, and map payload behavior is out of
  scope.

Completed planning setup:

- BL-01 input funnels ADR accepted.
- BL-02 module and interface docs accepted.
- BL-03 architecture wording refactored with Telegram UX/access kept as current
  runtime responsibilities.

### BL-01 Add input funnels ADR

Status: completed.

Created `adr/0007-input-funnels-and-episode-drafts.md`.

Acceptance:

- ADR distinguishes `input`, `transcript`, `draft`, `episode`, `annotation`,
  `graph`, and `report`.
- ADR says multiple capture forms produce drafts, not separate episode types.
- ADR preserves observed episode files as canonical source artifacts.

### BL-02 Add module and interface docs

Status: completed.

Created planning docs for:

```text
modules/input-funnels.md
modules/episode-drafts.md
modules/gap-hydration.md
interfaces/input-to-draft.md
interfaces/draft-to-episode.md
```

Acceptance:

- each file states purpose, inputs, outputs, guarantees, ownership, and
  lifecycle.
- new docs remain planning-level and do not imply runtime behavior already
  exists.

### BL-03 Refactor architecture wording

Status: completed.

Updated architecture and Telegram Capture docs so the classic question flow is a
capture strategy, not the architecture boundary.

Acceptance:

- architecture flow includes Input Funnels, Episode Drafts, and Gap Hydration.
- `modules/telegram-capture.md` describes Telegram as a surface adapter.
- `interfaces/capture-to-episode.md` remains as compatibility/direct completed
  capture boundary.

### BL-04 Shorten capture CTA

Replace the heavy start framing with one clear CTA-style question.

Candidate copy:

```text
What happened? Send text or voice — I’ll make a draft and ask only what’s missing.
```

Russian candidate:

```text
Что случилось? Ответь текстом или голосом — я соберу черновик и спрошу только недостающее.
```

Acceptance:

- one action is visible to the user.
- the 10-question structure is not exposed upfront.
- the old question flow can still be used behind the draft/gap boundary.

### BL-05 Refactor classic 10Q as draft filler

Treat the existing 10-question sequence as one way to fill an Episode Draft.

Implementation split:

- BL-05a: introduce draft vocabulary around the existing `LoopSession` observed
  in-progress state without behavior, schema, or persistence changes.
- BL-05b: route current question progression through a reusable draft/gap
  selector once the draft boundary is explicit.
- BL-05c: move draft counting, status, and target-selection primitives into
  `app/episode_drafts.py` while keeping `LoopSession` as the current runtime
  holder.
- BL-05d: introduce a passive `app/gap_hydration.py` runtime boundary that
  can report/select draft gaps without changing current 10Q behavior.
- BL-05e: wire missing-field discovery in `loop_extractor` through passive
  Gap Hydration while keeping active target selection current-order.
- BL-05f: route active target selection through Gap Hydration while keeping
  the current-order strategy for normal active sessions.

Acceptance:

- each answer updates a draft field.
- missing required fields are selected by Gap Hydration.
- completed and confirmed drafts still persist through Episode Model + Storage.

### BL-06 Add one-take text draft path

Allow one text message to produce a provisional episode draft.

Implementation split:

- BL-06a: introduce a runtime `InputArtifact` boundary for text, voice, audio,
  and document inputs without changing Telegram behavior.
- BL-06b: add passive one-take text-to-draft construction behind explicit
  routing.
- BL-06c: add a draft-to-session bridge so one-take drafts can enter the
  existing LoopSession runtime without Telegram routing changes.
- BL-06d: add explicit hidden `/capture <text>` Telegram routing into the
  one-take draft/session bridge while leaving plain text without session
  unchanged.
- BL-06e: route natural plain text without an active session into one-take
  draft/session capture while keeping `/start` as an explicit guided entry.

Acceptance:

- one-take text can create a partial draft.
- missing fields are detected.
- the user can confirm, continue, edit, or discard.

### BL-07 Add Telegram voice funnel

Accept Telegram voice notes as input artifacts.

Implementation split:

- BL-07a: add a passive voice `InputArtifact` factory that carries Telegram
  file metadata and optional transcript text without storing raw audio.
- BL-07b: route Telegram `voice` messages into voice input artifacts and
  reject them before draft construction until transcription is available.
- BL-07c: add transcript-to-draft/session routing so voice can enter the
  same draft path as text after transcription.
- BL-07d: add a passive transcription boundary that can attach transcript
  support text to audio artifacts without choosing a provider yet.

Acceptance:

- voice input enters the same draft path as text.
- transcript is support evidence, not a saved episode.
- confirmation is required before persistence.
- raw audio is not saved by default.

### BL-08 Add audio/document fallback

Accept uploaded audio files as a fallback to voice notes.

Implementation split:

- BL-08a: add passive `audio` and audio-like `document` input artifact
  factories without Telegram routing changes.
- BL-08b: route Telegram `audio` and audio-like `document` messages into
  input artifacts and reject unsupported files before transcription.

Acceptance:

- `audio` messages and audio-like `document` messages can enter the same
  funnel.
- unsupported or oversized files are rejected clearly.
- downstream draft behavior is identical to voice.

### BL-09 Add three-block narrative mode

Add a lighter guided capture strategy:

```text
1. What happened?
2. What happened inside you?
3. What did you do / what changed after?
```

Implementation split:

- BL-09a: add passive three-block-to-draft construction with a default
  canonical field mapping and no Telegram routing.
- BL-09b: add hidden `/capture3 a | b | c` routing that creates a
  three-block draft/session.
- BL-09c: decide whether three-block should become a visible intake option.

Acceptance:

- three answers produce a draft.
- Gap Hydration asks only for missing canonical fields.
- no new episode schema is required.

### BL-10 Track funnel UX metrics

Add UX events for funnel comparison.

Implementation split:

- BL-10a: emit `input_received` and `draft_created` for draft-producing
  text, hidden command, transcribed-artifact, and three-block funnels.
- BL-10b: emit media rejection/transcription-pending events for voice, audio,
  and document inputs that cannot yet create drafts.
- BL-10c: add funnel/media summary counts to UX analytics markdown/json
  reports.
- BL-10d: document product-facing funnel success metrics and non-goals in
  UX Analytics.
- BL-10e: emit `gap_question_asked` events and summarize gap-question funnel
  metrics.

Candidate events:

```text
input_received
transcript_created
draft_created
gap_question_asked
draft_confirmed
draft_discarded
episode_saved
transcription_failed
transcription_pending
input_rejected
```

Acceptance:

- events avoid private content unless already allowed by UX event policy.
- metrics can compare 10Q, one-take, voice, and three-block capture.

### BL-11 Add draft confirmation boundary

Make the save review an explicit draft confirmation boundary before the
canonical episode is persisted.

Implementation split:

- BL-11a: add a passive draft-review renderer for complete draft summaries.
- BL-11b: route the existing final save review through the draft-review
  boundary without changing copy or buttons.
- BL-11c: carry funnel metadata on draft sessions and emit confirmation, save,
  and discard UX metrics.

Acceptance:

- complete drafts are shown back before persistence.
- save and discard remain explicit user decisions.
- review rendering does not create annotations, graph facts, or reports.
- unconfirmed or discarded drafts do not become episode files.


## MVP2 Audio Input

Status: next branch after `epic/input-funnel-alpha`.

Branch:

```text
mvp2/audio-input from epic/input-funnel-alpha
```

Intent: turn voice/audio/document intake placeholders into production audio
draft capture without changing the canonical episode schema.

Global acceptance:

- no audio-specific episode type.
- no draft creation from media without transcript.
- no raw audio persistence by default.
- no silent fallback: failed or empty transcript never creates a draft.
- MVP2 soft duration target is 3 minutes; hard cap is 5 minutes.
- confirmed observed episode remains the canonical source artifact.
- provider failures are safe and observable.
- legacy sessions without optional funnel/media metadata keep working.

### PR-A0 Audio transcription ADR

Status: planned.

Create and accept `docs/adr/0008-audio-transcription-provider-and-retention.md`.

Acceptance:

- provider choice is explicit: Whisper first, cross-provider boundary.
- retention policy is explicit.
- transcript role is support evidence, not canonical episode data.
- failure and retry behavior is explicit.
- raw audio is temporary-only by default.

### PR-A1 Telegram media boundary

Status: planned.

Add the download/cleanup boundary before provider wiring.

Acceptance:

- voice/audio/audio-document files can be fetched via fake Telegram file tests.
- unsupported media is rejected before provider calls.
- oversized or over-duration media is rejected before provider calls.
- temp files or bytes are cleaned after success/failure.

### PR-A2 Transcription provider interface

Status: planned.

Upgrade `app.transcription` from passive placeholder to provider boundary.

Acceptance:

- `TranscriptResult` is produced on success.
- empty transcript is failure.
- provider errors emit safe UX events.
- failed transcription does not create drafts.

### PR-A3 Voice transcript artifact creation

Status: planned.

Wire Telegram voice notes into the existing transcript-to-draft/session path.

Acceptance:

- voice note can create an IntakeTranscript after transcription.
- missing transcript keeps current `transcription_pending` behavior.
- draft confirmation remains required.

### PR-A4 Uploaded audio transcript artifact creation

Status: planned.

Wire `message.audio` and audio-like documents into the same path as voice.

Acceptance:

- uploaded audio can create an IntakeTranscript after transcription.
- audio-like document can create an IntakeTranscript after transcription.
- unsupported documents remain rejected.

### PR-A5 Production smoke, operator notes, and rollback

Status: planned.

Acceptance:

- full local test suite passes before rollout.
- smoke checklist covers text, hidden commands, media, save/cancel, profile, and
  UX report.
- `docs/workflows/audio-input-smoke.md` exists.
- operator notes distinguish placeholder media intake from production audio
  draft capture.
- expected UX events are listed for each smoke flow.
- legacy sessions without optional metadata keep working.
- rollback note says no episode schema migration is required.

## Now

### Add Set Signature / Co-signature

Intent: distinguish ordered signatures from unordered co-presence patterns.

Acceptance:

- Registry distinguishes `signature` from `set_signature`.
- Reports do not imply causality or sequence from set signatures.
- Set signatures can be counted across episodes when implemented.

Notes:

- Example set: `{trigger:social, emotion:shame, behavior:avoid}`.
- Keep this report-layer until schema/runtime work explicitly promotes it.

### Split Motif Variants

Intent: avoid collapsing repeated paths and repeated sets into one label.

Acceptance:

- Registry names `path_motif` and `set_motif`.
- Future metrics can count both without changing observed episode storage.
- Report labels keep ordered and unordered support separate.

## Next

### Define Attractor Readiness

Intent: make attractor a cautious report-layer region, not a single repeated
path or diagnosis.

Acceptance:

- Draft rule uses at least `support_count >= 3`, `unique_signatures >= 2`,
  `unique_episodes >= 3`, usable confidence, and provenance episode IDs.
- One repeated path remains a motif, not an attractor.
- Optional stability rule can require presence in at least two time buckets.

### Surface Contrast / Counterexamples

Intent: let reports show meaningful variation without erasing the main pattern.

Acceptance:

- Counterexamples include evidence and provenance.
- Counterexamples do not automatically invalidate a dominant motif.
- Contrasts stay report-level insight candidates, not graph source facts.

## Later

### Decide Promotion Path

Intent: decide whether `set_signature`, `set_motif`, and `attractor` stay in
methodology/report layers or become accepted model/runtime concepts.

Acceptance:

- If promoted to accepted model, update `model/`, schemas or runtime code as
  needed, docs, and ADR.
- If kept as report-layer concepts, document payload fields without changing
  episode storage.

## Parking Lot

- Explore whether hyperedge/simplex language adds user value at larger sample
  sizes.
- Revisit map payload terms only after domain entities are stable.


## Future Audio Extraction Track

Audio transcript persistence is not the same as episode creation. Future work may
add:

- transcript -> structured observed-field extraction.
- user validation / correction.
- confirmed episode persistence.
- annotation re-runs from transcript source artifacts.

Until that track exists, audio intake stores transcript source artifacts and does
not contribute to graph/report analytics as episodes.

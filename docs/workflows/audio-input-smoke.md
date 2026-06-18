# Audio Input Smoke Checklist

Use this checklist before marking explicit Telegram userflow containment and
audio transcript intake deployable.

## Preconditions

- Branch is based on `epic/input-funnel-alpha`.
- Default transcription provider is `whisper`; local alpha smoke uses
  `.venv/bin/whisper`.
- Whisper command, model, and language values are known to the operator.
- Raw audio retention remains disabled; media is temporary-only.
- Test user is approved in the userlist.

## Commands

Run local checks first:

```bash
make release-audio-check
```

If `make check-whisper` fails, run `make venv` or set `M3_WHISPER_COMMAND` to a
valid command before inviting alpha users.

## Containment Regression Matrix

| Scenario | Expected transition/reply | Durable artifact | Prohibited side effects |
|---|---|---|---|
| idle text | stays idle; returns `/start` guidance | none | no `LoopSession`, download, transcription, or transcript |
| idle voice/audio/document | stays idle; same `/start` guidance | none | no download, transcription, `LoopSession`, or transcript |
| idle `/start` | idle -> `classic_10q` | classic runtime session only | no audio state |
| classic 10Q text answer | remains `classic_10q`; advances current question | updated classic runtime session | no audio state or transcript |
| classic 10Q media | remains `classic_10q`; existing text-required reply | unchanged classic runtime session | no download or transcription |
| idle hidden `/voice` | idle -> `audio_one_take`; asks for voice/audio | short-lived audio flow state | no `LoopSession` or episode |
| `audio_one_take` text | remains armed; asks for voice/audio or `/cancel` | unchanged audio flow state | no classic session or transcript |
| `audio_one_take` supported media | `audio_intake_started` -> transcription -> preview -> `audio_intake_completed` -> idle | one private `IntakeTranscript` source artifact | no `EpisodeDraft`, `LoopSession`, episode, or raw-audio archive |
| post-audio idle text | stays idle; returns `/start` guidance | existing transcript remains source-only | no automatic classic session |
| `/cancel` from classic | `classic_10q` -> idle | classic runtime state removed | no audio state created |
| `/cancel` from audio | `audio_one_take` -> idle | audio flow state removed | no transcript or episode created by cancel |
| `/help` during either flow | flow state unchanged; current help copy | none | no session/flow mutation |
| `/profile` during either flow | flow state unchanged; current report behavior | none | no session/flow mutation |

Hidden `/capture` and `/capture3` remain explicit developer routes for draft
testing. They are not normal idle entrypoints and are not part of audio intake.

## Event And Lifecycle Expectations

Successful armed audio intake emits these UX events:

```text
input_received
transcript_created
```

Safe lifecycle logging reaches:

```text
audio_intake_completed
```

`audio_intake_started` names the workflow phase beginning after armed media is
accepted; it is not currently a separate UX event. Safe lifecycle logs expose
lower-level media and transcription markers. Do not infer draft or episode
creation from them.

Failed armed media intake should include one of:

```text
input_rejected
media_download_failed
transcription_failed
transcription_pending
```

Validation, download, transcription, or transcript-storage failure leaves
`audio_one_take` armed for an explicit retry or `/cancel`.

## Release Notes

Use honest wording:

```text
Audio input is enabled for short voice/audio notes. Audio is transcribed first,
then stored as a private IntakeTranscript source artifact. Audio intake does not
create an EpisodeDraft or episode. Raw audio is temporary-only by default.
```

Do not claim:

```text
long-form transcription
voice emotion detection
raw audio archive
clinical interpretation
```

## Readiness Note

Audio alpha is releasable only after this manual smoke passes. Rollback does not
require an episode schema migration or raw-audio deletion because this flow does
not change the episode schema and raw audio is temporary-only by default.

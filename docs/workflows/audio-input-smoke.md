# Audio Input Smoke Checklist

Use this checklist before marking explicit Telegram userflow containment and
audio transcript intake deployable.

## Preconditions

- Branch is based on `epic/input-funnel-alpha`.
- Default transcription provider is `whisper`; local alpha smoke uses
  `.venv/bin/whisper`.
- Whisper command, model, and language values are known to the operator.
- `OPENAI_API_KEY` and explicit `M3_CAPTURE_EXTRACTION_MODEL` are configured.
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
| idle `/start` or `/10q` | idle -> `classic_10q` | classic runtime session only | no pre-draft state |
| idle `/1t` then text | `one_take_text` -> extraction -> review | CaptureArtifact, CaptureExtraction, review session | no gap questions or episode before Save |
| idle `/3b` then three answers | `three_block` -> extraction -> review | restart-safe pre-draft state, CaptureArtifact, CaptureExtraction, review | no gap questions or invented evidence |
| classic 10Q text answer | remains `classic_10q`; advances current question | updated classic runtime session | no audio state or transcript |
| classic 10Q media | remains `classic_10q`; existing text-required reply | unchanged classic runtime session | no download or transcription |
| idle `/1a` | idle -> `one_take_audio`; asks for voice/audio | short-lived capture flow state | no `LoopSession` or episode |
| `one_take_audio` text | remains armed; asks for voice/audio or `/cancel` | unchanged capture flow state | no draft or transcript |
| supported media | transcription -> full transcript -> confirmation | private `IntakeTranscript`; confirmation state | no draft, episode, or raw-audio archive before Continue |
| reject transcript | confirmation -> idle | transcript retained | no draft or episode |
| continue transcript | confirmation -> extraction -> review | CaptureArtifact, CaptureExtraction, review linked to transcript | no episode before final Save |
| extraction failure | flow -> idle with safe restart message | CaptureArtifact plus failed CaptureExtraction | no draft, review, fallback, or episode |
| final Save | review -> idle | observed Episode plus extraction and transcript backlinks | no raw-audio archive |
| `/cancel` from classic | `classic_10q` -> idle | classic runtime state removed | no audio state created |
| `/cancel` from audio | `one_take_audio` -> idle | capture flow state removed | existing transcript, if any, remains; no episode |
| `/help` during either flow | flow state unchanged; current help copy | none | no session/flow mutation |
| `/profile` during either flow | flow state unchanged; current report behavior | none | no session/flow mutation |

Hidden `/capture`, `/capture3`, `/voice`, and `/1v` remain compatibility routes.

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
`one_take_audio` armed for an explicit retry or `/cancel`.

## Release Notes

Use honest wording:

```text
Audio input is enabled for short voice/audio notes. Audio is transcribed first
and stored as a private IntakeTranscript. The complete transcript must be
accepted before grounded schema extraction, and the extracted draft must be
saved before an episode exists. Raw audio is temporary-only by default.
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

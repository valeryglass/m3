# Telegram Flow Routing Audit

## Contained Entry Points

| Entry point | Classification | Contained behavior |
|---|---|---|
| `/start` | explicit command | starts or explicitly restarts `classic_10q` |
| active text | active continuation | answers the current classic 10Q step |
| idle text | idle fallback | returns `/start` guidance |
| idle media | idle fallback | returns `/start` guidance before download or transcription |
| active 10Q media | active-flow conflict | asks for text without downloading media |
| `/voice` | hidden explicit command | arms `audio_one_take` |
| armed audio media | audio intake | stores `IntakeTranscript`, previews it, and returns to idle |
| armed audio text | active-flow conflict | asks for voice/audio or `/cancel` |
| `/capture`, `/capture3` | hidden developer routes | explicitly create draft-backed sessions |
| `/cancel` | explicit command | clears classic, audio, or inconsistent dual state |

## Resolved Coupling

- Idle text and media cannot start capture.
- Audio eligibility comes from separate `audio_one_take` state.
- Audio success does not create or delete a `LoopSession`.
- `/cancel` clears either state and defensively clears both.

## Accepted Containment

```text
idle + /start -> classic_10q
idle + /voice -> audio_one_take awaiting media
idle + arbitrary text/media -> /start guidance
classic_10q + text -> current step
classic_10q + media -> text-required guidance
audio_one_take + media
  -> audio_intake_started
  -> IntakeTranscript source artifact
  -> preview
  -> audio_intake_completed
  -> idle
audio_one_take + text -> media-or-cancel guidance
```

`IntakeTranscript` remains a source artifact. The router must not convert audio
intake into an `EpisodeDraft`, episode, annotation, graph, or report.

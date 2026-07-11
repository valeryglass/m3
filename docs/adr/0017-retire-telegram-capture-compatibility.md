# 0017: Retire Telegram Capture Compatibility Routes

## Status

Accepted and implemented for RM-10.

## Context

ADRs 0009 and 0013 retained `/voice`, `/1v`, `/capture`, and `/capture3` while
the first-class `/1a`, `/1t`, and `/3b` flows matured. The canonical flows now
use the shared `CaptureFlowStore -> CaptureArtifact -> CaptureExtraction ->
review/gap` pipeline.

The direct `/capture` and `/capture3` handlers duplicate that pipeline with a
second command grammar. `/voice` and `/1v` only alias `/1a`. The runtime no
longer imports the audio-only flow facade, and the operator verified that the
private legacy `data/runtime-flows/audio-one-take/` path contains no flow files.

## Decision

The supported Telegram user command surface is:

```text
/start /10q /3b /1t /1a /status /profile /cancel /help
```

- `/voice`, `/1v`, `/capture`, and `/capture3` are unregistered.
- Unknown commands receive one `/help` guidance response and do not mutate flow
  state.
- The direct inline and pipe-separated capture handlers are removed.
- `AudioFlowStore` and the old `audio-one-take` path/payload reader are removed.
- `CaptureFlowStore` remains the only pre-draft flow store.
- Telegram voice notes, audio files, audio-like documents, transcription,
  `IntakeTranscript`, and `one_take_audio` remain supported through `/1a`.
- Admin/operator commands remain registered and hidden from the user menu.

## Consequences

- Each capture strategy has one command entry and one runtime path.
- Old commands fail visibly instead of silently selecting compatibility logic.
- Existing canonical runtime-flow files remain readable without migration.
- A deployment that still has legacy `audio-one-take` files must migrate or
  clear those short-lived files before adopting this version.
- Historical UX command events retain their original command names.
- Episode, capture, transcript, annotation, report, and payload schemas do not
  change.

## Rejected Alternative

Keep aliases indefinitely. This preserves old command habits but retains dead
handlers, duplicate tests, and an obsolete persisted-state reader without a
current product use case.

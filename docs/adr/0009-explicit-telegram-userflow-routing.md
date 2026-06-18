# 0009: Explicit Telegram Userflow Routing

## Status

Accepted for `mvp2/userflow-containment`.

## Decision

Telegram input is routed by explicit userflow state before handlers mutate
classic sessions, download media, or persist transcript artifacts.

The MVP userflows are:

```text
idle
classic_10q
audio_one_take
```

Normal entry is command-driven:

```text
/start -> classic_10q
/voice -> audio_one_take
```

Arbitrary idle text or media does not start capture. Hidden `/capture` and
`/capture3` remain explicit developer routes.

Classic 10Q state remains a `LoopSession`. Audio one-take state is stored
separately under `data/runtime-flows/` and expires using the existing initial
session TTL. Commands do not silently replace another active flow; the user must
cancel first.

## Data Flow

```text
audio_one_take awaiting media
  -> temporary Telegram media
  -> transcription provider
  -> IntakeTranscript
  -> transcript preview
  -> idle
```

The audio path does not create an `EpisodeDraft` or `LoopSession`.

## Consequences

- Routing becomes testable without Telegram API or filesystem side effects.
- Idle input can no longer leak into classic 10Q or audio capture.
- `/cancel` must clear either flow and defensively clear inconsistent dual state.
- A small private runtime-flow store is added; no episode schema migration is
  required.

## Non-goals

- no generic workflow framework.
- no audio follow-up questions.
- no transcript-to-episode conversion.
- no annotation, graph, or report changes.
- no raw audio retention.

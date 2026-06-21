# 0013: First-Class Draft Capture Modes

## Status

Accepted for the first-class Telegram capture epic.

## Decision

Telegram exposes four explicit capture modes:

```text
/10q -> classic_10q
/3b  -> three_block
/1t  -> one_take_text
/1a  -> one_take_audio
```

`/start` aliases `/10q`. Hidden `/1v`, `/capture`, `/capture3`, and `/voice`
remain compatibility routes.

Every mode converges on the same provisional boundary:

```text
initial input -> EpisodeDraft -> Gap Hydration -> Save/Cancel review -> Episode
```

Classic 10Q starts an empty draft. Three-block intake stores three sequential
answers before constructing a draft. One-take text seeds only
`observed.situation`. One-take audio first creates an immutable
`IntakeTranscript`; the user must explicitly accept the complete transcript
before its exact text seeds `observed.situation`.

## Runtime State

One chat may have at most one active state:

- a pre-draft `CaptureFlow`; or
- a draft-backed `LoopSession`.

`CaptureFlow` is private TTL state for `awaiting_text`,
`awaiting_three_block`, `awaiting_media`, or
`awaiting_transcript_confirmation`. Existing `audio-one-take` files remain
readable. Existing `LoopSession` files remain readable through optional
defaults.

Commands never replace active work. The user must send `/cancel` before
switching modes.

## Audio Boundary

ADR 0008 remains authoritative for provider isolation and raw-audio retention.
This ADR accepts the previously deferred extraction/validation step:

```text
temporary media
  -> transcription
  -> IntakeTranscript
  -> explicit transcript confirmation
  -> situation-only EpisodeDraft
  -> Gap Hydration
  -> final Save confirmation
  -> Episode
```

Rejecting a transcript keeps the private source artifact but creates no draft or
episode. Saving a confirmed audio-derived episode writes the episode identifier
back to the transcript's existing optional `episode_id`. Raw audio remains
temporary-only.

## Consequences

- Input modes are capture strategies, not episode types.
- The canonical episode schema does not change.
- Transcript confirmation and final episode confirmation are separate gates.
- Initial one-take extraction is deliberately conservative: no observed field
  other than `situation` is inferred.
- UX analytics use the canonical funnels `classic_10q`, `three_block`,
  `one_take_text`, and `one_take_audio`.

## Non-goals

- no multi-field prose or transcript extraction;
- no voice emotion, prosody, or diagnostic inference;
- no raw-audio archive;
- no field-editing workflow on the final review screen;
- no annotation, graph, payload, report, or `/profile` contract changes.

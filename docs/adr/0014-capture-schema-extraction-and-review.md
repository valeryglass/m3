# 0014: Capture Schema Extraction And Review

## Status

Accepted for the capture extraction refactor.

## Decision

Completed capture evidence is converted into a schema-complete
`EpisodeDraft` by a mode-specific extraction boundary before review:

```text
capture evidence
  -> CaptureArtifact
  -> Capture Extraction
  -> EpisodeDraft
  -> DraftReviewSession
  -> Save/Cancel
  -> Episode
```

`classic_10q` remains deterministic direct field collection. `three_block`,
`one_take_text`, and `one_take_audio` use the configured extraction provider.
The initial provider is OpenAI Responses structured output behind a local
protocol. Provider configuration requires both an API key and an explicit
model; there is no implicit model or fallback provider.

This decision supersedes ADR 0013 where it routes non-10Q capture through Gap
Hydration or stores review state in `LoopSession`. ADR 0013 remains accepted for
the visible command set, explicit flow containment, transcript confirmation,
and temporary-only raw audio.

## Evidence Policy

Capture extraction writes provisional observed fields, not derived
annotations. Grounded normalization is allowed:

```text
value        = normalized schema value
source_quote = exact substring from one declared capture piece
```

All seven required observed fields must be present and grounded before review.
`trigger`, `actor`, and `quote` remain optional. A missing field, invented
quote, quote from the wrong three-block evidence group, refusal, incomplete
response, provider failure, or invalid schema rejects the entire extraction.
The bot does not silently fall back to 10Q or Gap Hydration.

## Artifacts

Private durable source and provenance artifacts are stored separately:

```text
data/capture-artifacts/
data/capture-extractions/
```

A `CaptureArtifact` stores completed typed evidence pieces, source metadata,
and hashes. It must not store Telegram file IDs or raw audio.

A `CaptureExtraction` stores success/failure status, safe failure code,
provider/model/prompt version, field-level source-piece references and
confidence, and an optional confirmed episode backlink. These artifacts are not
used as implicit runtime queues or review discovery.

## Runtime State

`LoopSession` owns active classic 10Q progression only.
`DraftReviewSession` owns complete provisional observed fields awaiting
Save/Cancel. A chat may have at most one capture flow, classic session, or
review session.

On extraction failure the bot persists failure provenance, clears the active
capture flow, creates no review or episode, and asks the user to restart the
mode with richer input.

## Consequences

- Capture modes converge at `EpisodeDraft`, not at missing questions.
- Gap Hydration remains an experimental module but is not used by production
  non-10Q capture.
- Episode persistence no longer accepts `LoopSession` as its contract.
- Capture input and extraction provenance remain private and reproducible.
- Profile, annotation, Insight, Map, and canonical Episode schemas do not
  change.

## Non-goals

- no field-editing review workflow;
- no automatic provider retry;
- no implicit latest artifact selection;
- no raw-audio retention;
- no diagnostic inference;
- no changes to downstream annotation or payload contracts.

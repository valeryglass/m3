# Capture Extraction

## Purpose

Project a complete `CaptureArtifact` into a schema-complete `EpisodeDraft`
without inventing unsupported observed evidence.

## Providers

- `classic_10q` uses deterministic direct projection.
- `three_block`, `one_take_text`, and `one_take_audio` require the configured
  OpenAI Responses provider.

Production non-10Q extraction requires both `OPENAI_API_KEY` and an explicit
`M3_CAPTURE_EXTRACTION_MODEL`. There is no default model and no fallback to
10Q or Gap Hydration.

## Grounding

All seven required observed fields must be non-empty. Optional trigger, actor,
and quote fields may be absent. Every field carries an exact `source_quote`
and its source piece role. Normalized values are allowed; invented evidence,
wrong 3B evidence groups, malformed output, refusal, incomplete output, and
provider failures reject the whole extraction.

Every attempt writes a private `CaptureExtraction` sidecar under
`data/capture-extractions/`. Sidecars record status, provider/model/prompt
provenance, parsed fields or a safe failure code, source-piece references, and
an optional confirmed episode backlink.

## Lifecycle

`experimental`

# capture_to_draft

## Contract

Capture Extraction consumes one persisted `CaptureArtifact` and returns either
a schema-complete provisional `EpisodeDraft` or a typed failure.

## Input

- one explicit `CaptureArtifact`;
- its canonical capture mode;
- deterministic 10Q projection or the explicitly configured extraction
  provider.

## Output

- a persisted `CaptureExtraction` sidecar;
- on success, all seven required observed fields plus supported optional
  fields;
- on failure, a safe failure code and no draft or review session.

## Guarantees

- the capture artifact exists before provider work begins;
- provider work runs outside the Telegram event loop;
- every source quote is an exact substring of its declared evidence piece;
- 3B fields use their intended evidence group;
- unsupported completion rejects the entire result;
- successful output enters `DraftReviewSession` directly;
- non-10Q production flows do not call Gap Hydration;
- no episode is persisted through this interface.

## Ownership

- producer: `capture_extraction`
- consumer: `episode_drafts`

## Lifecycle

`experimental`

# capture_to_draft

## Contract

Capture Extraction consumes one persisted `CaptureArtifact` and returns either
a schema-complete provisional `EpisodeDraft`, a partial provisional draft for
gap continuation, or a typed failure with no usable draft context.

## Input

- one explicit `CaptureArtifact`;
- its canonical capture mode;
- deterministic 10Q projection or the explicitly configured extraction
  provider.

## Output

- a persisted `CaptureExtraction` sidecar;
- on success, all seven required observed fields plus supported optional
  fields;
- on failure, a safe failure code;
- on non-10Q failure with usable context, a partial `EpisodeDraft` for the
  normal missing-field flow.

## Guarantees

- the capture artifact exists before provider work begins;
- provider work runs outside the Telegram event loop;
- every source quote is an exact substring of its declared evidence piece;
- 3B fields use their intended evidence group;
- unsupported completion rejects the successful extraction sidecar;
- successful schema-complete output enters `DraftReviewSession` directly;
- partial non-10Q output enters the existing missing-field loop before review;
- no episode is persisted through this interface.

## Ownership

- producer: `capture_extraction`
- consumer: `episode_drafts`, `loop_extractor`, `draft_review_sessions`

## Lifecycle

`experimental`

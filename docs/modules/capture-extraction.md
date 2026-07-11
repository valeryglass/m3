# Capture Extraction

## Purpose

Project a complete `CaptureArtifact` into a schema-complete `EpisodeDraft`
without inventing unsupported observed evidence.

## Providers

- `classic_10q` uses deterministic direct projection.
- `three_block`, `one_take_text`, and `one_take_audio` require the configured
  capture extraction provider.

Runtime mode is explicit:

- `M3_APP_MODE=ml` defaults to `M3_CAPTURE_EXTRACTION_PROVIDER=unavailable`;
- `M3_APP_MODE=production` defaults to
  `M3_CAPTURE_EXTRACTION_PROVIDER=deepseek`.

Production DeepSeek extraction requires `DEEPSEEK_API_KEY` and an explicit
`M3_CAPTURE_EXTRACTION_MODEL`. OpenAI remains supported only when the owner
explicitly sets `M3_CAPTURE_EXTRACTION_PROVIDER=openai` and configures
`OPENAI_API_KEY`.

There is no default model and no fallback to classic 10Q.

Paid extraction calls pass through Provider Operations. Per-user capture quota,
global token budget, queue bound, retry, and circuit state are checked before
DeepSeek/OpenAI work. A blocked call follows the unavailable-provider path: the
capture artifact and typed failure sidecar remain private evidence, usable
partial material may enter gap hydration, and final Save stays schema-gated.

## Debug Visibility

Provider attempts may write private debug sidecars under `data/capture-debug/`.
By default these sidecars store safe parser metadata: response presence and
length, JSON parse status, top-level keys, validation error paths, parsed field
names, missing required fields, and grounding failure codes.

Raw provider output is stored only when the owner explicitly enables
`M3_CAPTURE_DEBUG_RAW_PROVIDER_OUTPUT=1`. Raw debug output is private
diagnostic material only; it is not part of episode schema, annotation schema,
UX analytics, process journal events, reports, or payloads.

## Grounding

All seven required observed fields must be non-empty before direct review.
Optional trigger, actor, and quote fields may be absent. Every extracted field
carries an exact `source_quote` and its source piece role. Normalized values
are allowed; invented evidence, wrong 3B evidence groups, malformed output,
refusal, incomplete output, and provider failures reject the whole extraction
sidecar.

For non-10Q capture, failed extraction may still seed a partial draft/gap
session from grounded parseable fields or from the original capture artifact.
This does not change the failed extraction status and does not create an
episode. Final review and Save remain blocked until the observed episode is
schema-valid.

Every attempt writes a private `CaptureExtraction` sidecar under
`data/capture-extractions/`. Sidecars record status, provider/model/prompt
provenance, parsed fields or a safe failure code, source-piece references, and
an optional confirmed episode backlink.

Current beta behavior: capture artifacts are saved before extraction, failed
non-10Q extraction stays visible as a failed `CaptureExtraction` sidecar, and
usable partial evidence can continue into missing-field questions while keeping
final Save schema-valid.

## Lifecycle

`experimental`

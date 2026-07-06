# 0015: Beta Runtime Modes And DeepSeek Provider

## Status

Accepted and implemented for RM-01.

## Decision

`Beta-1 Stable Micro Build` uses two runtime mode concepts:

```text
ml
production
```

`ml` means free/non-LLM local mode. In that mode, `/10q` remains deterministic
and usable end to end. Non-10Q capture should fail safely when no extraction
provider is configured: failed extraction sidecar, no draft, no episode, and no
fallback to 10Q or Gap Hydration.

`production` means the DeepSeek API LLM mode for non-10Q capture extraction.
DeepSeek sits behind the existing capture extraction provider protocol.

Owner-controlled settings:

```text
M3_APP_MODE=ml|production
M3_CAPTURE_EXTRACTION_PROVIDER=unavailable|deepseek|openai
DEEPSEEK_API_KEY
M3_DEEPSEEK_BASE_URL
M3_CAPTURE_EXTRACTION_MODEL
```

`M3_CAPTURE_EXTRACTION_MODEL` has no default. Operators must choose an explicit
model, such as `deepseek-v4-flash`, so provider model changes do not require a
code change.

## Runtime Truth

DeepSeek is the default production provider after RM-01. OpenAI Responses
remains available only when the owner explicitly sets
`M3_CAPTURE_EXTRACTION_PROVIDER=openai`.

Missing credentials or model do not crash Telegram capture. The provider factory
returns `UnavailableCaptureExtractionProvider`, so the existing extraction
failure path writes a typed sidecar and creates no draft or episode.

## Consequences

- `classic_10q` remains deterministic.
- RM-01 does not add silent fallback paths for non-10Q extraction.
- RM-01 does not change schemas, Telegram command surface, or private data
  retention.
- Reports, graph analytics, annotation production, and map exports remain
  deterministic unless a later ADR explicitly changes that boundary.

## Non-goals

- no LLM annotation producer;
- no LLM report rewriting;
- no new capture mode;
- no episode schema change;
- no raw-audio retention change.

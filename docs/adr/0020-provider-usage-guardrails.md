# 0020: Provider Usage Guardrails

## Status

Accepted and implemented for RM-14. Live quota tuning and provider-health
evidence remain part of RM-16.

## Context

Production capture extraction and profile interpretation use a paid external
provider. The single-writer and worker bounds introduced in RM-13 prevent local
write races and event-loop blocking, but they do not limit daily calls, token
cost, queue pressure, or repeated calls during a provider incident.

Public-beta operation needs a local, content-free control boundary that applies
to both provider surfaces without changing capture, episode, annotation, or
report contracts.

## Decision

- `app.provider_guard` owns shared provider admission, usage accounting, retry,
  and circuit behavior.
- Owner-configured per-user daily call limits apply independently to capture and
  profile calls.
- One per-user semaphore prevents a single user from occupying more than one
  provider slot. A global semaphore and queue timeout bound total in-flight
  work.
- A provider call is counted when its reservation is acquired. Token totals are
  recorded after a response only when the provider returns usage metadata.
- Daily count and token state is stored atomically in
  `data/provider-usage/state.json` and resets by UTC day.
- The daily token budget, consecutive retryable failures, and circuit cooldown
  apply across capture and profile surfaces.
- Retryable provider failures use bounded exponential backoff. Rate limiting has
  the additive safe capture failure code `rate_limited`.
- Missing or invalid usage state blocks a new paid call. Failure to append token
  telemetry after an already successful response is journaled and must not
  trigger a duplicate provider call.
- A blocked profile uses the existing deterministic report. A blocked non-10Q
  extraction uses the existing unavailable-provider/partial-gap path and never
  bypasses final schema validation.
- Usage state and journal events contain identity, surface, counts, token totals,
  status, and failure codes only. They never contain prompts, provider output,
  API keys, episode text, transcripts, or report text.

## Consequences

- Limits survive normal bot restart without introducing a database.
- Exact provider cost remains approximate when an API omits usage metadata;
  call quotas and in-flight limits still apply.
- The semaphore boundary is process-local and relies on the RM-13 single bot
  writer policy. Multi-instance provider coordination is out of scope.
- Provider usage records participate in identity-scoped export and deletion.
- Operators must tune limits against real beta evidence before release rather
  than treating defaults as a commercial budget decision.

## Rejected Alternatives

- Rely only on provider-dashboard limits. That does not bound local queues or
  provide per-user admission.
- Introduce a database or remote rate-limit service for the small single-host
  beta. That adds operational surface without changing the current requirement.
- Retry after telemetry persistence failure. The paid response already exists,
  so another provider call could duplicate cost without improving the result.

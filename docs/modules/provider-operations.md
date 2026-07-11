# Provider Operations

## Purpose

Bound paid capture and profile provider calls before they create unbounded cost,
latency, or queue pressure.

## Inputs

- provider surface: `capture` or `profile`;
- private Telegram identity;
- owner-configured limits;
- safe provider call result and optional token usage counts.

## Outputs

- provider admission or a typed safe blocker;
- private count-only daily usage state;
- bounded retry and circuit state;
- safe UX/process-journal failure metadata.

## Runtime Policy

`ProviderGuard` shares one global in-flight semaphore and one single-slot
semaphore per user. It checks persistent daily quotas and circuit state before a
call, consumes one call reservation before provider work, and records returned
token usage afterward.

The owner configures policy with:

```text
M3_PROVIDER_CAPTURE_DAILY_LIMIT
M3_PROVIDER_PROFILE_DAILY_LIMIT
M3_PROVIDER_DAILY_TOKEN_BUDGET
M3_PROVIDER_MAX_IN_FLIGHT
M3_PROVIDER_QUEUE_TIMEOUT_SEC
M3_PROVIDER_CIRCUIT_FAILURE_THRESHOLD
M3_PROVIDER_CIRCUIT_COOLDOWN_SEC
M3_PROVIDER_MAX_RETRIES
M3_PROVIDER_RETRY_BACKOFF_SEC
```

Daily state lives at `M3_PROVIDER_USAGE_STATE`, defaults to
`data/provider-usage/state.json`, and resets on the next UTC day. It contains
call counts, token totals, and circuit counters only.

Before a paid call, unreadable state fails closed with
`usage_state_unavailable`. After a provider has already returned, telemetry
write failure is best-effort and journals `usage_state_write_failed`; it never
causes a duplicate provider request.

## Operator Check

With the bot stopped or while only reading the atomic state:

```bash
.venv/bin/python -m app.provider_guard
```

The output is private because it includes user IDs. It contains no submitted or
generated content.

## Privacy

Never add prompts, responses, episode text, transcripts, report copy, source
quotes, or credentials to provider usage state. Identity-scoped provider counts
are included in the User Data Rights export/delete workflow.

## Lifecycle

`experimental`

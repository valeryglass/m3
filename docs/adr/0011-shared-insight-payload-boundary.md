# ADR 0011: Shared Insight Payload Boundary

## Status

Accepted

## Context

User reports and map payloads previously selected analytics directly from
`GraphReport`. That allowed downstream surfaces to choose different primary
motifs, forks, contrasts, counterexamples, or outcomes from the same evidence.
It also mixed target-agnostic analytics with report wording and map projection
concerns.

## Decision

Introduce Insight Payloads as the boundary between Graph Reporting and
downstream report and map consumers:

```text
GraphReport
-> InsightPayload
   -> user report rendering
   -> SpatialPayload
   -> map payload analytics
```

`InsightPayload` owns deterministic, target-agnostic analytics with support
provenance. It contains raw labels and no user-facing copy or layout decisions.
`SpatialPayload` projects those analytics into renderer-neutral paths, markers,
and outcome links without choosing coordinates.

Transfer ownership of `report_to_payload` from Graph Reporting to Insight
Payloads. Pattern Payloads may still consume report-ready episodes for
map-specific entities, topology, and provenance, but shared primary analytics
must come from the same `InsightPayload` used by report rendering.

## Consequences

- reports and maps share one deterministic analytics selection.
- report wording remains separate from machine payloads.
- map payloads expose shared insight and spatial analytics while retaining
  their existing semantic entity and topology fields.
- insight and spatial payloads are derived projections, not source-of-truth
  storage.
- episode and annotation-run schemas are unchanged.

## Policy

Downstream consumers must not independently reselect conflicting primary
analytics already represented by `InsightPayload`. Explicit payload exports may
contain private derived data and must remain under their declared export
directories. Insight and spatial payload versions remain experimental and do
not establish persisted source compatibility.

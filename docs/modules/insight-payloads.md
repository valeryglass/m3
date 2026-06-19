# Insight Payloads

## Purpose

Produce the shared deterministic analytics artifact used by downstream report
and map consumers.

## Inputs

- computed `GraphReport` views.
- deterministic pattern metrics with episode-level support provenance.

## Outputs

- target-agnostic `InsightPayload` objects.
- optional explicit JSON debug exports under `data/exports/insight-payload/`.

## Dependencies

- Graph Reporting for report-ready graph projections.
- `app.pattern_metrics` for deterministic support sets and ranking.

## Interfaces

- `report_to_insight_payload`
- `report_to_payload`

## Lifecycle

`experimental`

`InsightPayload` is not a source of truth. It is a deterministic projection over
report-ready graph material. It carries raw analytics entities such as motifs,
forks, counterexamples, contrasts, outcome patterns, coverage, gaps, and
provenance.

It must not contain user-facing copy, map layout decisions, hex-grid concepts,
LLM-generated interpretations, diagnostic claims, or stable-trait claims.

Reports and maps are downstream consumers of this payload. Reports first project
it into report cards; maps first project it into spatial payloads. These views may
render the same analytics differently, but they must not reselect conflicting
primary motifs, forks, contrasts, or outcomes.

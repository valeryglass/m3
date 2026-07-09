# Insight Payloads

## Purpose

Produce the shared deterministic analytics artifact used by downstream report
and map consumers.

## Inputs

- computed `GraphReport` views.
- deterministic pattern metrics with episode-level support provenance.

## Outputs

- target-agnostic `InsightPayload` objects.
- domain distributions and compact primary-domain analytics summaries.
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

For beta analytics, `InsightPayload` is the shared machine source for both
Report Entities and Map Primitives:

```text
Internal Analytics -> InsightPayload -> Report Entities / Map Primitives
```

For Beta-1, keep the analytical entity ladder explicit at the report/payload
layer:

```text
atom -> pair -> signature / set_signature -> path_motif / set_motif -> attractor -> insight
```

Ordered signatures and path motifs may describe sequence only when the source
graph relation supports it. `set_signature` and `set_motif` describe unordered
co-presence and must not be rendered as causality.

Version `0.2` adds primary/secondary domain distribution and compact summaries
per primary domain: support, dominant motif, main fork, and top outcomes.
Primary-domain summaries partition episodes; secondary domains remain
distribution metadata.

It must not contain user-facing copy, report-card wording, map layout decisions,
hex-grid concepts, LLM-generated interpretations, diagnostic claims,
stable-trait claims, or unsupported causal claims.

Reports and maps are downstream consumers of this payload. Reports first project
it into Report Entities, then report cards. Maps first project it into spatial
payloads and Map Primitives. These views may render the same analytics
differently, but they must not reselect conflicting primary motifs, forks,
contrasts, or outcomes.

File export requires an explicitly selected annotation-run, full row coverage,
and payload-eligible derived data for every episode in the selected source.
Export fails before writing when any selected episode is pending or ineligible.

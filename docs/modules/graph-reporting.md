# Graph Reporting

## Purpose

Build computed graph views, deterministic cross-episode analytics, graph
readiness reports, and user-facing report projections from observed episodes
plus selected annotations.

## Inputs

- analytics-ready episodes.
- readiness classifications.
- selected derived annotations and relations.

## Outputs

- computed `GraphReport` objects.
- shared deterministic pattern metrics with episode-level support provenance.
- plain-language `/profile` summary and details projections.
- optional Markdown debug exports.

## Dependencies

- Annotation Runs for derived graph data.
- Readiness gates for report inclusion.

## Interfaces

- `annotation_to_report`

## Lifecycle

`experimental`

Report shapes are useful locally, but not yet frozen as stable public outputs.

`GraphReport` is the current in-memory computed GraphView. It is built on
demand and is not a stored source-of-truth artifact.

`app.pattern_metrics` owns reusable deterministic counts and episode-support
sets for report and payload consumers. `app.user_report` composes those facts
into cautious user-facing observations; it does not generate new annotations
or diagnostic interpretations.

`app.graph_report` without `--output-dir` prints Markdown only and must not
write report files. Markdown export happens only when `--output-dir` is
explicitly passed.

# Graph Reporting

## Purpose

Build computed graph views, graph readiness reports, and repeated signature
summaries from observed episodes plus selected annotations.

## Inputs

- analytics-ready episodes.
- readiness classifications.
- selected derived annotations and relations.

## Outputs

- computed `GraphReport` objects.
- Markdown debug exports under `data/reports/graph/`.

## Dependencies

- Annotation Workflow for derived graph data.
- Readiness gates for report inclusion.

## Interfaces

- `annotation_to_report`

## Lifecycle

`experimental`

Report shapes are useful locally, but not yet frozen as stable public outputs.

`GraphReport` is the current in-memory computed GraphView. It is built on
demand and is not a stored source-of-truth artifact.
